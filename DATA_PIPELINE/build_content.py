"""Build content packages from the open datasets.

    python build_content.py openear ZETA  out/OPENEAR-ZETA
    python build_content.py bern    F01   out/BERN-F01
    python build_content.py index   out

Downloads what it needs from Zenodo (a few megabytes for the Phase 1 structures),
builds measured meshes and writes a package folder. Prints the error table.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np

from otopipe import fetch, frames, openear, package, split

ONTOLOGY = Path(__file__).resolve().parent.parent / "ontology" / "structures.json"

# Every OpenEar label is built.
OPENEAR_PHASE1 = (
    "Scala Tympani",
    "Scala Vestibuli",
    "Malleus",
    "Incus",
    "Stapes",
    "Facial Nerve",
    "Chorda Tympani",
    "Cochleovestibular nerve",
    "Tympanic Membrane",
    "Carotis Interna",
    "Bone",
    "External Auditory Canal",
    "Sinus Dura",
)

# Sides the dataset does not state, as determined by the reviewer.
OPENEAR_SIDES = {"ZETA": ("right", "Dr. Ali R. Muhammad", "2026-11-17")}


def build_openear(specimen: str, out: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        seg_path = fetch.fetch_openear_member(specimen, "06_Segmentation/Segmentation.seg.nrrd", tmp)
        segments = openear.read_segmentation(str(seg_path))
    missing = set(openear.EXPECTED_SEGMENTS) - set(segments)
    if missing:
        raise RuntimeError(f"segments missing from {specimen}: {sorted(missing)}")
    labels = []
    report = None
    for name in OPENEAR_PHASE1:
        seg = segments[name]
        if name != "Scala Vestibuli":
            labels.append(package.LabelInput(name, seg.mask, seg.spacing, seg.origin))
            continue
        # The label also holds the vestibule and canals; split them off (see otopipe/split.py).
        st = segments["Scala Tympani"]
        if not np.allclose(seg.spacing, st.spacing):
            raise RuntimeError("scala tympani and scala vestibuli are on different grids")
        parts = split.split_by_reach(seg.mask, seg.origin, st.mask, st.origin, seg.spacing)
        report = parts.report
        labels.append(package.LabelInput(name, parts.cochlear.mask, seg.spacing, parts.cochlear.origin, part="cochlear"))
        labels.append(package.LabelInput(name, parts.vestibular.mask, seg.spacing, parts.vestibular.origin, part="vestibular"))
    extra = {"frame": "Dataset frame of the segmentation file (right-anterior-superior), millimetres."}
    if report:
        extra["scala_vestibuli_split"] = report
        print("scala vestibuli split:", json.dumps(report))
    side = None
    if specimen.upper() in OPENEAR_SIDES:
        side, by, on = OPENEAR_SIDES[specimen.upper()]
        extra["side_determined_by"] = {"reviewer": by, "date": on}
    return package.build_package(
        out, f"OPENEAR-{specimen.upper()}", "openear", labels, package.load_ontology(ONTOLOGY), side=side, extra=extra
    )


def build_bern(specimen: str, out: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = fetch.fetch_bern_specimen(specimen, tmp)
        desc = json.loads((root / f"{specimen}_DESC.json").read_text(encoding="utf-8"))
        image = nib.load(root / "uCT" / f"{specimen}_uCT_LABELS.nii")
        mask = np.asanyarray(image.dataobj) > 0
        affine = image.affine
    if not np.allclose(affine[:3, :3], np.diag(np.diag(affine[:3, :3]))):
        raise RuntimeError("oblique volumes are not supported")
    spacing = tuple(float(v) for v in np.diag(affine[:3, :3]))
    origin = tuple(float(v) for v in affine[:3, 3])
    frame = frames.cochlear_frame(desc["LANDMARKS"], desc["SIDE"])
    disagreement = frames.max_axis_disagreement(frame, desc["COORD"])
    if disagreement > 0.1:
        raise RuntimeError(f"computed cochlear frame disagrees with the descriptor by {disagreement:.2f}")
    extra = {
        "frame": "Scanner frame of the dataset's NIfTI files, millimetres.",
        "landmarks_mm": desc["LANDMARKS"],
        "cochlear_frame": {
            "origin": frame.origin.tolist(),
            "x": frame.x.tolist(),
            "y": frame.y.tolist(),
            "z": frame.z.tolist(),
            "max_disagreement_with_descriptor": round(disagreement, 4),
        },
    }
    labels = [package.LabelInput("bony labyrinth (single label)", mask, spacing, origin)]
    return package.build_package(
        out, f"BERN-{specimen}", "bern-labyrinth", labels, package.load_ontology(ONTOLOGY), side=desc["SIDE"].lower(), extra=extra
    )


def write_index(root: Path) -> list[dict]:
    """Write `index.json` listing every package folder under `root`."""
    specimens = []
    for manifest_path in sorted(root.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        specimens.append({"id": manifest["specimen_id"], "path": manifest_path.parent.name})
    (root / "index.json").write_text(json.dumps({"specimens": specimens}, indent=2), encoding="utf-8")
    return specimens


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "index":
        for entry in write_index(Path(argv[2])):
            print("indexed", entry["id"])
        return 0
    if len(argv) != 4 or argv[1] not in ("openear", "bern"):
        print(__doc__)
        return 2
    manifest = (build_openear if argv[1] == "openear" else build_bern)(argv[2], Path(argv[3]))
    print(f"{manifest['specimen_id']}  side={manifest['side']}")
    print(f"{'structure':28} {'voxel':>6} {'limit':>6} {'LOD':>3} {'tris':>8} {'hausdorff':>9} {'p95':>7} ok")
    for s in manifest["structures"]:
        for lod in s["lods"]:
            print(
                f"{s['id']:28} {s['source_voxel_mm'][0]:6.4f} {s['mesh_error_limit_mm']:6.2f} {lod['level']:3d} "
                f"{lod['triangles']:8d} {lod['hausdorff_mm']:9.4f} {lod['p95_mm']:7.4f} {'yes' if lod['within_limit'] else 'NO'}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
