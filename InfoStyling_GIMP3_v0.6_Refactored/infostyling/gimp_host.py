import gi
gi.require_version('Gimp','3.0');gi.require_version('Gegl','0.4')
from gi.repository import Gimp,Gegl,GObject,GLib
BINARY='infostyling'
def choice(labels):
 c=Gimp.Choice.new()
 for i,(key,label) in enumerate(labels):c.add(key,i,label,None)
 return c
def rgba(layer):
 b=layer.get_buffer();r=b.get_extent();return b,r,bytes(b.get(r,1.0,"R'G'B'A u8",Gegl.AbyssPolicy.NONE))
def write(layer,data):
 b,r,_=rgba(layer);b.set(r,"R'G'B'A u8",data);b.flush();layer.update(0,0,layer.get_width(),layer.get_height())
def dialog(procedure,config,title,fields):
 gi.require_version('GimpUi','3.0');from gi.repository import GimpUi
 GimpUi.init(BINARY);d=GimpUi.ProcedureDialog.new(procedure,config,title);GimpUi.window_set_transient(d);d.fill(fields);ok=d.run();d.destroy();return ok
def fail(p,msg,status=Gimp.PDBStatusType.EXECUTION_ERROR):return p.new_return_values(status,GLib.Error(msg))
def layer(p,drawables):return(drawables[0],None) if len(drawables)==1 and isinstance(drawables[0],Gimp.Layer) else(None,fail(p,'InfoStyling requires exactly one layer.',Gimp.PDBStatusType.CALLING_ERROR))
def text_result(p,text):
 v=p.new_return_values(Gimp.PDBStatusType.SUCCESS,None);v.insert(1,GObject.Value(GObject.TYPE_STRING,text));return v
def quad(text,w,h):
 pts=[]
 for s in str(text).split(';'):
  x,y=(float(v.strip()) for v in s.split(','));pts.append((x*w/100,y*h/100))
 if len(pts)!=4:raise ValueError('Corners must be TLx,TLy;TRx,TRy;BRx,BRy;BLx,BLy')
 return pts
