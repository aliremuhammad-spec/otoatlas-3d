import numpy as np, glob
def load_colour(d="/tmp/devc/repo"):
    parts=[np.load(p) for p in sorted(glob.glob(d+"/ZETA_colour_0p2_part*.npz"))]
    rgb=np.concatenate([p["rgb"] for p in parts],axis=1)  # [c,x,y,z]
    return rgb, parts[0]["spacing"]
def load_cbct(f="/tmp/devm/repo/ZETA.npz"):
    z=np.load(f); return z
