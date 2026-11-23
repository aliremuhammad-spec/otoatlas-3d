"""Build a content package: measured meshes plus a manifest the app can trust.

A package is a folder with one `manifest.json` and one binary glTF file per
structure and level of detail. The manifest records, for every mesh, how far it
lies from its label surface, so the app can show the figure and refuse to measure
on a level that exceeds the limit.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from . import mesh as M

PIPELINE_VERSION = "0.1.0"
MANIFEST_SCHEMA = 1
# The app shows the full-resolution mesh when it has at most this many triangles;
# larger structures (the temporal bone, the sinus-and-dura label) are shown at the
# finest level under the budget, and are not measured on unless that level is within its limit.
DISPLAY_TRIANGLE_BUDGET = 1_000_000


def display_level(lods: list[dict]) -> int:
    """The finest level whose triangle count fits the display budget (the coarsest level if none does)."""
    for lod in lods:
        if lod["triangles"] <= DISPLAY_TRIANGLE_BUDGET:
            return int(lod["level"])
    return int(lods[-1]["level"])


@dataclass(frozen=True)
class LabelInput:
    """One binary label ready for meshing, in the specimen frame."""

    source_label: str
    mask: np.ndarray
    spacing: tuple[float, float, float]
    origin: tuple[float, float, float]
    part: str | None = None  # set when one dataset label is split into several structures


def load_ontology(path: str | Path) -> dict:
    """The ontology, with the descriptions from `descriptions.json` beside it attached to each structure."""
    path = Path(path)
    ontology = json.loads(path.read_text(encoding="utf-8"))
    extra = path.with_name("descriptions.json")
    if extra.exists():
        texts = json.loads(extra.read_text(encoding="utf-8"))["descriptions"]
        for s in ontology["structures"]:
            if s["id"] in texts:
                # Every description is a draft until the reviewer approves it in that file.
                s["description"] = {"status": "draft", **texts[s["id"]]}
    return ontology


def group_of(ontology: dict, entry: dict) -> dict | None:
    """For a part of another structure (a membrane quadrant, a part of a bone), that structure's id and names."""
    parent = entry.get("parent")
    for s in ontology["structures"]:
        if s["id"] == parent:
            return {"id": s["id"], "names": {"en": s["name_en"], "ar": s["name_ar"], "latin": s["name_ta_latin"]}}
    return None


def structure_for(ontology: dict, dataset: str, source_label: str, part: str | None = None) -> dict:
    """The ontology entry that a dataset label (or one part of it) maps to. Unknown labels are an error, never skipped."""
    for s in ontology["structures"]:
        for src in s["sources"]:
            if src["dataset"] == dataset and src["label"] == source_label and src.get("part") == part:
                return s
    where = f" (part {part!r})" if part else ""
    raise KeyError(f"label {source_label!r}{where} of dataset {dataset!r} is not in the ontology")


def build_package(
    out_dir: str | Path,
    specimen_id: str,
    dataset: str,
    labels: list[LabelInput],
    ontology: dict,
    side: str | None = None,
    extra: dict | None = None,
    synthetic: bool = False,
    keep_fractions: tuple[float, ...] = (1.0, 0.25, 0.1),
    samples: int = 20000,
    publish_shown_only: bool = False,
) -> dict:
    """Mesh every label, measure it, write the files, and return the manifest.

    Every level is built and measured. With `publish_shown_only`, only the level the
    app shows is kept on disk; the others stay in the manifest with their measured
    error and `"published": false`. That keeps eight OpenEar specimens under the
    hosting size limit (a full-resolution temporal bone alone is about 130 MB).
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    structures = []
    for label in labels:
        entry = structure_for(ontology, dataset, label.source_label, label.part)
        limit = float(entry["mesh_error_limit_mm"])
        build = M.build_lods(
            label.mask, label.spacing, label.origin, limit_mm=limit, keep_fractions=keep_fractions, samples=samples
        )
        lods = []
        for lod in build.lods:
            file_name = f"{entry['id']}.lod{lod.level}.glb"
            lod.mesh.export(out / file_name, file_type="glb")
            lods.append(
                {
                    "level": lod.level,
                    "file": file_name,
                    "triangles": int(lod.mesh.faces.shape[0]),
                    "within_limit": bool(lod.within_limit),
                    **lod.error.as_dict(),
                }
            )
        if not lods[0]["within_limit"]:
            raise RuntimeError(f"{entry['id']}: full-resolution mesh exceeds its {limit} mm limit")
        shown = display_level(lods)
        for lod in lods:
            lod["published"] = not publish_shown_only or lod["level"] == shown
            if not lod["published"]:
                (out / lod["file"]).unlink()
        lod0 = build.lods[0].mesh
        structures.append(
            {
                "id": entry["id"],
                "source_label": label.source_label,
                **({"source_part": label.part} if label.part else {}),
                "names": {"en": entry["name_en"], "ar": entry["name_ar"], "latin": entry["name_ta_latin"]},
                "ar_status": entry["ar_status"],
                "content_status": entry["content_status"],
                "provenance_tier": entry["provenance_tier"],
                "system": entry["system"],
                "color": entry["color"],
                "mesh_error_limit_mm": limit,
                "default_opacity": float(entry.get("default_opacity", 1.0)),
                "default_visible": bool(entry.get("default_visible", True)),
                **({"description": entry["description"]} if "description" in entry else {}),
                **({"group": group_of(ontology, entry)} if group_of(ontology, entry) else {}),
                **(
                    {"division_review": {"by": entry["division_reviewed_by"], "on": entry["division_reviewed_on"]}}
                    if entry.get("division_reviewed_by")
                    else {}
                ),
                "smoothing": {"method": "taubin", "max_vertex_displacement_mm": round(build.clamp_mm, 4)},
                "closed_surface": bool(lod0.is_watertight),
                "source_voxel_mm": [round(float(v), 5) for v in label.spacing],
                "bounds_mm": np.round(lod0.bounds, 4).tolist(),
                # Volume is only meaningful for a closed surface.
                "volume_mm3": round(float(lod0.volume), 4) if lod0.is_watertight else None,
                "display_level": shown,
                "lods": lods,
            }
        )
    info = ontology["datasets"][dataset]
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "specimen_id": specimen_id,
        "dataset": dataset,
        "side": side,
        "synthetic": synthetic,
        "units": "mm",
        "attribution": {"data_doi": info["data_doi"], "paper_doi": info["paper_doi"], "license": info["license"]},
        "generated": {"pipeline_version": PIPELINE_VERSION, "date": date.today().isoformat()},
        "structures": structures,
        **(extra or {}),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
