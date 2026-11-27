"""Development extract for Phase 2B WP0: ZETA's micro-slicing colour volume (RGB, own frame, not
registered), block-averaged to 0.2 mm and saved as .npz parts below 90 MB, plus the header and the
two reconstruction CSV files. Lives outside DATA_PIPELINE so editing it does not rebuild content.

    python extract_colour_dev.py ZETA out_dir

Derived from OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "DATA_PIPELINE"))
from otopipe import fetch  # noqa: E402


def main(specimen: str, out_dir: Path) -> None:
    import nrrd
    from scipy import ndimage

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for suffix in ("Layer_Positions_ZETA.csv", "Transformations_Zeta.CSV"):
            p = fetch.fetch_openear_member(specimen, suffix, tmp)
            (out_dir / p.name).write_bytes(p.read_bytes())
        path = fetch.fetch_openear_member(specimen, r"re:04_Reconstruction_Microslicing/[^/]*\.nrrd$", tmp)
        data, header = nrrd.read(str(path), index_order="F")  # [channel, x, y, z]
    print("shape", data.shape, data.dtype, flush=True)
    assert data.ndim == 4 and data.shape[0] == 3
    step = np.abs(np.diag(np.asarray(header["space directions"][1:], dtype=np.float64)))
    f = int(round(0.2 / step[0]))
    nx, ny = data.shape[1] // f, data.shape[2] // f
    small = data[:, : nx * f, : ny * f, :].reshape(3, nx, f, ny, f, data.shape[3]).mean(axis=(2, 4), dtype=np.float32)
    del data
    nz = int(round((small.shape[3] - 1) * step[2] / 0.2)) + 1
    zoom = (nz - 1) / (small.shape[3] - 1)
    out = np.stack(
        [ndimage.zoom(small[c], (1, 1, zoom), order=1, mode="nearest", grid_mode=False)[:, :, :nz] for c in range(3)]
    )
    sp = np.array([step[0] * f, step[1] * f, step[2] * (small.shape[3] - 1) / (nz - 1)])
    out = np.clip(np.rint(out), 0, 255).astype(np.uint8)
    print("0.2 mm volume", out.shape, "spacing", sp, flush=True)
    # Split along x so every file stays well below GitHub's 100 MB limit.
    parts = 4
    edges = np.linspace(0, out.shape[1], parts + 1).astype(int)
    for i in range(parts):
        np.savez_compressed(
            out_dir / f"{specimen}_colour_0p2_part{i}.npz",
            rgb=out[:, edges[i] : edges[i + 1]],
            x0=edges[i],
            spacing=sp,
            origin=np.zeros(3),
        )
    (out_dir / "header.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in header.items()) + f"\nblock_average_xy={f}\nz_spacing_mm={sp[2]}\n"
    )
    for p in sorted(out_dir.iterdir()):
        print(p.name, p.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
