"""Regenerates app/e2e/fixtures/content-colour/TEST-COLOUR-01 (run from the repository root).

A tiny package for the surgical view tests: a pink tissue ball with a dark core, as true-colour bricks at
0.15 and 0.2 mm, normals at 0.4 mm, and a label volume at 0.125 mm in which the shell is "malleus" and the
core is "scala_tympani". Designed under the supervision of Dr. Ali R. Muhammad.
"""
import gzip
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "DATA_PIPELINE")
from otopipe import colour, labelvol  # noqa: E402

SRC = Path("app/e2e/fixtures/content/TEST-SYNTHETIC-01")
DST = Path("app/e2e/fixtures/content-colour/TEST-COLOUR-01")
ORIGIN = [-4.0, -4.0, -4.0]


def ball(n):
    g = (np.indices((n, n, n)) - (n - 1) / 2) / ((n - 1) / 2)
    return g, np.sqrt((g**2).sum(0))


def colour_volume(n):
    _, r = ball(n)
    a = np.zeros((4, n, n, n), np.uint8)
    inside = r < 0.8
    a[0][inside], a[1][inside], a[2][inside], a[3][inside] = 200, 120, 110, 255
    core = r < 0.35
    a[0][core], a[1][core], a[2][core] = 140, 60, 60
    return a


def normals_volume(n):
    g, r = ball(n)
    r = r + 1e-6
    a = np.zeros((4, n, n, n), np.uint8)
    for k in range(3):
        a[k] = np.clip((g[k] / r * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    a[3] = np.where(np.abs(r - 0.8) < 0.12, 255, 0).astype(np.uint8)
    return a


def write(stem, arr, step):
    blob, index = colour.bricks_encode(arr, 64)
    index["spacing_mm"] = [step] * 3
    index["origin_mm"] = ORIGIN
    (DST / "colour" / f"{stem}.bricks").write_bytes(blob)
    (DST / "colour" / f"{stem}.json").write_text(json.dumps(index))
    n = arr.shape[1]
    return {"spacing_mm": step, "dims": [n, n, n], "origin_mm": ORIGIN, "index": f"colour/{stem}.json",
            "bricks": f"colour/{stem}.bricks", "bytes": len(blob), "on_site": True}


def main():
    (DST / "colour").mkdir(parents=True, exist_ok=True)
    m = json.loads((SRC / "manifest.json").read_text())
    m["specimen_id"], m["side"] = "TEST-COLOUR-01", "right"
    tiers = [write("TEST_colour_0p15", colour_volume(54), 0.15), write("TEST_colour_0p20", colour_volume(40), 0.2)]
    normals = write("TEST_normal", normals_volume(20), 0.4)
    m["colour"] = {"alpha_source": "colour", "levelled": True, "shift_mm": [0, 0, 0], "brick": 64, "tiers": tiers, "normals": normals}
    # Label volume: core 1.4 mm radius is scala_tympani, the rest of the ball out to 3.2 mm is malleus.
    n = 65
    idx = np.arange(n) * 0.125 - 4.0
    x, y, z = np.meshgrid(idx, idx, idx, indexing="ij")
    r = np.sqrt(x**2 + y**2 + z**2)
    items = [
        labelvol.Item("malleus", r < 3.2, (0.125,) * 3, (-4.0, -4.0, -4.0)),
        labelvol.Item("scala_tympani", r < 1.4, (0.125,) * 3, (-4.0, -4.0, -4.0)),
    ]
    vol = labelvol.build(items)
    blob = labelvol.encode(vol)
    (DST / "labels.u8.gz").write_bytes(blob)
    m["label_volume"] = labelvol.manifest_block(vol, blob, "labels.u8.gz", [])
    (DST / "manifest.json").write_text(json.dumps(m, indent=1))
    (DST.parent / "index.json").write_text(json.dumps({"specimens": [{"id": "TEST-COLOUR-01", "path": "TEST-COLOUR-01"}]}, indent=2))


if __name__ == "__main__":
    main()
