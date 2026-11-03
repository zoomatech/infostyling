#!/usr/bin/env python3
import os,sys,gi
gi.require_version('Gimp','3.0');gi.require_version('Gegl','0.4')
from gi.repository import Gimp,Gegl,GObject
sys.path.insert(0,os.path.dirname(__file__))
from core import frame_bits,v3_frame_bits,render,blind_capacity_bytes,apply_blind,decode_blind,decode_camera
from config import STYLE_LABELS,PARAMS,profile
import gimp_host as H
APPLY='plug-in-infostyling-apply';DECODE='plug-in-infostyling-decode-blind';CAMERA='plug-in-infostyling-decode-camera'
def apply_run(p,mode,image,drawables,cfg,data):
 layer,err=H.layer(p,drawables)
 if err:return err
 if mode==Gimp.RunMode.INTERACTIVE and not H.dialog(p,cfg,'Apply InfoStyling',['message','style']+[x[0] for x in PARAMS]):return p.new_return_values(Gimp.PDBStatusType.CANCEL,None)
 try:
  Gegl.init(None);q=profile(cfg);text=cfg.get_property('message') or ''
  if not text:return H.fail(p,'Enter a payload.',Gimp.PDBStatusType.CALLING_ERROR)
  w=layer.get_width();h=layer.get_height();cap=blind_capacity_bytes(w,h,q['blind_cell']);n=len(text.encode())
  if n>cap:return H.fail(p,f'Payload is {n} bytes; current ISB3 capacity is approximately {cap}.',Gimp.PDBStatusType.CALLING_ERROR)
  _,_,src=H.rgba(layer);image.undo_group_start();out=Gimp.Layer.new_from_drawable(layer,image);image.insert_layer(out,layer.get_parent(),image.get_item_position(layer));visible=render(src,w,h,frame_bits(text),q);styled,_=apply_blind(visible,w,h,v3_frame_bits(text,q['style'],q['blind_cell'],q['seed']),q);H.write(out,styled);out.set_name(f"InfoStyled • {q['style']} [IS5 src={layer.get_id()} cell={q['blind_cell']}]");image.set_selected_layers([out]);image.undo_group_end();Gimp.displays_flush();return p.new_return_values(Gimp.PDBStatusType.SUCCESS,None)
 except Exception as e:
  try:image.undo_group_end()
  except:pass
  return H.fail(p,str(e))
def decode_run(p,mode,image,drawables,cfg,data):
 layer,err=H.layer(p,drawables)
 if err:return err
 if mode==Gimp.RunMode.INTERACTIVE and not H.dialog(p,cfg,'Decode InfoStyling (Blind)',['hint-cell','deep-search']):return p.new_return_values(Gimp.PDBStatusType.CANCEL,None)
 try:
  Gegl.init(None);_,_,rgba=H.rgba(layer);r=decode_blind(rgba,layer.get_width(),layer.get_height(),cfg.get_property('hint-cell'),cfg.get_property('deep-search'));text=r['text']
  if mode==Gimp.RunMode.INTERACTIVE:Gimp.message(f"ISB3 decode OK — CRC valid\n\n{text}\n\nCarrier: {r['cell']} px; offset {r['offx']},{r['offy']}")
  return H.text_result(p,text)
 except Exception as e:return H.fail(p,str(e))
def camera_run(p,mode,image,drawables,cfg,data):
 layer,err=H.layer(p,drawables)
 if err:return err
 fields=['hint-cell','deep-search','corners','rect-width','rect-height','rotation-x10','lens-k1-x1000','lens-k2-x1000']
 if mode==Gimp.RunMode.INTERACTIVE and not H.dialog(p,cfg,'Decode InfoStyling Photograph / Print',fields):return p.new_return_values(Gimp.PDBStatusType.CANCEL,None)
 try:
  Gegl.init(None);_,_,rgba=H.rgba(layer);w=layer.get_width();h=layer.get_height();r=decode_camera(rgba,w,h,cfg.get_property('hint-cell'),H.quad(cfg.get_property('corners'),w-1,h-1),cfg.get_property('rect-width'),cfg.get_property('rect-height'),cfg.get_property('lens-k1-x1000')/1000,cfg.get_property('lens-k2-x1000')/1000,cfg.get_property('rotation-x10')/10,cfg.get_property('deep-search'));text=r['text']
  if mode==Gimp.RunMode.INTERACTIVE:Gimp.message(f"ISB3 camera decode OK — CRC valid\n\n{text}\n\nRectified: {r['rect_width']}×{r['rect_height']}; carrier {r['cell']} px")
  return H.text_result(p,text)
 except Exception as e:return H.fail(p,str(e))
def base(plugin,name,run,label,doc):
 p=Gimp.ImageProcedure.new(plugin,name,Gimp.PDBProcType.PLUGIN,run,None);p.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.DRAWABLE);p.set_menu_label(label);p.add_menu_path('<Image>/Filters/Artistic');p.set_image_types('RGB*');p.set_attribution('InfoStyling project','InfoStyling project','2026');p.set_documentation(doc,doc,None);return p
def common_decode(p):
 p.add_int_argument('hint-cell','Carrier cell hint',None,6,64,16,GObject.ParamFlags.READWRITE);p.add_boolean_argument('deep-search','Deep crop/grid-phase search',None,False,GObject.ParamFlags.READWRITE)
def result(p):p.add_string_return_value('decoded-text','Decoded text',None,'',GObject.ParamFlags.READWRITE);return p
class InfoStyling(Gimp.PlugIn):
 def do_query_procedures(self):return[APPLY,DECODE,CAMERA]
 def do_create_procedure(self,name):
  if name==APPLY:
   p=base(self,name,apply_run,'_Apply InfoStyling…','Encode text into an artistic visual style');p.add_string_argument('message','Payload','UTF-8 text to encode','',GObject.ParamFlags.READWRITE);p.add_choice_argument('style','Style',None,H.choice(STYLE_LABELS),'engraving',GObject.ParamFlags.READWRITE)
   for n,_,label,lo,hi,val,_ in PARAMS:p.add_int_argument(n,label,None,lo,hi,val,GObject.ParamFlags.READWRITE)
   return p
  if name==DECODE:
   p=base(self,name,decode_run,'_Decode InfoStyling (Blind)','Decode an ISB3 raster without its source layer');common_decode(p);return result(p)
  if name==CAMERA:
   p=base(self,name,camera_run,'_Decode InfoStyling Photograph / Print','Rectify a photographed print and decode ISB3');common_decode(p);p.add_string_argument('corners','Artwork corners (%)','TLx,TLy;TRx,TRy;BRx,BRy;BLx,BLy','0,0;100,0;100,100;0,100',GObject.ParamFlags.READWRITE);p.add_int_argument('rect-width','Rectified width (0 auto)',None,0,20000,0,GObject.ParamFlags.READWRITE);p.add_int_argument('rect-height','Rectified height (0 auto)',None,0,20000,0,GObject.ParamFlags.READWRITE);p.add_int_argument('rotation-x10','Rotation correction ×10 degrees',None,-300,300,0,GObject.ParamFlags.READWRITE);p.add_int_argument('lens-k1-x1000','Lens k1 ×1000',None,-500,500,0,GObject.ParamFlags.READWRITE);p.add_int_argument('lens-k2-x1000','Lens k2 ×1000',None,-500,500,0,GObject.ParamFlags.READWRITE);return result(p)
Gimp.main(InfoStyling.__gtype__,sys.argv)
