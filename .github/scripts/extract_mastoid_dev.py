"""Development extract for the mastoid work: the bone, its neighbours and the registered CBCT
of one OpenEar specimen, cropped to the bone, saved as one .npz (labels bit-packed, CBCT
windowed to 8 bits). Lives outside DATA_PIPELINE so editing it does not rebuild content.

    python extract_mastoid_dev.py ZETA out_dir

Derived from OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "DATA_PIPELINE"))
import build_content  # noqa: E402
from otopipe import fetch, openear, scan  # noqa: E402

WANTED = (
    "Bone",
    "Sinus Dura",
    "External Auditory Canal",
    "Facial Nerve",
    "Scala Tympani",
    "Scala Vestibuli",
    "Tympanic Membrane",
    "Malleus",
    "Incus",
    "Stapes",
    "Carotis Interna",
)


def main(specimen: str, out_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = fetch.fetch_openear_member(specimen, "06_Segmentation/Segmentation.seg.nrrd", tmp)
        found = openear.read_segmentation(str(path))
    segments, _, _ = openear.match_segments(found, WANTED)
    arrays = {}
    for name, seg in segments.items():
        key = name.lower().replace(" ", "_")
        arrays[f"{key}__bits"] = np.packbits(seg.mask.ravel())
        arrays[f"{key}__shape"] = np.array(seg.mask.shape)
        arrays[f"{key}__spacing"] = np.array(seg.spacing)
        arrays[f"{key}__origin"] = np.array(seg.origin)
        print(f"{specimen}: {name} {seg.mask.shape} at {seg.spacing}, {int(seg.mask.sum())} voxels", flush=True)
    del found
    cbct = build_content.load_openear_cbct(specimen)
    if cbct is not None and "Bone" in segments:
        volume, name = cbct
        b = segments["Bone"]
        lo, hi = scan.box_around([(b.mask, b.spacing, b.origin)], 1.0)
        sub = scan.crop(volume, lo, hi)
        u8, low, high = scan.window(sub.data)
        arrays["cbct__u8"] = u8
        arrays["cbct__spacing"] = np.array(sub.spacing)
        arrays["cbct__origin"] = np.array(sub.origin)
        arrays["cbct__window"] = np.array([low, high])
        print(f"{specimen}: CBCT {name} cropped to {u8.shape} at {sub.spacing}, window {low:.0f}..{high:.0f}")
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / f"{specimen}.npz", **arrays)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
