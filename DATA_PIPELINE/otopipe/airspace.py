"""The air space of the middle ear cleft, computed from a specimen's labels.

No open dataset labels the tympanic cavity. Its air is what the labels leave empty
inside the temporal bone: this module closes the specimen's solid labels (bone and
every soft-tissue label) into an envelope, fills it, and keeps the empty voxels inside.
Of those, only the pieces that touch the ossicles, and only within `REACH_MM` of them,
are kept: the tympanic cavity with its recesses. The antrum and mastoid cells are a
separate, later step.

The bone label alone is not enough: it leaves gaps in less dense bone, so the empty
space it encloses spread through the whole block (5 to 16 mL per specimen in the first
run; a 10 mm ball around the ossicles in the second). Bone is therefore also taken from
the registered CBCT, above an Otsu threshold between bone and the epoxy that fills the
cavity in these embedded specimens (epoxy around 750, bone up to 2400 in ZETA and
GAMMA). The unembedded CBCT does not line up with the labels and is not used.

It is a new segmentation, derived by rule, not drawn by an expert: the reviewer checks
it on the scan before it is marked reviewed. Openings narrower than about twice the
closing radius (the Eustachian tube, the aditus) are bridged by the envelope; wider
openings at the cut faces of the specimen block are not, so cells opened by the cut
are left out.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

DEFAULT_CLOSING_MM = 2.0
COARSE_FACTOR = 2  # the envelope is computed at twice the voxel size, then brought back
SEED_REACH_MM = 0.5
REACH_MM = 12.0


@dataclass(frozen=True)
class AirSpace:
    mask: np.ndarray
    origin: tuple[float, float, float]
    report: dict


def _place(grid_shape, grid_origin, spacing, mask, origin) -> np.ndarray:
    """A label mask placed into a larger grid with the same voxel size."""
    out = np.zeros(grid_shape, dtype=bool)
    off = np.round((np.asarray(origin) - np.asarray(grid_origin)) / np.asarray(spacing)).astype(int)
    lo = np.maximum(off, 0)
    hi = np.minimum(off + np.array(mask.shape), grid_shape)
    if (hi <= lo).any():
        return out
    src_lo = lo - off
    src_hi = src_lo + (hi - lo)
    out[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]] |= mask[
        src_lo[0] : src_hi[0], src_lo[1] : src_hi[1], src_lo[2] : src_hi[2]
    ]
    return out


def _close_and_fill(solid: np.ndarray, spacing, radius_mm: float) -> np.ndarray:
    """Morphological closing by a ball of `radius_mm`, then hole filling, using distance maps."""
    sp = np.asarray(spacing, dtype=np.float64)
    pad = int(np.ceil(radius_mm / sp.min())) + 2
    padded = np.pad(solid, pad)
    grown = ndimage.distance_transform_edt(~padded, sampling=sp) <= radius_mm
    closed = ndimage.distance_transform_edt(grown, sampling=sp) > radius_mm
    closed |= padded
    filled = ndimage.binary_fill_holes(closed)
    return filled[pad:-pad, pad:-pad, pad:-pad]


def middle_ear_air(
    bone: tuple[np.ndarray, tuple, tuple],
    soft: list[tuple[np.ndarray, tuple, tuple]],
    seeds: list[tuple[np.ndarray, tuple, tuple]],
    closing_mm: float = DEFAULT_CLOSING_MM,
    ct=None,
    reach_mm: float = REACH_MM,
) -> AirSpace:
    """Air of the middle ear cleft in the bone label's grid.

    `bone`, `soft` and `seeds` are (mask, spacing, origin) on one voxel size; `seeds` are
    the ossicles, which the kept air must touch.
    """
    bmask, spacing, borigin = bone
    sp = np.asarray(spacing, dtype=np.float64)
    full_seed = np.zeros(bmask.shape, dtype=bool)
    for mask, s, o in seeds:
        full_seed |= _place(bmask.shape, borigin, spacing, mask, o)
    if not full_seed.any():
        raise ValueError("no ossicle inside the bone grid to find the middle ear from")
    # Work in a box reaching `reach_mm` from the ossicles.
    sidx = np.argwhere(full_seed)
    r = int(np.ceil(reach_mm / sp.min()))
    blo = np.maximum(sidx.min(axis=0) - r, 0)
    bhi = np.minimum(sidx.max(axis=0) + 1 + r, bmask.shape)
    del full_seed
    bmask = bmask[blo[0] : bhi[0], blo[1] : bhi[1], blo[2] : bhi[2]]
    borigin = tuple(float(v) for v in np.asarray(borigin) + blo * sp)
    shape = bmask.shape
    solid = bmask.copy()
    for mask, s, o in soft:
        if not np.allclose(s, spacing):
            raise ValueError("all labels must share one voxel size")
        solid |= _place(shape, borigin, spacing, mask, o)
    threshold = None
    if ct is not None:
        # The bone label leaves gaps in less dense bone; bone from the scan closes them.
        values = _ct_on_grid(ct, borigin, sp, shape)
        threshold = _bone_threshold(values)
        solid |= values >= threshold

    # Envelope at a coarser voxel, where a block counts as solid if any of its voxels is.
    f = COARSE_FACTOR
    cshape = tuple(int(np.ceil(n / f)) for n in shape)
    padded = np.zeros(tuple(c * f for c in cshape), dtype=bool)
    padded[: shape[0], : shape[1], : shape[2]] = solid
    coarse = padded.reshape(cshape[0], f, cshape[1], f, cshape[2], f).any(axis=(1, 3, 5))
    envelope_c = _close_and_fill(coarse, sp * f, closing_mm)
    envelope = np.repeat(np.repeat(np.repeat(envelope_c, f, 0), f, 1), f, 2)[: shape[0], : shape[1], : shape[2]]

    empty = envelope & ~solid
    pieces, count = ndimage.label(empty, structure=np.ones((3, 3, 3), bool))
    seed = np.zeros(shape, dtype=bool)
    for mask, s, o in seeds:
        seed |= _place(shape, borigin, spacing, mask, o)
    if not seed.any():
        raise ValueError("no ossicle inside the bone grid to find the middle ear from")
    # Distances to the ossicles only within a box around them, to keep memory small.
    sidx = np.argwhere(seed)
    m = int(np.ceil(SEED_REACH_MM / sp.min())) + 1
    slo = np.maximum(sidx.min(axis=0) - m, 0)
    shi = np.minimum(sidx.max(axis=0) + 1 + m, shape)
    box = tuple(slice(a, b) for a, b in zip(slo, shi))
    near_seed = ndimage.distance_transform_edt(~seed[box], sampling=sp) <= SEED_REACH_MM
    local = pieces[box]
    keep = np.unique(local[near_seed & (local > 0)])
    air = np.isin(pieces, keep)
    # Within reach of the ossicles only (the working box is already that size, so this is cheap).
    air &= ndimage.distance_transform_edt(~seed, sampling=sp) <= reach_mm
    if not air.any():
        raise ValueError("no air space touches the ossicles")

    idx = np.argwhere(air)
    lo, hi = idx.min(axis=0), idx.max(axis=0) + 1
    crop = air[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]].copy()
    voxel = float(np.prod(sp))
    report = {
        "method": "empty space inside the closed and filled solid labels, pieces touching the ossicles",
        "closing_mm": closing_mm,
        "envelope_voxel_mm": [round(float(v) * f, 5) for v in sp],
        "volume_mm3": round(float(air.sum()) * voxel, 1),
        "extent_mm": [round(float(v), 2) for v in (hi - lo) * sp],
        "pieces_kept": int(len(keep)),
        "pieces_dropped": int(count - len(keep)),
        "reach_mm": reach_mm,
        "ct_bone_threshold": None if threshold is None else round(float(threshold), 1),
    }
    return AirSpace(crop, tuple(float(v) for v in np.asarray(borigin) + lo * sp), report)


def _dark_only(empty: np.ndarray, origin, sp: np.ndarray, ct) -> tuple[np.ndarray, float]:
    """Keep the empty voxels whose CBCT value is below an Otsu threshold (air, not tissue)."""
    from skimage.filters import threshold_otsu

    idx = np.argwhere(empty)
    if idx.size == 0:
        return empty, float("nan")
    world = np.asarray(origin) + idx * sp
    cidx = np.rint((world - np.asarray(ct.origin)) / np.asarray(ct.spacing)).astype(int)
    inside = np.all((cidx >= 0) & (cidx < np.array(ct.data.shape)), axis=1)
    values = np.full(len(idx), np.inf, dtype=np.float64)
    ci = cidx[inside]
    values[inside] = ct.data[ci[:, 0], ci[:, 1], ci[:, 2]]
    finite = values[np.isfinite(values)]
    if finite.size < 100:
        raise ValueError("the CBCT does not cover the middle ear")
    t = float(threshold_otsu(finite))
    out = np.zeros_like(empty)
    sel = idx[values < t]
    out[sel[:, 0], sel[:, 1], sel[:, 2]] = True
    return out, t


def _ct_on_grid(ct, origin, sp: np.ndarray, shape) -> np.ndarray:
    """The scan's values at the voxel centres of a grid (nearest voxel; outside the scan: -inf)."""
    axes = [np.asarray(origin)[i] + np.arange(shape[i]) * sp[i] for i in range(3)]
    idx = [np.rint((axes[i] - ct.origin[i]) / ct.spacing[i]).astype(int) for i in range(3)]
    ok = [(v >= 0) & (v < ct.data.shape[i]) for i, v in enumerate(idx)]
    clipped = [np.clip(v, 0, ct.data.shape[i] - 1) for i, v in enumerate(idx)]
    out = ct.data[np.ix_(*clipped)].astype(np.float32)
    outside = ~(ok[0][:, None, None] & ok[1][None, :, None] & ok[2][None, None, :])
    out[outside] = -np.inf
    return out


def _bone_threshold(values: np.ndarray) -> float:
    """Otsu threshold between bone and what fills the cavity, ignoring the scan's background."""
    from skimage.filters import threshold_otsu

    finite = values[np.isfinite(values)]
    if finite.size < 1000:
        raise ValueError("the scan does not cover the middle ear")
    # The scan's padding outside the specimen sits at its minimum value; leave it out.
    lowest = finite.min()
    sample = finite[finite > lowest] if (finite == lowest).mean() > 0.01 else finite
    return float(threshold_otsu(sample[:: max(1, sample.size // 2_000_000)]))
