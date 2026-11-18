"""Package a specimen's own scan for the slice view.

The scan is cropped to the region around the structures, mapped to 8-bit grey with a
window recorded in the manifest, and written gzip-compressed with x varying fastest.
Positions use the same frame as the meshes: millimetres, origin at the centre of
voxel (0, 0, 0), axes running in the positive right-anterior-superior directions.
"""
from __future__ import annotations

import gzip
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SCAN_FILE = "scan.u8.gz"


@dataclass(frozen=True)
class Volume:
    data: np.ndarray  # indexed [x, y, z]
    spacing: tuple[float, float, float]
    origin: tuple[float, float, float]


def to_positive_axes(data: np.ndarray, step, first) -> Volume:
    """Flip axes whose step is negative, so every axis runs in the positive direction."""
    step = np.asarray(step, dtype=np.float64)
    first = np.asarray(first, dtype=np.float64)
    for axis in range(3):
        if step[axis] < 0:
            data = np.flip(data, axis=axis)
            first[axis] = first[axis] + (data.shape[axis] - 1) * step[axis]
            step[axis] = -step[axis]
    return Volume(np.ascontiguousarray(data), tuple(float(s) for s in step), tuple(float(o) for o in first))


def crop(volume: Volume, lo_mm, hi_mm) -> Volume:
    """The voxels covering the box [lo_mm, hi_mm] (rounded outwards to whole voxels), clipped to the volume."""
    sp, org = np.asarray(volume.spacing), np.asarray(volume.origin)
    lo = np.clip(np.floor((np.asarray(lo_mm) - org) / sp).astype(int), 0, None)
    hi = np.minimum(np.ceil((np.asarray(hi_mm) - org) / sp).astype(int) + 1, volume.data.shape)
    if (hi <= lo).any():
        raise ValueError("the crop box does not overlap the scan")
    sub = volume.data[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]]
    return Volume(np.ascontiguousarray(sub), volume.spacing, tuple(float(v) for v in org + lo * sp))


def window(data: np.ndarray, low_pct: float = 0.5, high_pct: float = 99.8) -> tuple[np.ndarray, float, float]:
    """Map to 0..255 between two percentiles of the cropped scan, so each scan uses its own range."""
    sample = data[:: max(1, data.shape[0] // 64), :: max(1, data.shape[1] // 64), :: max(1, data.shape[2] // 64)]
    low, high = (float(v) for v in np.percentile(sample, [low_pct, high_pct]))
    if high <= low:
        high = low + 1.0
    scaled = (data.astype(np.float32) - low) * (255.0 / (high - low))
    return np.clip(np.rint(scaled), 0, 255).astype(np.uint8), low, high


def write_scan(out_dir: str | Path, volume: Volume, modality: str, source: str) -> dict:
    """Write the windowed scan and return its manifest entry."""
    u8, low, high = window(volume.data)
    raw = np.ascontiguousarray(u8.transpose(2, 1, 0)).tobytes()  # x fastest, then y, then z
    path = Path(out_dir) / SCAN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb", compresslevel=6) as fh:
        fh.write(raw)
    return {
        "file": SCAN_FILE,
        "format": "uint8, gzip, x fastest",
        "shape": [int(v) for v in u8.shape],
        "spacing_mm": [round(s, 6) for s in volume.spacing],
        "origin_mm": [round(o, 6) for o in volume.origin],
        "modality": modality,
        "source": source,
        "window": {"low": round(low, 3), "high": round(high, 3), "rule": "0.5th to 99.8th percentile of the crop"},
    }


def box_around(labels, margin_mm: float) -> tuple[np.ndarray, np.ndarray]:
    """Bounding box, in mm, of several cropped label masks plus a margin."""
    los, his = [], []
    for mask, spacing, origin in labels:
        idx = np.argwhere(mask)
        if idx.size == 0:
            continue
        sp, org = np.asarray(spacing), np.asarray(origin)
        los.append(org + idx.min(axis=0) * sp)
        his.append(org + idx.max(axis=0) * sp)
    if not los:
        raise ValueError("no labels to frame the scan")
    return np.min(los, axis=0) - margin_mm, np.max(his, axis=0) + margin_mm
