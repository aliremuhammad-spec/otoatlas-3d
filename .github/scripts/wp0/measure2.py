import sys; sys.path.insert(0,"/home/claude/otoatlas-3d/DATA_PIPELINE")
import numpy as np, json
from scipy import ndimage
from devtools import devdata as dd
labels,ct=dd.load("ZETA","/tmp/devm/repo"); L=np.load("landmarks.npy",allow_pickle=True).item(); vs=np.load("vestibular.npy",allow_pickle=True).item()
z=np.load("/tmp/devp/ZETA_native_ear.npz"); rgb=z["rgb"].astype(np.float32); sp=z["spacing"]; org=z["origin"]; print("native crop",rgb.shape,sp,org)
# vector gradient magnitude of lightly smoothed colour
sm=np.stack([ndimage.gaussian_filter(rgb[c],(2,2,1)) for c in range(3)])
g2=0
for c in range(3):
    gx,gy,gz=np.gradient(sm[c],sp[0],sp[1],sp[2]); g2=g2+gx**2+gy**2+gz**2
G=np.sqrt(g2).astype(np.float32)
def sample(vol,pts):  # pts (N,3) mm
    idx=((pts-org)/sp).T
    return ndimage.map_coordinates(vol,idx,order=1,mode="nearest")
struct={"malleus":labels["malleus"],"stapes":labels["stapes"],"facial_nerve":labels["facial_nerve"],"scala_tympani":labels["scala_tympani"],
        "scala_vestibuli_vestibular":(vs["mask"],tuple(vs["spacing"]),tuple(vs["origin"]))}

def boundary_pts(m,s,o,step=2):
    s=np.asarray(s); o=np.asarray(o); er=ndimage.binary_erosion(m); bd=np.argwhere(m&~er)[::step]; return o+bd*s
allP=np.concatenate([boundary_pts(*struct[k][:1],struct[k][1],struct[k][2]) for k in ["malleus","stapes","facial_nerve","scala_tympani","scala_vestibuli_vestibular"]])
lo=org+3; hi=org+np.array(rgb.shape[1:])*sp-3
allP=allP[((allP>lo)&(allP<hi)).all(1)]; print("global fit points",len(allP))
def gscore(t): return sample(G,allP+t).mean()
tg=np.zeros(3); bsg=gscore(tg)
for step,span in ((0.1,0.6),(0.025,0.1)):
    c=tg.copy()
    for dx in np.arange(-span,span+1e-9,step):
        for dy in np.arange(-span,span+1e-9,step):
            for dz in np.arange(-span,span+1e-9,step):
                t=c+np.array([dx,dy,dz]); sc=gscore(t)
                if sc>bsg: bsg,tg=sc,t
print("GLOBAL shift (colour = label + t) mm",np.round(tg,3),"gain %",round(float(100*(bsg/gscore(np.zeros(3))-1)),1),flush=True)
TG=tg
R=2.5; out={}
for name,(sname,pt) in L.items():
    m,s,o=struct[sname]; s=np.asarray(s); o=np.asarray(o)
    er=ndimage.binary_erosion(m); bd=np.argwhere(m&~er)
    P=o+bd*s; near=np.linalg.norm(P-pt,axis=1)<R; P=P[near]; bd=bd[near]
    P=P+TG  # sample the colour where the label sits after the global shift
    sm_m=ndimage.gaussian_filter(m.astype(np.float32),1.0); nx,ny,nz=np.gradient(sm_m,*s)
    N=-np.stack([nx[tuple(bd.T)],ny[tuple(bd.T)],nz[tuple(bd.T)]],1); N/=np.maximum(np.linalg.norm(N,axis=1,keepdims=True),1e-9)
    # label boundary lies half a voxel outside the last inside voxel centre
    P=P+N*(0.5*s.mean()*0.0)  # kept at voxel centres; offset of half a voxel reported separately
    ss=np.arange(-0.6,0.6001,0.025)
    prof=np.stack([sample(G,P+N*t) for t in ss],1)
    pk=prof.argmax(1); peak=prof.max(1); ok=peak>1.5*prof.mean(1)
    off=ss[pk][ok]
    # translation search maximising mean edge strength at the boundary points
    def score(t): return sample(G,P+t).mean()
    best=np.zeros(3); bs=score(best)
    for step,span in ((0.1,0.5),(0.025,0.1)):
        c=best.copy()
        for dx in np.arange(-span,span+1e-9,step):
            for dy in np.arange(-span,span+1e-9,step):
                for dz in np.arange(-span,span+1e-9,step):
                    t=c+np.array([dx,dy,dz]); sc=score(t)
                    if sc>bs: bs,best=sc,t
    out[name]={"structure":sname,"point_mm":[round(float(v),2) for v in pt],"boundary_points":int(len(P)),"edge_found_pct":round(100*float(ok.mean()),0),
      "normal_offset_median_mm":round(float(np.median(off)),3),"normal_offset_abs_median_mm":round(float(np.median(np.abs(off))),3),
      "normal_offset_p75_abs_mm":round(float(np.percentile(np.abs(off),75)),3),
      "best_translation_mm":[round(float(v),3) for v in best],"best_translation_norm_mm":round(float(np.linalg.norm(best)),3),
      "edge_gain_pct":round(float(100*(bs/score(np.zeros(3))-1)),1)}
    print(name,json.dumps(out[name],default=float),flush=True)
json.dump({"global_shift_mm":[float(v) for v in TG],"landmarks":out},open("alignment_native_shifted.json","w"),indent=1,default=float)
