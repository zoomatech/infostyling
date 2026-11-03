from . import carrier,geometry
def blind(src,w,h,hint=16,deep=False):return carrier.decode(src,w,h,hint,deep)
def camera(src,w,h,hint,quad,rect_w=0,rect_h=0,k1=0.,k2=0.,rotation=0.,deep=False):
 work,w2,h2=geometry.undistort(src,w,h,k1,k2);work,w2,h2=geometry.rectify(work,w2,h2,quad,rect_w,rect_h)
 if abs(rotation)>.01:work,w2,h2=geometry.rotate(work,w2,h2,rotation)
 r=carrier.decode(work,w2,h2,hint,deep);r.update(rect_width=w2,rect_height=h2);return r
