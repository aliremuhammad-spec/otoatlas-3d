"""One label volume per specimen: which structure each voxel belongs to, for the surgical view.

The colour volume says what the tissue looks like; this volume says what it is, so the app can hide, show,
tint or isolate a structure in the colour picture. Every structure of the package that comes from the
specimen (including parts made by a computed division) is painted in as its manifest id. Schematic
structures are left out: they are drawn from rules, not from the scan, and they overlap real tissue.

Layout of the file: raw uint8, [z][y][x] with x fastest, gzipped; the manifest gives dims as [nx, ny, nz],
the voxel size and the position of the centre of the first voxel in the specimen frame (the same frame as
the meshes and the colour volume).
"""
from __future__ import annotations

import gzip
from dataclasses import dataclass

import numpy as np

GRID_MM = 0.125
MAX_IDS = 255
MAX_VOXELS = 400_000_000


@dataclass(frozen=True)
class Item:
    id: str
    mask: np.ndarray  # bool [x, y, z]
    spacing: tuple[float, float, float]
    origin: tuple[float, float, float]  # centre of voxel [0, 0, 0]


@dataclass(frozen=True)
class LabelVolume:
    data: np.ndarray  # uint8 [z, y, x]
    spacing_mm: float
    origin_mm: tuple[float, float, float]
    dims: tuple[int, int, int]  # nx, ny, nz
    values: dict[str, int]  # structure id -> value in the volume (1..255; 0 means no structure)


def _extent(item: Item) -> tuple[np.ndarray, np.ndarray] | None:
    """Index range of the true voxels per axis, or None for an empty mask."""
    lo, hi = [], []
    for axis in range(3):
        others = tuple(a for a in range(3) if a != axis)
        present = np.flatnonzero(item.mask.any(axis=others))
        if present.size == 0:
            return None
        lo.append(int(present[0]))
        hi.append(int(present[-1]))
    return np.array(lo), np.array(hi)


def build(items: list[Item], spacing_mm: float = GRID_MM) -> LabelVolume:
    """Paint every item on one grid, nearest neighbour; where two overlap the smaller structure wins."""
    if len(items) > MAX_IDS:
        raise ValueError(f"{len(items)} structures do not fit in an 8-bit label volume")
    boxes: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for it in items:
        ext = _extent(it)
        if ext is None:
            continue
        sp, org = np.asarray(it.spacing, float), np.asarray(it.origin, float)
        boxes[it.id] = (org + ext[0] * sp, org + ext[1] * sp)  # centres of the first and last true voxels, mm
    if not boxes:
        raise ValueError("no structure has any voxel")
    lo = np.min([b[0] for b in boxes.values()], axis=0)
    hi = np.max([b[1] for b in boxes.values()], axis=0)
    dims = tuple(int(v) for v in np.floor((hi - lo) / spacing_mm + 0.5) + 1)
    if int(np.prod(dims)) > MAX_VOXELS:
        raise ValueError(f"label volume of {dims} voxels is too large")
    out = np.zeros(dims, np.uint8)  # [x, y, z] while painting
    values = {i: n + 1 for n, i in enumerate(sorted(boxes))}
    # Largest first, so that the smallest structure is painted last and keeps an overlapped voxel.
    volume = {it.id: float(it.mask.sum()) * float(np.prod(it.spacing)) for it in items if it.id in boxes}
    for it in sorted((i for i in items if i.id in boxes), key=lambda i: -volume[i.id]):
        sp, org = np.asarray(it.spacing, float), np.asarray(it.origin, float)
        b_lo, b_hi = boxes[it.id]
        t_lo = np.maximum(np.ceil((b_lo - sp / 2 - lo) / spacing_mm - 1e-9).astype(int), 0)
        t_hi = np.minimum(np.floor((b_hi + sp / 2 - lo) / spacing_mm + 1e-9).astype(int), np.array(dims) - 1)
        if np.any(t_hi < t_lo):
            continue
        ids, ok = [], []
        for k in range(3):
            pos = lo[k] + np.arange(t_lo[k], t_hi[k] + 1) * spacing_mm
            idx = np.floor((pos - org[k]) / sp[k] + 0.5).astype(int)
            good = (idx >= 0) & (idx < it.mask.shape[k])
            ids.append(np.where(good, idx, 0))
            ok.append(good)
        inside = it.mask[np.ix_(*ids)] & ok[0][:, None, None] & ok[1][None, :, None] & ok[2][None, None, :]
        view = out[t_lo[0] : t_hi[0] + 1, t_lo[1] : t_hi[1] + 1, t_lo[2] : t_hi[2] + 1]
        view[inside] = values[it.id]
    return LabelVolume(
        data=np.ascontiguousarray(out.transpose(2, 1, 0)),
        spacing_mm=float(spacing_mm),
        origin_mm=tuple(float(v) for v in lo),
        dims=dims,
        values=values,
    )


def encode(vol: LabelVolume) -> bytes:
    """The bytes of `labels.u8.gz`."""
    return gzip.compress(vol.data.tobytes(), compresslevel=9, mtime=0)


def decode(blob: bytes, dims: tuple[int, int, int]) -> np.ndarray:
    """Inverse of `encode`: uint8 [z, y, x]."""
    nx, ny, nz = dims
    return np.frombuffer(gzip.decompress(blob), np.uint8).reshape(nz, ny, nx)


def manifest_block(vol: LabelVolume, blob: bytes, file: str, excluded: list[str]) -> dict:
    return {
        "file": file,
        "bytes": len(blob),
        "dims": list(vol.dims),
        "spacing_mm": vol.spacing_mm,
        "origin_mm": [round(v, 6) for v in vol.origin_mm],
        "structures": [{"id": k, "value": v} for k, v in sorted(vol.values.items(), key=lambda kv: kv[1])],
        "excluded_schematic": sorted(excluded),
        "layout": "gzip of uint8 [z][y][x], x fastest; 0 means no structure; nearest neighbour from each label",
    }
