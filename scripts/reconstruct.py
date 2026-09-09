"""PDS3 CAHVOR stereo, metric triangulation and an uncertainty-filtered mesh."""
import re,json,hashlib
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
def read_pds(path):
 b=path.read_bytes();header=b[:int(re.search(rb'LABEL_RECORDS\s*=\s*(\d+)',b).group(1))*2048].decode('ascii')
 def number(key):return int(re.search(r'^\s*'+re.escape(key)+r'\s*=\s*(\d+)',header,re.M).group(1))
 model={k:np.fromstring(re.search(r'MODEL_COMPONENT_'+str(i)+r'\s*=\s*\(([^)]+)',header).group(1),sep=',') for i,k in enumerate('CAHVOR',1)}
 image_obj=re.search(r'OBJECT\s*=\s*IMAGE\s*\r?\n(.*?)END_OBJECT\s*=\s*IMAGE',header,re.S).group(1)
 h=int(re.search(r'LINES\s*=\s*(\d+)',image_obj).group(1));w=int(re.search(r'LINE_SAMPLES\s*=\s*(\d+)',image_obj).group(1))
 assert 'MSB_INTEGER' in image_obj and '16' in image_obj
 raw=np.frombuffer(b,dtype='>u2',offset=(number('^IMAGE')-1)*number('RECORD_BYTES'),count=h*w).reshape(h,w)
 return raw,model,header

def project(rays,m):
 """CAHVOR forward projection: distortion is applied around optical axis O."""
 omega=rays@m['O'];lam=rays-omega[...,None]*m['O'];tau=(lam*lam).sum(-1)/omega**2
 mu=m['R'][0]+m['R'][1]*tau+m['R'][2]*tau**2
 p=rays+mu[...,None]*lam;alpha=p@m['A']
 return (p@m['H'])/alpha,(p@m['V'])/alpha

def main():
 out=ROOT/'output';out.mkdir(exist_ok=True)
 files=sorted((ROOT/'data').glob('*.img'));assert len(files)==2
 L,ml,hl=read_pds(files[0]);R,mr,hr=read_pds(files[1]);assert 'LEFT' in hl and 'RIGHT' in hr
 baseline=np.linalg.norm(mr['C']-ml['C']);ex=(mr['C']-ml['C'])/baseline
 ez=ml['A']+mr['A'];ez-=ex*(ez@ex);ez/=np.linalg.norm(ez);ey=np.cross(ez,ex);ey/=np.linalg.norm(ey)
 basis=np.stack([ex,ey,ez]);n=1024;f=1150.;cx=cy=(n-1)/2
 yy,xx=np.mgrid[:n,:n];rays=(xx[...,None]-cx)/f*ex+(yy[...,None]-cy)/f*ey+ez
 lo,hi=np.percentile(np.concatenate([L.ravel(),R.ravel()]),[.5,99.5])
 rect=[];maps=[]
 for a,m,name in [(L,ml,'left'),(R,mr,'right')]:
  u,v=project(rays,m);maps.append((u,v));im=np.uint8(np.clip((a-lo)/(hi-lo),0,1)*255)
  Image.fromarray(im).save(out/(name+'-raw.png'))
  rect.append(cv2.remap(im,u.astype('float32'),v.astype('float32'),cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT))
  Image.fromarray(rect[-1]).save(out/(name+'.png'))
 # Empirically refine subpixel vertical registration; its physical cause is not established.
 sift=cv2.SIFT_create();kl,desl=sift.detectAndCompute(rect[0],None);kr,desr=sift.detectAndCompute(rect[1],None)
 matches=cv2.BFMatcher().knnMatch(desl,desr,k=2)
 dy=np.array([kl[a.queryIdx].pt[1]-kr[a.trainIdx].pt[1] for a,b in matches if a.distance<.7*b.distance])
 inlier=dy[np.abs(dy-np.median(dy))<1.5];vertical_offset=float(np.median(inlier))
 assert abs(vertical_offset)<2, 'Calibration mismatch too large for translation refinement'
 rect[1]=cv2.warpAffine(rect[1],np.float32([[1,0,0],[0,1,vertical_offset]]),(n,n),flags=cv2.INTER_CUBIC)
 Image.fromarray(rect[1]).save(out/'right.png')
 # Left/right independent disparity estimates permit a cycle-consistency test.
 params=dict(numDisparities=160,blockSize=5,P1=8*25,P2=32*25,disp12MaxDiff=-1,uniquenessRatio=8,speckleWindowSize=100,speckleRange=2,mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY)
 dl=cv2.StereoSGBM_create(minDisparity=0,**params).compute(*rect).astype(float)/16
 dr=cv2.StereoSGBM_create(minDisparity=-160,**params).compute(rect[1],rect[0]).astype(float)/16
 xr=(xx-dl).astype('float32');rr=cv2.remap(dr.astype('float32'),xr,yy.astype('float32'),cv2.INTER_LINEAR,borderValue=-999)
 cycle=abs(dl+rr);depth=f*baseline/np.maximum(dl,.01)
 valid=(dl>2)&(dl<158)&(cycle<1.0)&(depth>.8)&(depth<30)&(xx>170)&(yy>70)&(yy<930)
 for u,v in maps:valid&=(u>3)&(v>3)&(u<1020)&(v<1020)
 xyz=np.stack([(xx-cx)*depth/f,(yy-cy)*depth/f,depth],-1)
 # Grid mesh preserves pixel topology, cutting depth jumps and unsupported triangles.
 step=3;grid=xyz[::step,::step];ok=valid[::step,::step];gh,gw=ok.shape
 a=np.arange(gh*gw).reshape(gh,gw);faces=np.concatenate([np.stack([a[:-1,:-1],a[:-1,1:],a[1:,:-1]],-1).reshape(-1,3),np.stack([a[:-1,1:],a[1:,1:],a[1:,:-1]],-1).reshape(-1,3)])
 verts=grid.reshape(-1,3);keep=ok.ravel()[faces].all(1)
 zz=verts[faces,2];keep&=(zz.max(1)-zz.min(1))<(.06+.035*zz.min(1));faces=faces[keep]
 ids=np.unique(faces);remap=np.full(len(verts),-1,int);remap[ids]=np.arange(len(ids));faces=remap[faces];verts=verts[ids]
 uv=np.stack([xx[::step,::step].ravel()/1023,1-yy[::step,::step].ravel()/1023],-1)[ids]
 colors=rect[0][::step,::step].ravel()[ids]
 with open(out/'terrain.obj','w') as h:
  h.write('mtllib terrain.mtl\nusemtl navcam\n')
  for p in verts:h.write('v %.7f %.7f %.7f\n'%tuple(p))
  for p in uv:h.write('vt %.7f %.7f\n'%tuple(p))
  for face in faces+1:h.write('f '+' '.join(f'{i}/{i}' for i in face)+'\n')
 (out/'terrain.mtl').write_text('newmtl navcam\nKd 1 1 1\nmap_Kd left.png\n')
 world=verts@basis+ml['C']
 with open(out/'terrain.ply','w') as h:
  h.write(f'ply\nformat ascii 1.0\nelement vertex {len(world)}\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n')
  for p,c in zip(world,colors):h.write('%.7f %.7f %.7f %d %d %d\n'%(*p,c,c,c))
 np.savez_compressed(out/'terrain.npz',vertices=verts,faces=faces,uv=uv,texture=rect[0],valid=valid,disparity=dl,cycle=cycle,basis=basis,center=ml['C'],baseline=baseline,focal=f)
 heat=cv2.applyColorMap(np.uint8(np.clip(dl/100,0,1)*255),cv2.COLORMAP_TURBO);heat[~valid]=0;cv2.imwrite(str(out/'disparity.png'),heat)
 report={'mission':'Spirit (MER2)','sol':767,'acquired':re.search(r'^ START_TIME\s*=\s*(\S+)',hl,re.M).group(1),'vertical_refinement_px':vertical_offset,'epipolar_residual_after_px_median':float(np.median(abs(inlier-vertical_offset))),'baseline_m':float(baseline),'rectified_focal_px':f,'valid_pixels':int(valid.sum()),'vertices':len(verts),'triangles':len(faces),'depth_m_percentiles':np.percentile(depth[valid],[5,50,95]).tolist(),'left_right_cycle_px_percentiles':np.percentile(cycle[valid],[50,95,100]).tolist(),'one_pixel_depth_uncertainty_m_median':float(np.median(depth[valid]**2/(f*baseline))),'inputs':[{'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'url':'https://planetarydata.jpl.nasa.gov/img/data/mer/mer2no_0xxx/data/sol0767/edr/'+p.name} for p in files]}
 (out/'metrics.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
