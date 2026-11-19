"""One-off check: CBCT values in the middle ear of an OpenEar specimen, embedded vs unembedded.

Prints percentiles of each registered CBCT in two places: the empty shell right around the
ossicles (surely the tympanic cavity) and every empty voxel the envelope encloses.
"""
import sys
import tempfile

import nrrd
import numpy as np
from scipy import ndimage

sys.path.insert(0, "DATA_PIPELINE")
import build_content as bc  # noqa: E402
from otopipe import airspace, fetch, openear, scan  # noqa: E402

specimen = sys.argv[1]
with tempfile.TemporaryDirectory() as tmp:
    found = openear.read_segmentation(str(fetch.fetch_openear_member(specimen, "06_Segmentation/Segmentation.seg.nrrd", tmp)))
segs, _, _ = openear.match_segments(found, bc.OPENEAR_PHASE1)
bone = segs["Bone"]
sp = np.asarray(bone.spacing)
soft = [(s.mask, s.spacing, s.origin) for n, s in segs.items() if n != "Bone"]
seed = [(segs[o].mask, segs[o].spacing, segs[o].origin) for o in bc.OSSICLES if o in segs]
shape = bone.mask.shape
solid = bone.mask.copy()
for m, s, o in soft:
    solid |= airspace._place(shape, bone.origin, bone.spacing, m, o)
seedm = np.zeros(shape, bool)
for m, s, o in seed:
    seedm |= airspace._place(shape, bone.origin, bone.spacing, m, o)
idx = np.argwhere(seedm)
lo = np.maximum(idx.min(0) - 40, 0); hi = np.minimum(idx.max(0) + 41, shape)
box = tuple(slice(a, b) for a, b in zip(lo, hi))
shell = (ndimage.distance_transform_edt(~seedm[box], sampling=sp) <= 0.5) & ~solid[box]
print("shell voxels", int(shell.sum()))
for pattern in (r"re:05_[^/]*/cbct_embedded[^/]*\.nrrd$", r"re:05_[^/]*/cbct_unembedded[^/]*\.nrrd$"):
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = fetch.fetch_openear_member(specimen, pattern, tmp)
            data, header = nrrd.read(str(path), index_order="F")
    except Exception as e:
        print(pattern, "missing:", e)
        continue
    d = np.asarray(header["space directions"], float)
    signs = openear._to_ras_signs(str(header["space"]))
    vol = scan.to_positive_axes(data, np.diag(d) * signs, np.asarray(header["space origin"], float) * signs)

    def sample(mask, origin):
        w = np.asarray(origin) + np.argwhere(mask) * sp
        c = np.rint((w - np.asarray(vol.origin)) / np.asarray(vol.spacing)).astype(int)
        ok = np.all((c >= 0) & (c < vol.data.shape), axis=1)
        c = c[ok]
        return vol.data[c[:, 0], c[:, 1], c[:, 2]].astype(float)

    o_box = np.asarray(bone.origin) + lo * sp
    s_vals = sample(shell, o_box)
    b_vals = sample(bone.mask[box][::3, ::3, ::3], o_box)
    print(path.name, "spacing", vol.spacing)
    print("  around ossicles:", np.percentile(s_vals, [5, 25, 50, 75, 95]).round(0))
    print("  bone:           ", np.percentile(b_vals, [5, 25, 50, 75, 95]).round(0))
    print("  whole crop:     ", np.percentile(vol.data[::4, ::4, ::4], [1, 5, 25, 50, 75, 95]).round(0))
