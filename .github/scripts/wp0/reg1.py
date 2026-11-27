import sys; sys.path.insert(0,"/tmp/work")
import numpy as np, SimpleITK as sitk, itertools, time, json
from load import *
from scipy import ndimage
rgb,sp_c=load_colour(); gray=rgb.mean(0).astype(np.float32)
z=load_cbct(); cb=z["cbct__u8"].astype(np.float32); org=z["cbct__origin"]; sp=0.125
# CBCT block-average x3
f=3; s=[(n//f)*f for n in cb.shape]
cb3=cb[:s[0],:s[1],:s[2]].reshape(s[0]//f,f,s[1]//f,f,s[2]//f,f).mean(axis=(1,3,5))
spf=sp*f; orgf=org+sp  # centre of the first 3-voxel block
def to_img(a,spacing,origin):
    im=sitk.GetImageFromArray(np.ascontiguousarray(a.transpose(2,1,0)))
    im.SetSpacing([float(v) for v in spacing]); im.SetOrigin([float(v) for v in origin]); return im
fixed=to_img(cb3,[spf]*3,orgf)
# cylinder centre in CBCT (xy) from the outer ring at mid z
mid=cb3[:,:,cb3.shape[2]//2]; m=mid>20
xs=np.argwhere(m); cxy=orgf[:2]+xs.mean(0)*spf; print("cbct cylinder centre xy",cxy)
gc=gray.copy(); mask_c=gc>10
res=[]
def make_moving(flip):
    g=gray
    for ax in range(3):
        if flip[ax]: g=np.flip(g,ax)
    mk=g>10
    c_xy=np.argwhere(mk.any(2)).mean(0)*sp_c[:2]
    return g,mk,c_xy
t0=time.time()
for flip in itertools.product([0,1],repeat=3):
    g,mk,c_xy=make_moving(flip)
    mov=to_img(g,sp_c,[0,0,0]); mmask=to_img(mk.astype(np.uint8),sp_c,[0,0,0])
    ext=np.array(g.shape)*sp_c
    for dz in [-8,-4,0,4,8]:
        for rot in [-15,0,15]:
            # transform maps fixed point -> moving point: p_m = R(p_f - c_f) + c_m ; set via translation
            tr=sitk.Euler3DTransform(); tr.SetRotation(0,0,np.deg2rad(rot))
            cf=np.array([cxy[0],cxy[1],orgf[2]+cb3.shape[2]*spf/2+dz])
            cm=np.array([c_xy[0],c_xy[1],ext[2]/2])
            tr.SetCenter(cf.tolist()); tr.SetTranslation((cm-cf).tolist())
            reg=sitk.ImageRegistrationMethod(); reg.SetMetricAsMattesMutualInformation(32)
            reg.SetMetricSamplingStrategy(reg.RANDOM); reg.SetMetricSamplingPercentage(0.05,42)
            reg.SetMetricMovingMask(mmask); reg.SetInterpolator(sitk.sitkLinear)
            reg.SetInitialTransform(tr,inPlace=False)
            v=reg.MetricEvaluate(fixed,mov)
            res.append((v,flip,dz,rot))
    print(flip, "best so far", min(r[0] for r in res if r[1]==flip), f"{time.time()-t0:.0f}s", flush=True)
res.sort(key=lambda r:r[0])
for r in res[:12]: print(r)
json.dump([(float(a),list(b),c,d) for a,b,c,d in res[:30]],open("reg1_top.json","w"))
