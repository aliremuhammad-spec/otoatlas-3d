"""Publish every specimen scan to a public Hugging Face dataset and point the manifests at it.

Run in the deploy job after the site is assembled, with HF_TOKEN set. For each package
in the content folder, the scan file is uploaded under content/<package>/ in the dataset
<user>/otoatlas-3d-content, the manifest gets an absolute "url" pinned to that upload's
commit (so a cached copy never mixes versions), and the local file is removed so it is
not also published on GitHub Pages. Files that did not change are not uploaded again.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

REPO_NAME = "otoatlas-3d-content"

CARD = """---
license: cc-by-4.0
pretty_name: OtoAtlas 3D specimen scans
tags:
- medical
- anatomy
- temporal-bone
- otology
---

# OtoAtlas 3D specimen scans

Cropped, 8-bit copies of specimen scans used by the OtoAtlas 3D teaching app
(https://aliremuhammad-spec.github.io/otoatlas-3d/). Each `scan.u8.gz` is gzip-compressed
uint8 with x varying fastest; shape, voxel size, origin and grey window are in the
specimen's `manifest.json` in the app.

Designed under the supervision of Dr. Ali R. Muhammad.

For education only. Not a medical device; not for diagnosis or planning surgery on a
particular patient.

## Sources (both CC BY 4.0)

- OpenEar: Sieber D. et al. The OpenEar library of 3D models of the human temporal bone
  based on computed tomography and micro-slicing. Scientific Data 6, 180297 (2019).
  doi:10.5281/zenodo.1473724
- Human bony labyrinth dataset: Wimmer W. et al. Human bony labyrinth dataset: co-registered
  CT and micro-CT images, surface models and anatomical landmarks. Data in Brief 27, 104782
  (2019). doi:10.5281/zenodo.3355272

The files here are derived from those datasets: cropped around the ear structures and
mapped to 8 bits between the 0.5th and 99.8th percentile of each crop.
"""


def main(content: Path) -> None:
    api = HfApi()
    repo = f"{api.whoami()['name']}/{REPO_NAME}"
    api.create_repo(repo, repo_type="dataset", private=False, exist_ok=True)
    manifests = sorted(content.glob("*/manifest.json"))
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        moved: list[tuple[Path, dict, Path]] = []
        for path in manifests:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            scan = manifest.get("scan")
            if not scan:
                continue
            local = path.parent / scan["file"]
            if not local.exists():
                continue
            target = stage / path.parent.name / scan["file"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local, target)
            moved.append((path, manifest, local))
        (stage / "README.md").write_text(CARD, encoding="utf-8")
        commit = api.upload_folder(
            repo_id=repo,
            repo_type="dataset",
            folder_path=str(stage),
            path_in_repo="",
            commit_message="Update specimen scans",
            delete_patterns=["*/scan.u8.gz"],
        )
    revision = getattr(commit, "oid", None) or api.repo_info(repo, repo_type="dataset").sha
    for path, manifest, local in moved:
        package = path.parent.name
        manifest["scan"]["url"] = (
            f"https://huggingface.co/datasets/{repo}/resolve/{revision}/{package}/{manifest['scan']['file']}"
        )
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        local.unlink()
    print(f"{len(moved)} scans published to https://huggingface.co/datasets/{repo} at {revision}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
