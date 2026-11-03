import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'infostyling'))
from core import codec,style,carrier
W=H=512;MSG='Cross-language InfoStyling v0.6 ✓'
p={'style':'fractal','strength':54,'cell_size':20,'density':64,'contrast':35,'luminance':25,'hue':20,'inversion':8,'carrier':36,'wobble':8.5,'wobble_scale':30,'payload_wobble':72,'octaves':6,'persistence':.64,'lacunarity':2.15,'line_width':1.5,'orientation':12,'roughness':85,'blind_cell':12,'blind_strength':76,'seed':24681357}
def src():
 a=bytearray(W*H*4)
 for y in range(H):
  for x in range(W):
   i=(y*W+x)*4;a[i]=70+x%150;a[i+1]=60+y%160;a[i+2]=90+(x+y)%130;a[i+3]=255
 return bytes(a)
mode,file=sys.argv[1:3]
if mode=='decode':
 r=carrier.decode(Path(file).read_bytes(),W,H,12,False);assert r['text']==MSG,r;print('Python decoded JS raster PASS')
else:
 v=style.render(src(),W,H,codec.frame_bits(MSG),p);e,_=carrier.apply(v,W,H,codec.v3_frame_bits(MSG,p['style'],p['blind_cell'],p['seed']),p);Path(file).write_bytes(e)
