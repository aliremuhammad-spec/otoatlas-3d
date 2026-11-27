"""Development extract for Phase 2B WP0, second step: from ZETA's micro-slicing colour volume
(already in the specimen frame, see CLAUDE.md) make
  * RGBA volumes at 0.1, 0.15 and 0.2 mm cropped to the tissue; alpha is 0 for epoxy and the
    black surround (low saturation and bright, or dark), a soft ramp in between;
  * a native-resolution crop (0.05 x 0.05 x 0.15 mm, RGB) around the middle and inner ear for
    measuring how well colour edges and labels agree.
Voxel centres: native voxel i lies at i * step (header origin 0), a block average of f voxels is
centred (f - 1) / 2 steps later; `origin` in every file is the centre of its first voxel, mm.

    python extract_colour_products.py ZETA out_dir

Derived from OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "DATA_PIPELINE"))
from otopipe import fetch  # noqa: E402

STEP = np.array([0.05, 0.05, 0.15])
NATIVE_BOX_MM = ((14.0, 32.0), (12.0, 30.0), (24.0, 44.0))  # x, y, z, around the ossicles, facial nerve and labyrinth


def alpha_of(rgb: np.ndarray) -> np.ndarray:
    """rgb float [3, ...] -> alpha 0..1 (epoxy and black surround transparent)."""
    mx, mn = rgb.max(0), rgb.min(0)
    sat = (mx - mn) / np.maximum(mx, 1.0)
    a = np.clip((sat - 0.14) / 0.12, 0.0, 1.0)
    a[mx < 40] = 0.0
    return a


def resample(vol: np.ndarray, target: float) -> tuple[np.ndarray, np.ndarray]:
    """vol float32 [3, x, y, z] at STEP -> isotropic `target` mm, area-averaged in x and y, linear in z.
    Returns (volume, origin of its first voxel centre)."""
    out_xy = []
    f = int(round(target / STEP[0]))
    fx = vol.shape[1] // f
    fy = vol.shape[2] // f
    a = vol[:, : fx * f, : fy * f, :].reshape(3, fx, f, fy, f, vol.shape[3]).mean(axis=(2, 4))
    nz = int(np.floor((a.shape[3] - 1) * STEP[2] / target)) + 1
    pos = np.arange(nz) * target / STEP[2]
    i0 = np.minimum(np.floor(pos).astype(int), a.shape[3] - 2)
    w = (pos - i0).astype(np.float32)
    out = a[..., i0] * (1 - w) + a[..., i0 + 1] * w
    origin = np.array([(f - 1) / 2 * STEP[0], (f - 1) / 2 * STEP[1], 0.0])
    return out.astype(np.float32), origin


def main(specimen: str, out_dir: Path) -> None:
    import nrrd

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        path = fetch.fetch_openear_member(specimen, r"re:04_Reconstruction_Microslicing/[^/]*\.nrrd$", tmp)
        data, header = nrrd.read(str(path), index_order="F")  # [channel, x, y, z], uint8
    assert data.shape == (3, 792, 792, 346), data.shape
    lo = [int(np.floor(a / s)) for (a, _), s in zip(NATIVE_BOX_MM, STEP)]
    hi = [int(np.ceil(b / s)) for (_, b), s in zip(NATIVE_BOX_MM, STEP)]
    native = np.ascontiguousarray(data[:, lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]])
    np.savez_compressed(out_dir / f"{specimen}_native_ear.npz", rgb=native, spacing=STEP, origin=np.array(lo) * STEP)
    print("native crop", native.shape, flush=True)
    vol = data.astype(np.float32)
    del data
    for target in (0.2, 0.15, 0.1):
        small, origin = resample(vol, target)
        alpha = alpha_of(small)
        idx = np.argwhere(alpha > 0.5)
        margin = int(round(1.0 / target))
        lo_i = np.maximum(idx.min(0) - margin, 0)
        hi_i = np.minimum(idx.max(0) + margin + 1, alpha.shape)
        sl = tuple(slice(a, b) for a, b in zip(lo_i, hi_i))
        rgba = np.concatenate(
            [np.clip(np.rint(small[(slice(None),) + sl]), 0, 255), np.rint(alpha[sl] * 255)[None]], axis=0
        ).astype(np.uint8)
        org = origin + lo_i * target
        tag = f"{target:.2f}".replace(".", "p")
        parts = max(1, int(np.ceil(rgba.nbytes / 160e6)))
        edges = np.linspace(0, rgba.shape[1], parts + 1).astype(int)
        for i in range(parts):
            np.savez_compressed(
                out_dir / f"{specimen}_rgba_{tag}_part{i}.npz",
                rgba=rgba[:, edges[i] : edges[i + 1]],
                spacing=np.full(3, target),
                origin=org + np.array([edges[i], 0, 0]) * target,
            )
        print(f"{target} mm: {rgba.shape[1:]} voxels, origin {org}, {parts} part(s)", flush=True)
        del small, alpha, rgba
    (out_dir / "products_header.txt").write_text(
        f"native step {STEP.tolist()} mm; native box mm {NATIVE_BOX_MM}; source space {header['space']}\n"
    )
    for p in sorted(out_dir.iterdir()):
        print(p.name, p.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
