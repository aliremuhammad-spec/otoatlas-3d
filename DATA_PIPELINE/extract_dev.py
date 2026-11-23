"""Development extract: the ossicles and their neighbours from one OpenEar specimen, as
bit-packed masks in one .npz, for working on ossicle parts outside CI.

    python extract_dev.py ZETA out_dir

Derived from OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

from otopipe import fetch, openear

WANTED = (
    "Malleus",
    "Incus",
    "Stapes",
    "Tympanic Membrane",
    "Facial Nerve",
    "Chorda Tympani",
    "Scala Tympani",
    "Scala Vestibuli",
    "Cochleovestibular nerve",
    "External Auditory Canal",
)


def main(specimen: str, out_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = fetch.fetch_openear_member(specimen, "06_Segmentation/Segmentation.seg.nrrd", tmp)
        found = openear.read_segmentation(str(path))
    segments, sources, _ = openear.match_segments(found, WANTED)
    arrays = {}
    for name, seg in segments.items():
        key = name.lower().replace(" ", "_")
        arrays[f"{key}__bits"] = np.packbits(seg.mask.ravel())
        arrays[f"{key}__shape"] = np.array(seg.mask.shape)
        arrays[f"{key}__spacing"] = np.array(seg.spacing)
        arrays[f"{key}__origin"] = np.array(seg.origin)
        print(f"{specimen}: {name} ({sources[name]}) {seg.mask.shape} at {seg.spacing}, {int(seg.mask.sum())} voxels")
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / f"{specimen}.npz", **arrays)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
