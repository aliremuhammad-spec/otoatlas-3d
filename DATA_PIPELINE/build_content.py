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

from otopipe import airspace, fetch, frames, openear, package, scan, split

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
    "Round Window",
)

# Enclosing labels that are shown simplified anyway. In finer specimens (BETA is 0.05 mm)
# they would give tens of millions of triangles, so they are meshed from a copy resampled
# to about 0.125 mm; the error is then measured against that copy, and the manifest says so.
COARSEN = {"Bone", "Sinus Dura"}
COARSEN_BELOW_MM = 0.1
COARSEN_TO_MM = 0.125


def coarsen(mask: np.ndarray, spacing, origin, factor):
    """Resample a binary label by an integer factor per axis: a block is inside when most of its voxels are."""
    f = (factor,) * 3 if isinstance(factor, int) else tuple(int(v) for v in factor)
    if f == (1, 1, 1):
        return mask, tuple(float(s) for s in spacing), tuple(float(o) for o in origin)
    shape = [s // k * k for s, k in zip(mask.shape, f)]
    m = mask[: shape[0], : shape[1], : shape[2]].reshape(
        shape[0] // f[0], f[0], shape[1] // f[1], f[1], shape[2] // f[2], f[2]
    )
    out = m.mean(axis=(1, 3, 5)) >= 0.5
    sp = tuple(float(s) * k for s, k in zip(spacing, f))
    # Block centres sit (k - 1) / 2 voxels in from the first voxel centre.
    org = tuple(float(o) + (k - 1) / 2 * float(s) for o, s, k in zip(origin, spacing, f))
    return out, sp, org


# Sides the dataset does not state, as determined by the reviewer.
OPENEAR_SIDES = {"ZETA": ("right", "Dr. Ali R. Muhammad", "2026-11-17")}


def build_openear(specimen: str, out: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        seg_path = fetch.fetch_openear_member(specimen, "06_Segmentation/Segmentation.seg.nrrd", tmp)
        found = openear.read_segmentation(str(seg_path))
    print(f"{specimen}: segments in file: {sorted(found)}")
    # Specimens spell some names differently ("Facial nerve", "Facial Nerve"); match on
    # letters only, and refuse two file segments that would match one name.
    segments, source_names, unmatched = openear.match_segments(found, OPENEAR_PHASE1)
    if unmatched:
        print(f"{specimen}: segments not used: {unmatched}")
    # A specimen may lack a label; build the rest and record the gap rather than failing.
    missing = sorted(set(OPENEAR_PHASE1) - set(segments))
    if "Scala Tympani" in missing and "Scala Vestibuli" not in missing:
        missing.append("Scala Vestibuli")  # cannot be split without scala tympani
    labels = []
    report = None
    resampled: dict[str, dict] = {}
    for name in OPENEAR_PHASE1:
        if name in missing:
            continue
        seg = segments[name]
        if name in COARSEN and min(seg.spacing) < COARSEN_BELOW_MM:
            # Per axis: BETA is 0.05 x 0.05 x 0.15 mm, so only its first two axes are merged.
            factor = tuple(max(1, round(COARSEN_TO_MM / float(s))) for s in seg.spacing)
            mask, spacing, origin = coarsen(seg.mask, seg.spacing, seg.origin, factor)
            resampled[name] = {
                "from_mm": [round(float(s), 5) for s in seg.spacing],
                "to_mm": [round(float(s), 5) for s in spacing],
                "rule": "majority of each block",
            }
            labels.append(package.LabelInput(name, mask, spacing, origin))
            continue
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
    extra["segment_names_in_file"] = source_names
    if unmatched:
        extra["segments_not_used"] = unmatched
    if resampled:
        extra["labels_resampled"] = resampled
        print(f"{specimen}: resampled before meshing: {resampled}")
    absent_expected = [m for m in missing if m not in openear.OPTIONAL_SEGMENTS]
    if absent_expected:
        extra["labels_not_built"] = absent_expected
        print(f"{specimen}: labels not built: {absent_expected}")
    if report:
        extra["scala_vestibuli_split"] = report
        print("scala vestibuli split:", json.dumps(report))
    air = openear_air(specimen, segments)
    if air is not None:
        labels.append(package.LabelInput(AIR_LABEL, air.mask, air_spacing(segments), air.origin))
        extra["middle_ear_air"] = air.report
    scan_entry = openear_scan(specimen, labels, out)
    if scan_entry:
        extra["scan"] = scan_entry
    side = None
    if specimen.upper() in OPENEAR_SIDES:
        side, by, on = OPENEAR_SIDES[specimen.upper()]
        extra["side_determined_by"] = {"reviewer": by, "date": on}
    return package.build_package(
        out, f"OPENEAR-{specimen.upper()}", "openear", labels, package.load_ontology(ONTOLOGY), side=side, extra=extra,
        publish_shown_only=True,
    )


# Structures that frame the CBCT crop: the middle and inner ear, not the large enclosing labels.
SCAN_FRAME_EXCLUDE = {"Bone", "Sinus Dura", "External Auditory Canal", "Middle Ear Air (derived)"}

AIR_LABEL = "Middle Ear Air (derived)"
OSSICLES = ("Malleus", "Incus", "Stapes")


def _air_factor(spacing) -> tuple[int, int, int]:
    return tuple(max(1, round(COARSEN_TO_MM / float(s))) if float(s) < COARSEN_BELOW_MM else 1 for s in spacing)


def air_spacing(segments: dict) -> tuple[float, float, float]:
    sp = segments["Bone"].spacing
    return tuple(float(s) * k for s, k in zip(sp, _air_factor(sp)))


def openear_air(specimen: str, segments: dict):
    """The middle ear cleft's air (otopipe/airspace.py), or None when it cannot be derived.

    Fine specimens (BETA, DELTA) are worked at about 0.125 mm: every label is resampled
    by the same per-axis factor first (majority of each block)."""
    if "Bone" not in segments or not any(o in segments for o in OSSICLES):
        print(f"{specimen}: warning: no middle ear air space: bone or ossicles missing")
        return None
    try:
        factor = _air_factor(segments["Bone"].spacing)

        def prep(seg):
            return coarsen(seg.mask, seg.spacing, seg.origin, factor)

        bone = prep(segments["Bone"])
        soft = [prep(s) for n, s in segments.items() if n != "Bone"]
        seeds = [prep(segments[o]) for o in OSSICLES if o in segments]
        air = airspace.middle_ear_air(bone, soft, seeds)
        print(f"{specimen}: middle ear air: {json.dumps(air.report)}")
        return air
    except Exception as e:  # noqa: BLE001 - reported; the rest of the package still ships
        print(f"{specimen}: warning: no middle ear air space: {e}")
        return None
SCAN_MARGIN_MM = 3.0


def openear_scan(specimen: str, labels: list, out: Path) -> dict | None:
    """Crop the specimen's registered CBCT around the middle and inner ear. A failure here
    leaves the specimen without a slice view instead of failing the whole package."""
    import nrrd

    try:
        framing = [(l.mask, l.spacing, l.origin) for l in labels if l.source_label not in SCAN_FRAME_EXCLUDE]
        lo, hi = scan.box_around(framing, SCAN_MARGIN_MM)
        with tempfile.TemporaryDirectory() as tmp:
            # Most specimens have CBCT_Embedded and CBCT_Unembedded (any case); the embedded one is
            # registered to the segmentation. ALPHA has a single CBCT file, BETA none.
            try:
                path = fetch.fetch_openear_member(specimen, r"re:05_[^/]*/cbct_embedded[^/]*\.nrrd$", tmp)
            except LookupError:
                path = fetch.fetch_openear_member(specimen, r"re:^[^/]*/?05_[^/]*/[^/]*cbct[^/]*\.nrrd$", tmp)
            data, header = nrrd.read(str(path), index_order="F")
        directions = np.asarray(header["space directions"], dtype=np.float64)
        if np.abs(directions - np.diag(np.diag(directions))).max() > 1e-9:
            raise ValueError("oblique CBCT")
        signs = openear._to_ras_signs(str(header["space"]))
        volume = scan.to_positive_axes(
            data, np.diag(directions) * signs, np.asarray(header["space origin"], dtype=np.float64) * signs
        )
        del data
        cropped = scan.crop(volume, lo, hi)
        entry = scan.write_scan(out, cropped, "CBCT", path.name)
        print(f"{specimen}: scan {entry['shape']} at {entry['spacing_mm']} mm, window {entry['window']}")
        return entry
    except Exception as e:  # noqa: BLE001 - reported and recorded; the meshes still ship
        print(f"{specimen}: warning: no scan packaged: {e}")
        return None


def build_bern(specimen: str, out: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        root = fetch.fetch_bern_specimen(specimen, tmp)
        desc = json.loads((root / f"{specimen}_DESC.json").read_text(encoding="utf-8"))
        image = nib.load(root / "uCT" / f"{specimen}_uCT_LABELS.nii")
        mask = np.asanyarray(image.dataobj) > 0
        affine = image.affine
        raw_files = sorted((root / "uCT").glob("*_uCT_RAW.nii*"))
        raw_image = nib.load(raw_files[0]) if raw_files else None
        raw = np.asanyarray(raw_image.dataobj) if raw_image is not None else None
        raw_affine = raw_image.affine if raw_image is not None else None
    if not np.allclose(affine[:3, :3], np.diag(np.diag(affine[:3, :3]))):
        raise RuntimeError("oblique volumes are not supported")
    spacing = tuple(float(v) for v in np.diag(affine[:3, :3]))
    origin = tuple(float(v) for v in affine[:3, 3])
    frame = frames.cochlear_frame(desc["LANDMARKS"], desc["SIDE"])
    disagreement = frames.max_axis_disagreement(frame, desc["COORD"])
    # Above 0.5 an axis is flipped: stop. Between 0.1 and 0.5 (F05, F06, T02 show 0.10 to 0.16)
    # the axes differ by a few degrees; the frame is recorded with a warning, since nothing
    # shown or measured in the app uses it yet.
    if disagreement > 0.5:
        raise RuntimeError(f"computed cochlear frame disagrees with the descriptor by {disagreement:.2f}: an axis is flipped")
    if disagreement > 0.1:
        print(f"{specimen}: warning: cochlear frame differs from the descriptor by {disagreement:.2f}")
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
    if raw is not None and np.allclose(raw_affine[:3, :3], np.diag(np.diag(raw_affine[:3, :3]))):
        volume = scan.to_positive_axes(raw, np.diag(raw_affine[:3, :3]), raw_affine[:3, 3])
        lo, hi = scan.box_around([(mask, spacing, origin)], 1.5)
        extra["scan"] = scan.write_scan(out, scan.crop(volume, lo, hi), "micro-CT", f"uCT/{raw_files[0].name}")
        print(f"{specimen}: scan {extra['scan']['shape']} at {extra['scan']['spacing_mm']} mm")
    else:
        print(f"{specimen}: warning: no micro-CT image to package")
    return package.build_package(
        out, f"BERN-{specimen}", "bern-labyrinth", labels, package.load_ontology(ONTOLOGY), side=desc["SIDE"].lower(), extra=extra,
        publish_shown_only=True,
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
