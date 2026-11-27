import sys; sys.path.insert(0,"/home/claude/otoatlas-3d/DATA_PIPELINE")
import numpy as np
from devtools import devdata as dd
from otopipe import ossicles, facialnerve, split
labels,ct=dd.load("ZETA","/tmp/devm/repo")
print({k:v[0].shape for k,v in labels.items()})
f=dd.frame(labels); print("side",f.side,"umbo",np.round(f.umbo,2))
L={}
L["umbo"]=("malleus",f.umbo)
# footplate via the pipeline's stapes parts
try:
    p=ossicles.stapes_parts(labels["stapes"],labels["incus"],labels["scala_vestibuli"],f)
    m,o=p.parts["footplate"]; idx=np.argwhere(m); pt=np.asarray(o)+idx.mean(0)*np.array(labels["stapes"][1]); L["footplate"]=("stapes",pt); print("footplate",np.round(pt,2),p.report.get("footplate_length_mm"))
except Exception as e:
    print("stapes_parts failed",repr(e)); 
    s=dd.pts(labels["stapes"]); v=dd.pts(labels["scala_vestibuli"]); from scipy.spatial import cKDTree
    d,_=cKDTree(v[::2]).query(s); L["footplate"]=("stapes",s[d<np.percentile(d,15)].mean(0))
# second genu
line=facialnerve.centreline(labels["facial_nerve"],f); gi,ang=facialnerve.second_genu(line); L["second_genu"]=("facial_nerve",line[gi]); print("second genu",np.round(line[gi],2),"angle",round(ang,1),"line len",len(line)*0.5)
# split scala vestibuli -> vestibular part (canals+vestibule)
sv,svs,svo=labels["scala_vestibuli"]; st,sts,sto=labels["scala_tympani"]
sp_=split.split_by_reach(sv,svo,st,sto,svs)
vm,vo=sp_.vestibular.mask,sp_.vestibular.origin
V=np.asarray(vo)+np.argwhere(vm)*np.array(svs); vc=V.mean(0)
rel=V-vc
# lateral canal proxy: roughly in the horizontal plane through the vestibule (|superior|<3 mm), posterior to the vestibule centre, most lateral
sup,lat,ant=rel@f.superior,rel@f.lateral,rel@f.anterior
sel=(np.abs(sup)<3.0)&(ant<0)
L["lateral_canal"]=("scala_vestibuli_vestibular",V[sel][np.argmax(lat[sel])]); print("lateral canal proxy",np.round(L['lateral_canal'][1],2),"vestibular voxels",len(V))
# round window proxy: most lateral voxel of scala tympani (its basal end faces the round window)
S=dd.pts(labels["scala_tympani"]); L["round_window"]=("scala_tympani",S[np.argmax((S-S.mean(0))@f.lateral)]); print("RW proxy",np.round(L['round_window'][1],2))
np.save("landmarks.npy",{k:(a,b) for k,(a,b) in L.items()},allow_pickle=True)
# vestibular part mask for patch boundary
np.save("vestibular.npy",{"mask":vm,"origin":np.asarray(vo),"spacing":np.array(svs)},allow_pickle=True)
