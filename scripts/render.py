"""Deterministic textured-mesh flythrough; no geometry exists beyond stereo support."""
import json,subprocess,math,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from numba import njit
ROOT=Path(__file__).resolve().parents[1]
@njit(cache=True)
def raster(v,faces,uv,tex,w,h,f):
 im=np.zeros((h,w,3),np.uint8);im[:,:,0]=9;im[:,:,1]=11;im[:,:,2]=13;depth=np.full((h,w),1e10)
 for tri in faces:
  a,b,c=tri
  if min(v[a,2],v[b,2],v[c,2])<.1:continue
  x0=v[a,0]/v[a,2]*f+w/2;y0=v[a,1]/v[a,2]*f+h/2
  x1=v[b,0]/v[b,2]*f+w/2;y1=v[b,1]/v[b,2]*f+h/2
  x2=v[c,0]/v[c,2]*f+w/2;y2=v[c,1]/v[c,2]*f+h/2
  den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
  if abs(den)<1e-8:continue
  xmin=max(0,int(min(x0,x1,x2)));xmax=min(w-1,int(max(x0,x1,x2))+1)
  ymin=max(0,int(min(y0,y1,y2)));ymax=min(h-1,int(max(y0,y1,y2))+1)
  for y in range(ymin,ymax+1):
   for x in range(xmin,xmax+1):
    p=((y1-y2)*(x-x2)+(x2-x1)*(y-y2))/den;q=((y2-y0)*(x-x2)+(x0-x2)*(y-y2))/den;r=1-p-q
    if p<0 or q<0 or r<0:continue
    inv=p/v[a,2]+q/v[b,2]+r/v[c,2];z=1/inv
    if z>=depth[y,x]:continue
    depth[y,x]=z
    u=(p*uv[a,0]/v[a,2]+q*uv[b,0]/v[b,2]+r*uv[c,0]/v[c,2])*z*(tex.shape[1]-1)
    t=(1-(p*uv[a,1]/v[a,2]+q*uv[b,1]/v[b,2]+r*uv[c,1]/v[c,2])*z)*(tex.shape[0]-1)
    ix=min(tex.shape[1]-2,max(0,int(u)));iy=min(tex.shape[0]-2,max(0,int(t)));du=u-ix;dt=t-iy
    val=tex[iy,ix]*(1-du)*(1-dt)+tex[iy,ix+1]*du*(1-dt)+tex[iy+1,ix]*(1-du)*dt+tex[iy+1,ix+1]*du*dt
    val=min(255,max(0,val));im[y,x,0]=val;im[y,x,1]=val;im[y,x,2]=val
 return im
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
mono='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
def F(n,m=False):return ImageFont.truetype(mono if m else font,n)
def ease(x):return (1-math.cos(math.pi*np.clip(x,0,1)))/2
def camera(t):
 u=np.clip((t-13)/25,0,1);s=ease(u)
 pos=np.array([.09*math.sin(2*math.pi*s),-.15*math.sin(math.pi*s),.85*s])
 target=np.array([0.,.1,5.5]);z=target-pos;z/=np.linalg.norm(z);x=np.cross([0,1,0],z);x/=np.linalg.norm(x);y=np.cross(z,x)
 return pos,np.stack([x,y,z])
def main():
 d=np.load(ROOT/'output/terrain.npz');m=json.loads((ROOT/'output/metrics.json').read_text());v=d['vertices'];faces=d['faces'];uv=d['uv'];tex=d['texture']
 raw=[Image.open(ROOT/'output'/n).convert('RGB').resize((760,760),Image.Resampling.LANCZOS) for n in ['left-raw.png','right-raw.png']]
 W,H,fps,duration=1920,1080,30,44
 (ROOT/'demo').mkdir(exist_ok=True)
 proc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(ROOT/'demo/wheatstone.mp4')],stdin=subprocess.PIPE)
 for frame in range(fps*duration):
  t=frame/fps;im=Image.new('RGB',(W,H),(9,11,13));dr=ImageDraw.Draw(im)
  if t<4:
   alpha=ease(t/.9)*(1-ease((t-3.4)/.6));c=tuple(int(a*alpha) for a in (230,229,222))
   dr.text((115,205),'WHEATSTONE',font=F(30,True),fill=(163,174,171));dr.text((108,318),'A place on Mars.',font=F(104),fill=c)
   dr.text((115,520),'Two rover images. One measured surface.',font=F(32),fill=c)
   dr.line((115,678,1805,678),fill=(54,60,60));dr.text((115,718),'SPIRIT   /   SOL 767   /   01 MARCH 2006',font=F(24,True),fill=c)
  elif t<13:
   im.paste(raw[0],(140,180));im.paste(raw[1],(1020,180));dr=ImageDraw.Draw(im)
   dr.text((140,96),'LEFT NAVCAM',font=F(24,True),fill=(217,224,220));dr.text((1020,96),'RIGHT NAVCAM',font=F(24,True),fill=(217,224,220))
   line=int(180+760*ease((t-5)/6));dr.line((140,line,900,line),fill=(180,232,213),width=2);dr.line((1020,line,1780,line),fill=(180,232,213),width=2)
   dr.text((140,975),'20.03 cm separates the cameras.',font=F(28),fill=(218,223,218));dr.text((1120,980),'PDS ORIGINALS · MONOCHROME',font=F(21,True),fill=(133,148,142))
  elif t<39:
   pos,basis=camera(t);vv=(v-pos)@basis.T
   im=Image.fromarray(raster(vv,faces,uv,tex,W,H,2000.));dr=ImageDraw.Draw(im)
   dr.rectangle((0,0,W,126),fill=(9,11,13));dr.text((72,36),'WHEATSTONE',font=F(24,True),fill=(215,228,218));dr.text((420,36),'RECONSTRUCTED SURFACE',font=F(22,True),fill=(158,176,167))
   dr.text((1430,36),f'{pos[2]:.2f} m  FORWARD',font=F(22,True),fill=(180,232,213))
   dr.rectangle((0,982,W,H),fill=(9,11,13));dr.text((72,1010),f'{m["vertices"]:,} vertices   ·   {m["triangles"]:,} triangles',font=F(24),fill=(218,225,220))
   dr.text((1120,1013),'Black regions have no supported geometry.',font=F(22),fill=(145,160,151))
   if 13<=t<17:
    dr.text((72,169),'A camera move through measured depth.',font=F(36),fill=(235,237,231))
   if frame==660:im.save(ROOT/'demo/poster.png')
  else:
   dr.text((115,160),'BUILT FROM OBSERVATION',font=F(24,True),fill=(166,192,178))
   for i,(big,small) in enumerate([(f'{m["valid_pixels"]:,}','CONSISTENT PIXELS'),(f'{m["left_right_cycle_px_percentiles"][0]:.3f} px','MEDIAN CYCLE ERROR'),(f'{m["depth_m_percentiles"][1]:.2f} m','MEDIAN FORWARD DEPTH')]):
    xx=115+i*600;dr.text((xx,330),big,font=F(66),fill=(232,237,229));dr.text((xx,437),small,font=F(21,True),fill=(152,171,159))
   dr.line((115,570,1805,570),fill=(59,74,64));dr.text((115,632),'Original stereo. Calibrated cameras. Reproducible geometry.',font=F(33),fill=(231,237,229))
   dr.text((115,736),'Navigation imagery is grayscale. Unobserved terrain stays unbuilt.',font=F(24),fill=(152,171,159))
   dr.text((115,835),'Imagery: Courtesy NASA/JPL-Caltech.',font=F(21),fill=(152,171,159))
  dr.line((0,H-3,int(W*(frame+1)/(fps*duration)),H-3),fill=(177,220,192),width=3)
  proc.stdin.write(im.tobytes())
  if frame%300==0:print('frame',frame,flush=True)
 proc.stdin.close();assert proc.wait()==0
if __name__=='__main__':main()
