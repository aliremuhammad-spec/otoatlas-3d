"""Split OpenEar's "Scala Vestibuli" label into its cochlear and vestibular parts.

In OpenEar the label covers the whole perilymphatic space above the basilar membrane:
scala vestibuli, vestibule and semicircular canals. The reviewer asked for scala
vestibuli to be confined to the cochlea and the canals shown as a separate structure.

The dataset gives no boundary between scala vestibuli and the vestibule, so this is a
computed first pass: a voxel of the label belongs to the cochlea when it lies within
`reach_mm` of scala tympani, which the dataset does confine to the cochlea. Only the
largest connected piece of that set is kept as the cochlear part; everything else in
the label is the vestibular part. The reviewer checks the boundary before it is
marked reviewed.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

DEFAULT_REACH_MM = 1.0


@dataclass(frozen=True)
class Part:
    mask: np.ndarray
    origin: tuple[float, float, float]


@dataclass(frozen=True)
class Split:
    cochlear: Part
    vestibular: Part
    report: dict


def _crop(mask: np.ndarray, origin: np.ndarray, spacing: np.ndarray) -> Part:
    idx = np.argwhere(mask)
    if idx.size == 0:
        raise ValueError("a split part is empty")
    lo, hi = idx.min(axis=0), idx.max(axis=0) + 1
    sub = mask[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]].copy()
    return Part(sub, tuple(float(v) for v in origin + lo * spacing))


def _extent_mm(part: Part, spacing: np.ndarray) -> list[float]:
    return [round(float(v), 2) for v in np.array(part.mask.shape) * spacing]


def split_by_reach(
    label: np.ndarray,
    label_origin,
    reference: np.ndarray,
    reference_origin,
    spacing,
    reach_mm: float = DEFAULT_REACH_MM,
) -> Split:
    """Split `label` into the piece within `reach_mm` of `reference` and the rest.

    Both masks are cropped volumes on the same voxel grid; origins are the centres of
    voxel (0, 0, 0) in mm.
    """
    spacing = np.asarray(spacing, dtype=np.float64)
    lo_l, lo_r = np.asarray(label_origin, float), np.asarray(reference_origin, float)
    offset = (lo_r - lo_l) / spacing
    if np.abs(offset - np.round(offset)).max() > 1e-3:
        raise ValueError("the two labels are not on the same voxel grid")
    offset = np.round(offset).astype(int)

    # A common grid holding both masks, so distances to reference voxels outside the
    # label's own box are still counted.
    start = np.minimum(0, offset)
    stop = np.maximum(np.array(label.shape), offset + np.array(reference.shape))
    shape = tuple(int(v) for v in stop - start)
    lab = np.zeros(shape, bool)
    ref = np.zeros(shape, bool)
    a = -start
    lab[a[0] : a[0] + label.shape[0], a[1] : a[1] + label.shape[1], a[2] : a[2] + label.shape[2]] = label
    b = offset - start
    ref[b[0] : b[0] + reference.shape[0], b[1] : b[1] + reference.shape[1], b[2] : b[2] + reference.shape[2]] = reference
    grid_origin = lo_l + start * spacing

    distance = ndimage.distance_transform_edt(~ref, sampling=spacing)
    near = lab & (distance <= reach_mm)
    pieces, count = ndimage.label(near, structure=np.ones((3, 3, 3), bool))
    if count == 0:
        raise ValueError("no part of the label lies within reach of the reference")
    sizes = np.bincount(pieces.ravel())[1:]
    cochlear = pieces == (int(np.argmax(sizes)) + 1)
    vestibular = lab & ~cochlear
    _, vestibular_pieces = ndimage.label(vestibular, structure=np.ones((3, 3, 3), bool))

    c, v = _crop(cochlear, grid_origin, spacing), _crop(vestibular, grid_origin, spacing)
    voxel_mm3 = float(np.prod(spacing))
    report = {
        "method": "within reach of scala tympani, largest connected piece",
        "reach_mm": reach_mm,
        "cochlear_volume_mm3": round(float(cochlear.sum()) * voxel_mm3, 3),
        "vestibular_volume_mm3": round(float(vestibular.sum()) * voxel_mm3, 3),
        "cochlear_extent_mm": _extent_mm(c, spacing),
        "vestibular_extent_mm": _extent_mm(v, spacing),
        "vestibular_pieces": int(vestibular_pieces),
        "near_pieces_dropped": int(count - 1),
    }
    return Split(c, v, report)
