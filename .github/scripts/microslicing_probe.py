"""One-off check of an OpenEar micro-slicing colour volume: size, grid, registration, contrast.

Prints the NRRD header, its extent against the segmentation's, and colour statistics in
three places: the bone label, the empty shell around the ossicles (tympanic cavity), and
the ossicles.
"""
import sys
import tempfile

import nrrd
import numpy as np
from scipy import ndimage

sys.path.insert(0, "DATA_PIPELINE")
import build_content as bc  # noqa: E402
from otopipe import airspace, fetch, openear  # noqa: E402

specimen = sys.argv[1]
with tempfile.TemporaryDirectory() as tmp:
    found = openear.read_segmentation(str(fetch.fetch_openear_member(specimen, "06_Segmentation/Segmentation.seg.nrrd", tmp)))
    path = fetch.fetch_openear_member(specimen, r"re:04_reconstruction_microslicing/microslicing[^/]*\.nrrd$", tmp)
    header = nrrd.read_header(str(path))
    print({k: header[k] for k in ("type", "dimension", "space", "sizes", "space directions", "space origin", "encoding") if k in header})
    data, header = nrrd.read(str(path), index_order="F")
print("array", data.shape, data.dtype, f"{data.nbytes / 1e9:.2f} GB")
segs, _, _ = openear.match_segments(found, bc.OPENEAR_PHASE1)
bone = segs["Bone"]
print("segmentation bone origin", bone.origin, "spacing", bone.spacing, "shape", bone.mask.shape)
d = np.asarray(header["space directions"], dtype=float)
rgb_first = d.shape[0] == 4 and not np.isfinite(d[0]).all()
dirs = d[1:] if rgb_first else d
print("colour axis first:", rgb_first, "directions", dirs.tolist())
signs = openear._to_ras_signs(str(header["space"]))
step = np.diag(dirs) * signs
first = np.asarray(header["space origin"], float) * signs
print("RAS step", step, "first", first, "last", first + (np.array(data.shape[-3:]) - 1) * step)


def sample(mask, origin, spacing, n=200000):
    idx = np.argwhere(mask)
    if len(idx) > n:
        idx = idx[np.random.default_rng(0).choice(len(idx), n, replace=False)]
    w = np.asarray(origin) + idx * np.asarray(spacing)
    c = np.rint((w - first) / step).astype(int)
    ok = np.all((c >= 0) & (c < np.array(data.shape[-3:])), axis=1)
    c = c[ok]
    vals = data[:, c[:, 0], c[:, 1], c[:, 2]].T if rgb_first else data[c[:, 0], c[:, 1], c[:, 2]]
    return vals.astype(float), ok.mean()


sp = np.asarray(bone.spacing)
shape = bone.mask.shape
seed = np.zeros(shape, bool)
for o in bc.OSSICLES:
    if o in segs:
        seed |= airspace._place(shape, bone.origin, bone.spacing, segs[o].mask, segs[o].origin)
idx = np.argwhere(seed)
lo = np.maximum(idx.min(0) - 16, 0)
hi = np.minimum(idx.max(0) + 17, shape)
box = tuple(slice(a, b) for a, b in zip(lo, hi))
solid = bone.mask[box].copy()
for n, s in segs.items():
    if n != "Bone":
        solid |= airspace._place(solid.shape, np.asarray(bone.origin) + lo * sp, bone.spacing, s.mask, s.origin)
shell = (ndimage.distance_transform_edt(~seed[box], sampling=sp) <= 0.4) & ~solid
o_box = np.asarray(bone.origin) + lo * sp
for name, m in (("bone label", bone.mask[box]), ("shell around ossicles", shell), ("ossicles", seed[box])):
    v, inside = sample(m, o_box, sp)
    print(f"{name}: inside volume {inside:.2f}; percentiles 5/50/95 per channel:",
          np.percentile(v, [5, 50, 95], axis=0).round(0).tolist())
