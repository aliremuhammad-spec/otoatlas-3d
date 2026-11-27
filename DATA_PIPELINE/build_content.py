"""Build content packages from the open datasets.

    python build_content.py openear ZETA  out/OPENEAR-ZETA
    python build_content.py bern    F01   out/BERN-F01
    python build_content.py index   out

Downloads what it needs from Zenodo (a few megabytes for the Phase 1 structures),
builds measured meshes and writes a package folder. Prints the error table.
"""
from __future__ import annotations

import gc
import json
import resource
import sys
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np

from otopipe import (
    cochlea,
    facialnerve,
    fetch,
    frames,
    membranous,
    openear,
    ossicles,
    package,
    pneumatization,
    scan,
    softtissue,
    split,
    tm,
)

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
    # Counted in 16 bits: a float mean of the whole bone label needs several gigabytes.
    out = m.sum(axis=(1, 3, 5), dtype=np.uint16) * 2 >= int(np.prod(f))
    sp = tuple(float(s) * k for s, k in zip(spacing, f))
    # Block centres sit (k - 1) / 2 voxels in from the first voxel centre.
    org = tuple(float(o) + (k - 1) / 2 * float(s) for o, s, k in zip(origin, spacing, f))
    return out, sp, org


# Sides the dataset does not state, as determined by the reviewer.
OPENEAR_SIDES = {"ZETA": ("right", "Dr. Ali R. Muhammad", "2026-11-17")}


def peak_memory_gb() -> float:
    """Peak resident memory of this process so far (Linux reports kilobytes)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576


def build_openear(specimen: str, out: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        seg_path = fetch.fetch_openear_member(specimen, "06_Segmentation/Segmentation.seg.nrrd", tmp)
        names = openear.segment_names(str(seg_path))
        # Only the labels used are read: DELTA's unused ones took its runner to its 16 GB limit.
        found = openear.read_segmentation(str(seg_path), OPENEAR_PHASE1)
    print(f"{specimen}: segments in file: {sorted(names)}")
    # Specimens spell some names differently ("Facial nerve", "Facial Nerve"); match on
    # letters only, and refuse two file segments that would match one name.
    segments, source_names, _ = openear.match_segments(found, OPENEAR_PHASE1)
    unmatched = sorted(set(names) - set(source_names.values()))
    del found
    print(f"{specimen}: peak memory after reading the labels: {peak_memory_gb():.1f} GB", flush=True)
    if unmatched:
        print(f"{specimen}: segments not used: {unmatched}")
    # A specimen may lack a label; build the rest and record the gap rather than failing.
    missing = sorted(set(OPENEAR_PHASE1) - set(segments))
    if "Scala Tympani" in missing and "Scala Vestibuli" not in missing:
        missing.append("Scala Vestibuli")  # cannot be split without scala tympani
    labels = []
    report = None
    resampled: dict[str, dict] = {}
    vestibule_centre = None
    vestibular = None
    extra_tm: dict = {}
    for name in OPENEAR_PHASE1:
        if name in missing or name == "Tympanic Membrane" or name in OSSICLES:
            continue  # the membrane and the ossicles are added below, divided into parts when possible
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
            # Only the merged copy is needed from here on; the full-resolution one is the
            # largest array of a fine specimen (DELTA's runner ran out of memory with both).
            segments[name] = openear.Segment(name, mask, spacing, origin)
            del seg
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
        vestibule_centre = centroid(parts.vestibular.mask, seg.spacing, parts.vestibular.origin)
        vestibular = (parts.vestibular.mask, seg.spacing, parts.vestibular.origin)
    if "Tympanic Membrane" not in missing:
        labels.extend(tympanic_membrane(specimen, segments, vestibule_centre, extra_tm))
    ossicle_report: dict = {}
    ossicle_measurements: list = []
    labels.extend(ossicle_labels(specimen, segments, missing, vestibular, vestibule_centre, ossicle_report, ossicle_measurements))
    extra = {"frame": "Dataset frame of the segmentation file (right-anterior-superior), millimetres."}
    if "Tympanic Membrane" not in missing and extra_tm:
        extra["tympanic_membrane_quadrants"] = extra_tm
        quads = [f"tympanic_membrane_{q}" for q in tm.QUADRANTS]
        extra["measurements"] = [
            {"id": "tm_vertical_diameter", "value_mm": extra_tm["vertical_diameter_mm"], "structures": quads,
             "method": "extent of the membrane label along the malleus handle"},
            {"id": "tm_horizontal_diameter", "value_mm": extra_tm["horizontal_diameter_mm"], "structures": quads,
             "method": "extent of the membrane label at right angles to the handle"},
        ]
    frame = ossicle_report.pop("_frame", None)
    short_tip = ossicle_report.pop("_short_process_tip", None)
    ossicle_parts = ossicle_report.pop("_parts", {})
    if frame is not None:
        extra["anatomical_frame"] = {
            "lateral": [round(float(v), 5) for v in frame.lateral],
            "anterior": [round(float(v), 5) for v in frame.anterior],
            "superior": [round(float(v), 5) for v in frame.superior],
            "basis": "lateral: vestibule to membrane; superior: malleus long axis; anterior: towards the cochlea (otopipe/ossicles.py)",
        }
    if ossicle_report:
        extra["ossicle_parts"] = ossicle_report
    if frame is not None:
        facial_nerve_parts(specimen, labels, frame, extra)
    if frame is not None and vestibular is not None and not {"Scala Tympani", "Scala Vestibuli"} & set(missing):
        lab_of = {n: (segments[n].mask, segments[n].spacing, segments[n].origin) for n in ("Scala Tympani", "Scala Vestibuli")}
        mem = membranous.build(lab_of["Scala Tympani"], lab_of["Scala Vestibuli"], vestibular, frame)
        for part, (mask, origin) in mem.parts.items():
            labels.append(package.LabelInput(MEMBRANOUS_LABEL, mask, (membranous.GRID_MM,) * 3, origin, part=part))
        extra["membranous_labyrinth"] = mem.report
        width, _ = membranous.vestibule_width(vestibular)
        extra["measurements"] = extra.get("measurements", []) + [
            {"id": "vestibule_width", "value_mm": round(width, 2), "structures": ["vestibule_and_semicircular_canals"],
             "method": "diameter of the largest sphere that fits in the vestibular label"}
        ]
        print(f"{specimen}: membranous labyrinth (schematic): {json.dumps(mem.report)}")
        if ossicle_parts and "Facial Nerve" in segments:
            fn = segments["Facial Nerve"]
            bone = next(l for l in labels if l.source_label == "Bone" and l.part is None)
            labyrinth = np.vstack([ossicles.points(lab_of[n]) for n in lab_of])
            soft = softtissue.build(
                {k: v[0] for k, v in ossicle_parts.items()},
                {k: v[1] for k, v in ossicle_parts.items()},
                (fn.mask, fn.spacing, fn.origin),
                (bone.mask, bone.spacing, bone.origin),
                frame,
                labyrinth,
                membrane=(
                    (segments["Tympanic Membrane"].mask, segments["Tympanic Membrane"].spacing, segments["Tympanic Membrane"].origin)
                    if "Tympanic Membrane" in segments
                    else None
                ),
                cochlea_points=ossicles.points(lab_of["Scala Tympani"]),
            )
            for part, (mask, origin) in soft.parts.items():
                if mask.any():
                    labels.append(package.LabelInput(SOFT_TISSUE_LABEL, mask, (softtissue.GRID_MM,) * 3, origin, part=part))
            extra["muscles_and_ligaments"] = soft.report
            print(f"{specimen}: muscles and ligaments (schematic): {json.dumps(soft.report)}")
    if ossicle_measurements:
        extra["measurements"] = extra.get("measurements", []) + ossicle_measurements
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
    cbct = load_openear_cbct(specimen)
    air = openear_air_spaces(specimen, segments, labels, cbct)
    if air is not None:
        grid = (pneumatization.GRID_MM,) * 3
        cells = air.cells
        air_report = dict(air.report)
        measurements = [
            {"id": "tympanic_cavity_volume", "value_ml": air.report["tympanic_cavity_ml"], "structures": ["middle_ear_air_space"],
             "method": "computed air space within 4 mm of the ossicles and membrane"},
        ]
        if short_tip is not None:
            try:
                antrum, cells, antrum_report = pneumatization.split_antrum(cells, short_tip)
                air_report.update(antrum_report)
                labels.append(package.LabelInput(AIR_LABEL, antrum[0], grid, antrum[1], part="antrum"))
                measurements.append({"id": "antrum_volume", "value_ml": antrum_report["antrum_ml"], "structures": ["mastoid_antrum"],
                                     "method": "largest cavity within 6 mm of the incus short process, after opening the cells with a 1 mm ball"})
                print(f"{specimen}: antrum: {json.dumps(antrum_report)}")
            except ValueError as e:
                print(f"{specimen}: warning: no antrum: {e}")
        cells_ml = round(float(cells[0].sum()) * pneumatization.GRID_MM**3 / 1000.0, 2)
        labels.append(package.LabelInput(AIR_LABEL, air.tympanic[0], grid, air.tympanic[1], part="tympanic"))
        labels.append(package.LabelInput(AIR_LABEL, cells[0], grid, cells[1], part="cells"))
        measurements.append({"id": "air_cells_volume", "value_ml": cells_ml, "structures": ["temporal_bone_air_cells"],
                             "method": "the rest of the computed air space, inside the cut specimen block"})
        extra["air_spaces"] = air_report
        extra["measurements"] = extra.get("measurements", []) + measurements
    print(f"{specimen}: peak memory before the scan: {peak_memory_gb():.1f} GB", flush=True)
    scan_entry = openear_scan(specimen, labels, out, cbct)
    del cbct
    # Meshing is the most memory-hungry step; nothing but the labels is needed for it.
    segments.clear()
    gc.collect()
    print(f"{specimen}: peak memory before meshing: {peak_memory_gb():.1f} GB", flush=True)
    if scan_entry:
        extra["scan"] = scan_entry
    side = None
    if specimen.upper() in OPENEAR_SIDES:
        side, by, on = OPENEAR_SIDES[specimen.upper()]
        extra["side_determined_by"] = {"reviewer": by, "date": on}
    manifest = package.build_package(
        out, f"OPENEAR-{specimen.upper()}", "openear", labels, package.load_ontology(ONTOLOGY), side=side, extra=extra,
        publish_shown_only=True, label_volume=True,
    )
    print(f"{specimen}: peak memory after meshing: {peak_memory_gb():.1f} GB", flush=True)
    return manifest


# Structures that frame the CBCT crop: the middle and inner ear, not the large enclosing labels.
SCAN_FRAME_EXCLUDE = {"Bone", "Sinus Dura", "External Auditory Canal", "Air Spaces (computed)"}

def centroid(mask, spacing, origin) -> np.ndarray:
    return np.asarray(origin) + np.argwhere(mask).mean(axis=0) * np.asarray(spacing)


def tympanic_membrane(specimen: str, segments: dict, vestibule_centre, report_out: dict) -> list:
    """The membrane as four quadrants (otopipe/tm.py), or whole when they cannot be computed."""
    seg = segments["Tympanic Membrane"]
    try:
        if "Malleus" not in segments or "Scala Tympani" not in segments or vestibule_centre is None:
            raise ValueError("malleus, scala tympani or vestibule missing")
        st = segments["Scala Tympani"]
        q = tm.tympanic_quadrants(
            (seg.mask, seg.spacing, seg.origin),
            (segments["Malleus"].mask, segments["Malleus"].spacing, segments["Malleus"].origin),
            centroid(st.mask, st.spacing, st.origin),
            vestibule_centre,
        )
        report_out.update(q.report)
        print(f"{specimen}: tympanic membrane quadrants: {json.dumps(q.report)}")
        return [
            package.LabelInput("Tympanic Membrane", mask, seg.spacing, origin, part=name)
            for name, (mask, origin) in q.parts.items()
        ]
    except Exception as e:  # noqa: BLE001 - the whole membrane still ships
        print(f"{specimen}: warning: tympanic membrane kept whole: {e}")
        return [package.LabelInput("Tympanic Membrane", seg.mask, seg.spacing, seg.origin)]


def ossicle_labels(specimen, segments, missing, vestibular, vestibule_centre, report_out: dict, measurements_out: list) -> list:
    """Each ossicle divided into its parts (otopipe/ossicles.py), or whole when a rule fails for it."""
    present = [n for n in OSSICLES if n not in missing]
    whole = {n: package.LabelInput(n, segments[n].mask, segments[n].spacing, segments[n].origin) for n in present}

    def lab(name):
        g = segments[name]
        return (g.mask, g.spacing, g.origin)

    try:
        need = {"Malleus", "Incus", "Stapes", "Tympanic Membrane", "Scala Tympani"}
        if need & set(missing) or vestibular is None:
            raise ValueError("ossicles, membrane, scala tympani or vestibule missing")
        st = segments["Scala Tympani"]
        frame = ossicles.anatomical_frame(
            vestibule_centre, centroid(st.mask, st.spacing, st.origin), lab("Tympanic Membrane"), lab("Malleus")
        )
        report_out["side_from_anatomy"] = frame.side
        report_out["_frame"] = frame
        incus_pts = ossicles.points(lab("Incus"))
        report_out["_short_process_tip"] = incus_pts[np.argmin((incus_pts - frame.umbo) @ frame.anterior)]
        print(f"{specimen}: side from the labels' anatomy: {frame.side}")
    except Exception as e:  # noqa: BLE001 - the whole bones still ship
        print(f"{specimen}: warning: ossicles kept whole: {e}")
        return list(whole.values())
    rules = {
        "Malleus": lambda: ossicles.malleus_parts(lab("Malleus"), lab("Tympanic Membrane"), lab("Incus"), frame),
        "Incus": lambda: ossicles.incus_parts(lab("Incus"), lab("Stapes"), frame),
        "Stapes": lambda: ossicles.stapes_parts(lab("Stapes"), lab("Incus"), vestibular, frame),
    }
    out = []
    for name in present:
        try:
            result = rules[name]()
        except Exception as e:  # noqa: BLE001
            print(f"{specimen}: warning: {name.lower()} kept whole: {e}")
            report_out[name.lower()] = {"divided": False, "reason": str(e)}
            out.append(whole[name])
            continue
        seg = segments[name]
        report_out.setdefault("_parts", {})[name.lower()] = (result.parts, seg.spacing)
        report_out[name.lower()] = {"divided": True, **result.report}
        print(f"{specimen}: {name.lower()} parts: {json.dumps(result.report)}")
        ids = [f"{name.lower()}_{p}" for p in result.parts]
        out.extend(package.LabelInput(name, mask, seg.spacing, origin, part=p) for p, (mask, origin) in result.parts.items())
        r = result.report
        if name == "Malleus":
            measurements_out.append({"id": "malleus_length", "value_mm": r["length_mm"], "structures": ids,
                                     "method": "extent of the malleus label along its long axis"})
        if name == "Stapes":
            measurements_out.append({"id": "stapes_footplate_length", "value_mm": r["footplate_length_mm"],
                                     "structures": ["stapes_footplate"], "method": "extent of the footplate part along its long axis"})
            measurements_out.append({"id": "stapes_footplate_width", "value_mm": r["footplate_width_mm"],
                                     "structures": ["stapes_footplate"], "method": "extent of the footplate part across its long axis"})
    return out


def facial_nerve_parts(specimen, labels: list, frame, extra: dict) -> None:
    """The facial nerve divided at the second genu (otopipe/facialnerve.py), in place of the whole label."""
    whole = next((l for l in labels if l.source_label == "Facial Nerve" and l.part is None), None)
    if whole is None:
        return
    try:
        division = facialnerve.divide((whole.mask, whole.spacing, whole.origin), frame)
    except ValueError as e:
        print(f"{specimen}: warning: facial nerve kept whole: {e}")
        extra["facial_nerve_division"] = {"divided": False, "reason": str(e)}
        return
    labels.remove(whole)
    labels.extend(package.LabelInput("Facial Nerve", mask, whole.spacing, origin, part=p) for p, (mask, origin) in division.parts.items())
    extra["facial_nerve_division"] = {"divided": True, **division.report}
    extra["measurements"] = extra.get("measurements", []) + [
        {"id": "facial_mastoid_segment_length", "value_mm": division.report["mastoid_segment_mm"],
         "structures": ["facial_nerve_mastoid"],
         "method": "length of the label's centreline from the second genu (by rule) to the label's lower end"}
    ]
    print(f"{specimen}: facial nerve divided: {json.dumps(division.report)}")


AIR_LABEL = "Air Spaces (computed)"
MEMBRANOUS_LABEL = "Membranous Labyrinth (schematic)"
SOFT_TISSUE_LABEL = "Muscles and Ligaments (schematic)"
OSSICLES = ("Malleus", "Incus", "Stapes")
AIR_WALLS = ("External Auditory Canal", "Scala Tympani", "Scala Vestibuli", "Carotis Interna", "Facial Nerve", "Chorda Tympani",
             "Cochleovestibular nerve")


def openear_air_spaces(specimen: str, segments: dict, labels: list, cbct):
    """Tympanic cavity and air cells (otopipe/pneumatization.py), or None when they cannot be computed."""
    if cbct is None or "Bone" not in segments:
        print(f"{specimen}: warning: no air spaces: needs the bone label and a registered CBCT")
        return None
    try:
        # The bone and the sinus as meshed, already merged to 0.125 mm on the finest specimens.
        by_label = {l.source_label: l for l in labels if l.part is None}
        bone = by_label["Bone"]
        others = [(segments[n].mask, segments[n].spacing, segments[n].origin) for n in AIR_WALLS if n in segments]
        if "Sinus Dura" in by_label:
            sd = by_label["Sinus Dura"]
            others.append((sd.mask, sd.spacing, sd.origin))
        anchors = [(segments[n].mask, segments[n].spacing, segments[n].origin)
                   for n in (*OSSICLES, "Tympanic Membrane") if n in segments]
        volume, _ = cbct
        lo, hi = scan.box_around([(bone.mask, bone.spacing, bone.origin)], 1.0)
        sub = scan.crop(volume, lo, hi)
        u8, _, _ = scan.window(sub.data)
        air = pneumatization.air_spaces((bone.mask, bone.spacing, bone.origin), others, anchors, (u8, sub.spacing, sub.origin))
        print(f"{specimen}: air spaces: {json.dumps(air.report)}")
        return air
    except Exception as e:  # noqa: BLE001 - reported; the rest of the package still ships
        print(f"{specimen}: warning: no air spaces: {e}")
        return None


SCAN_MARGIN_MM = 3.0


def load_openear_cbct(specimen: str):
    """The specimen's registered CBCT with axes running in the positive RAS directions,
    or None when the archive has none (BETA) or it cannot be read."""
    import nrrd

    try:
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
        return volume, path.name
    except Exception as e:  # noqa: BLE001 - reported; the meshes still ship
        print(f"{specimen}: warning: no CBCT: {e}")
        return None


def openear_scan(specimen: str, labels: list, out: Path, cbct) -> dict | None:
    """Crop the specimen's registered CBCT around the middle and inner ear. A failure here
    leaves the specimen without a slice view instead of failing the whole package."""
    if cbct is None:
        return None
    volume, name = cbct
    try:
        framing = [(l.mask, l.spacing, l.origin) for l in labels if l.source_label not in SCAN_FRAME_EXCLUDE]
        lo, hi = scan.box_around(framing, SCAN_MARGIN_MM)
        entry = scan.write_scan(out, scan.crop(volume, lo, hi), "CBCT", name)
        print(f"{specimen}: scan {entry['shape']} at {entry['spacing_mm']} mm, window {entry['window']}")
        return entry
    except Exception as e:  # noqa: BLE001
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
    try:
        ab = cochlea.a_and_b(mask, spacing, origin, frame.origin, frame.z, desc["LANDMARKS"]["RW"])
        # A value outside a plausible adult range means the line missed the turn; do not ship it.
        # F05's B came out at 2.6 mm on the first run.
        bounds = {"cochlear_a_value": (7.0, 11.5), "cochlear_b_value": (5.0, 9.0)}
        kept = [k for k, (lo, hi) in bounds.items() if lo <= ab[k] <= hi]
        for k in set(bounds) - set(kept):
            print(f"{specimen}: warning: {k} {ab[k]} mm is outside {bounds[k]} and is not shipped")
        extra["measurements"] = [
            {"id": key, "value_mm": ab[key], "structures": ["bony_labyrinth"], "method": ab["method"]}
            for key in kept
        ]
        print(f"{specimen}: A {ab['cochlear_a_value']} mm, B {ab['cochlear_b_value']} mm")
    except Exception as e:  # noqa: BLE001
        print(f"{specimen}: warning: no A and B values: {e}")
    # Vestibule width: the widest place in the labyrinth, if it lies away from the cochlear axis.
    width, at = membranous.vestibule_width((mask, spacing, origin))
    rel = at - frame.origin
    off_axis = float(np.linalg.norm(rel - (rel @ frame.z) * frame.z))
    if off_axis > 3.0 and 2.0 <= width <= 4.5:
        extra.setdefault("measurements", []).append(
            {"id": "vestibule_width", "value_mm": round(width, 2), "structures": ["bony_labyrinth"],
             "method": "diameter of the largest sphere that fits in the labyrinth (it lies in the vestibule)"}
        )
        print(f"{specimen}: vestibule width {width:.2f} mm, {off_axis:.1f} mm from the cochlear axis")
    else:
        print(f"{specimen}: warning: widest place {width:.2f} mm, {off_axis:.1f} mm from the cochlear axis: not shipped")
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
