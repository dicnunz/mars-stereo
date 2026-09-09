"""Deterministic textured-mesh flythrough; no geometry exists beyond stereo support."""
import json,subprocess,math,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from numba import njit
ROOT=Path(__file__).resolve().parents[1]
@njit(cache=True)
def raster(v,faces,uv,tex,w,h,f):
 im=np.zeros((h,w,3),np.uint8);im[:,:,:]=255;depth=np.full((h,w),1e10)
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
# Figure typography and placement follow Maki et al. (2003), Figs. 25–27.
# Keep scientific labels outside image pixels.
FONT_PATHS = [
 '/System/Library/Fonts/Supplemental/Times New Roman.ttf',
 '/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf',
 '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
 'C:/Windows/Fonts/times.ttf',
]
def F(size):
 for path in FONT_PATHS:
  if Path(path).is_file(): return ImageFont.truetype(path,size)
 return ImageFont.load_default(size=size)
def ease(x): return (1-math.cos(math.pi*np.clip(x,0,1)))/2
def camera(t):
 s=ease((t-12)/32)
 pos=np.array([.09*math.sin(2*math.pi*s),-.15*math.sin(math.pi*s),.85*s])
 target=np.array([0.,.1,5.5]);z=target-pos;z/=np.linalg.norm(z)
 x=np.cross([0,1,0],z);x/=np.linalg.norm(x);y=np.cross(z,x)
 return pos,np.stack([x,y,z])
def main():
 d=np.load(ROOT/'output/terrain.npz')
 v,faces,uv,tex=[d[k] for k in ['vertices','faces','uv','texture']]
 raw=[Image.open(ROOT/'output'/n).convert('RGB').resize((864,864),Image.Resampling.LANCZOS) for n in ['left-raw.png','right-raw.png']]
 W,H,fps,duration=1920,1080,30,44
 (ROOT/'demo').mkdir(exist_ok=True)
 proc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(ROOT/'demo/wheatstone.mp4')],stdin=subprocess.PIPE)
 # Side-by-side source and reconstructed surface, following the source paper's
 # neighboring image/XYZ figures. Views are not geometrically rescaled.
 pos,basis=camera(26)
 comparison=Image.fromarray(raster((v-pos)@basis.T,faces,uv,tex,864,864,1150.))
 for frame in range(fps*duration):
  t=frame/fps;im=Image.new('RGB',(W,H),'white');dr=ImageDraw.Draw(im)
  if t<12:
   im.paste(raw[0],(64,56))
   im.paste(raw[1] if t<6 else comparison,(992,56))
   dr.text((64,944),'(a) Left Navcam',font=F(31),fill='black')
   dr.text((992,944),'(b) Right Navcam' if t<6 else '(b) Textured mesh',font=F(31),fill='black')
   dr.text((64,1005),'Spirit, sol 767.  1 March 2006.',font=F(27),fill='black')
   dr.text((1350,1005),'NASA/JPL-Caltech',font=F(27),fill='black')
   if frame==210: im.save(ROOT/'demo/poster.png')
  else:
   pos,basis=camera(t)
   surface=Image.fromarray(raster((v-pos)@basis.T,faces,uv,tex,1792,920,1680.))
   im.paste(surface,(64,32))
   dr.text((64,978),'Spirit, sol 767.  Textured mesh; gaps indicate missing geometry.',font=F(30),fill='black')
   dr.text((64,1024),f'Camera translation: {pos[2]:.2f} m forward.',font=F(25),fill='black')
   dr.text((1480,1024),'NASA/JPL-Caltech',font=F(25),fill='black')
  proc.stdin.write(im.tobytes())
  if frame%300==0: print('frame',frame,flush=True)
 proc.stdin.close()
 if proc.wait()!=0: raise RuntimeError('FFmpeg encoding failed')
 Image.open(ROOT/'demo/poster.png').resize((960,540),Image.Resampling.LANCZOS).save(ROOT/'demo/preview.png')
if __name__=='__main__': main()
