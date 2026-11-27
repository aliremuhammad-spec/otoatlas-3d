"""Attach the true-colour products (WP1) to the built specimen packages.

    python attach_colour.py attach CONTENT_DIR STAGING_DIR   # before the Hugging Face upload
    python attach_colour.py finish CONTENT_DIR               # after it

STAGING_DIR holds the files of every `build_colour.py` run (`<SPEC>_colour_*.bricks/json`, `<SPEC>_normal.*`,
`<SPEC>_colour_meta.json`), flattened. `attach` copies them into <package>/colour/ and writes the manifest's
`colour` block; a specimen whose build reported an orientation problem gets no colour block and stays on meshes.
`finish` takes the finest tier off the site: it is published only on Hugging Face (to keep the site under the Pages
limit), so a tier without a pinned url is dropped from the manifest, and its bricks file is deleted either way.

Derived from OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0.
Designed under the supervision of Dr. Ali R. Muhammad.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

TIER_ORDER = ("0p10", "0p15", "0p20")  # fine to coarse
OFF_SITE = {"0p10"}


def _volume(folder: Path, spec: str, stem: str, on_site: bool) -> dict:
    index = json.loads((folder / "colour" / f"{spec}_{stem}.json").read_text())
    bricks = folder / "colour" / f"{spec}_{stem}.bricks"
    return {
        "spacing_mm": index["spacing_mm"][0],
        "dims": index["dims"],
        "origin_mm": index["origin_mm"],
        "index": f"colour/{spec}_{stem}.json",
        "bricks": f"colour/{spec}_{stem}.bricks",
        "bytes": bricks.stat().st_size,
        "on_site": on_site,
    }


def attach(content: Path, staging: Path) -> int:
    done = 0
    for manifest_path in sorted(content.glob("*/manifest.json")):
        folder = manifest_path.parent
        spec = folder.name.partition("-")[2]
        meta_file = staging / f"{spec}_colour_meta.json"
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text())
        if any(w.startswith("ORIENTATION") for w in meta.get("warnings", [])):
            print(f"{folder.name}: colour left out, its orientation check failed")
            continue
        (folder / "colour").mkdir(exist_ok=True)
        for f in staging.glob(f"{spec}_*"):
            if f.suffix in (".bricks", ".json") and "_diag" not in f.name and "meta" not in f.name:
                shutil.copy2(f, folder / "colour" / f.name)
        (folder / "colour" / "README.md").write_text(
            f"True-colour volume of {folder.name} for OtoAtlas 3D, derived from the OpenEar micro-slicing images "
            "(Sieber et al., Scientific Data 2019, doi:10.1038/sdata.2018.297; data doi:10.5281/zenodo.1473724), CC BY 4.0.\n"
            "Designed under the supervision of Dr. Ali R. Muhammad.\n"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["colour"] = {
            "alpha_source": "colour+cbct" if meta.get("cbct_alpha", {}).get("usable") else "colour",
            "levelled": bool(meta["levelling"].get("levelled")),
            "shift_mm": meta["alignment"]["applied_shift_mm_colour_minus_label"],
            "brick": 64,
            "tiers": [_volume(folder, spec, f"colour_{t}", t not in OFF_SITE) for t in TIER_ORDER],
            "normals": _volume(folder, spec, "normal", True),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        done += 1
        print(f"{folder.name}: colour attached ({manifest['colour']['alpha_source']})")
    return done


def finish(content: Path) -> None:
    for manifest_path in sorted(content.glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        colour = manifest.get("colour")
        if not colour:
            continue
        kept = []
        for tier in colour["tiers"]:
            if not tier["on_site"]:
                (manifest_path.parent / tier["bricks"]).unlink(missing_ok=True)
                if not tier.get("url"):
                    print(f"{manifest_path.parent.name}: tier {tier['spacing_mm']} mm dropped (no Hugging Face url)")
                    continue
            kept.append(tier)
        colour["tiers"] = kept
        if not kept:
            del manifest["colour"]
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "attach":
        attach(Path(sys.argv[2]), Path(sys.argv[3]))
    elif sys.argv[1] == "finish":
        finish(Path(sys.argv[2]))
    else:
        raise SystemExit("usage: attach_colour.py attach CONTENT STAGING | finish CONTENT")
