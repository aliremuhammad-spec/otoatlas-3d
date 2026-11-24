"""The air spaces of the temporal bone, from the bone label and the registered CBCT.

OpenEar specimens are blocks of temporal bone cut out and embedded in epoxy. Inside the
block, every place that is neither bone nor another labelled structure is a space that
was air in life: the tympanic cavity, the antrum and the air cells. The block itself is
found on the CBCT (its bone is far brighter than the epoxy), so spaces outside the cut
faces are never counted.

Rules, on a 0.25 mm grid:
- walls: labelled bone (any part of a grid cell) that is also bright on the scan, and every other labelled structure
  (canal, sinus and dura, labyrinth, carotid, facial nerve, ossicles, membrane);
- spaces: what the walls enclose (gaps up to 0.5 mm closed; holes filled slice by slice in
  each of the three directions), that is neither bone nor another label and is darker than
  bone on the scan (the spaces hold epoxy in these specimens); pieces under
  1 cubic millimetre are dropped;
- tympanic cavity: the part of that space within 4 mm of the ossicles or the membrane;
- air cells: the rest: mastoid, perilabyrinthine, petrous and zygomatic cells as far as
  the block reaches;
- antrum (when the short process of the incus is known): the cells are opened with a
  1 mm ball, which removes small cells and the narrow passages between them; of the
  pieces left, the largest one within 6 mm of the tip of the short process is the
  antrum, grown back by the same ball inside the cells.

The division between the two is a distance rule, not the anatomical walls; it is shown as
computed and awaits review. Where the block was cut, the cells beyond the cut are missing,
so volumes are of the specimen, not of the whole ear.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

GRID_MM = 0.25
NEAR_OSSICLES_MM = 4.0
CLOSE_VOXELS = 2
WALL_LEVEL = 130  # on the scan windowed to 0..255 between its 0.5 and 99.8 percentiles
SPACE_LEVEL = 145
MIN_PIECE_MM3 = 1.0


@dataclass(frozen=True)
class AirSpaces:
    tympanic: tuple[np.ndarray, tuple[float, float, float]]  # mask, origin; spacing GRID_MM
    cells: tuple[np.ndarray, tuple[float, float, float]]
    report: dict


def _to_grid(mask, spacing, origin, grid_origin, grid_shape, rule: str) -> np.ndarray:
    """A label resampled to the grid by whole blocks of voxels: `majority` or `any`."""
    sp = np.asarray(spacing, float)
    f = np.maximum(1, np.rint(GRID_MM / sp).astype(int))
    if not np.allclose(f * sp, GRID_MM, atol=0.02):
        raise ValueError(f"label spacing {tuple(sp)} does not divide the {GRID_MM} mm grid")
    shape = [s // k * k for s, k in zip(mask.shape, f)]
    blocks = mask[: shape[0], : shape[1], : shape[2]].reshape(
        shape[0] // f[0], f[0], shape[1] // f[1], f[1], shape[2] // f[2], f[2]
    )
    if rule == "majority":  # counted in 16 bits: a float mean of a large label needs gigabytes
        small = blocks.sum(axis=(1, 3, 5), dtype=np.uint16) * 2 >= int(np.prod(f))
    else:
        small = blocks.any(axis=(1, 3, 5))
    out = np.zeros(grid_shape, bool)
    off = np.rint((np.asarray(origin, float) - grid_origin) / GRID_MM).astype(int)
    lo = np.maximum(off, 0)
    hi = np.minimum(off + np.array(small.shape), grid_shape)
    if (hi <= lo).any():
        return out
    out[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]] = small[
        lo[0] - off[0] : hi[0] - off[0], lo[1] - off[1] : hi[1] - off[1], lo[2] - off[2] : hi[2] - off[2]
    ]
    return out


def _scan_to_grid(u8: np.ndarray, spacing, origin, grid_origin, grid_shape) -> np.ndarray:
    sp = np.asarray(spacing, float)
    f = np.maximum(1, np.rint(GRID_MM / sp).astype(int))
    shape = [s // k * k for s, k in zip(u8.shape, f)]
    small = (
        u8[: shape[0], : shape[1], : shape[2]]
        .reshape(shape[0] // f[0], f[0], shape[1] // f[1], f[1], shape[2] // f[2], f[2])
        .mean(axis=(1, 3, 5))
    )
    out = np.zeros(grid_shape, np.float32)
    off = np.rint((np.asarray(origin, float) - grid_origin) / (sp * f)).astype(int)
    lo = np.maximum(off, 0)
    hi = np.minimum(off + np.array(small.shape), grid_shape)
    out[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]] = small[
        lo[0] - off[0] : hi[0] - off[0], lo[1] - off[1] : hi[1] - off[1], lo[2] - off[2] : hi[2] - off[2]
    ]
    return out


def _block(walls: np.ndarray) -> np.ndarray:
    """Everything enclosed by the walls: holes filled slice by slice along each axis, after
    closing gaps up to 0.5 mm. A concavity of the cut block's outside is not enclosed, so it
    is not filled."""
    closed = ndimage.binary_closing(walls, iterations=CLOSE_VOXELS) | walls
    filled = np.zeros_like(closed)
    for axis in range(3):
        moved = np.moveaxis(closed, axis, 0)
        out = np.moveaxis(filled, axis, 0)
        for i in range(moved.shape[0]):
            if moved[i].any():
                out[i] |= ndimage.binary_fill_holes(moved[i])
    return filled


def _crop(mask: np.ndarray, origin: np.ndarray) -> tuple[np.ndarray, tuple[float, float, float]]:
    idx = np.argwhere(mask)
    lo, hi = idx.min(axis=0), idx.max(axis=0) + 1
    return mask[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]].copy(), tuple(float(v) for v in origin + lo * GRID_MM)


def air_spaces(bone, others: list, ossicles_and_membrane: list, ct_u8) -> AirSpaces:
    """`bone` and every item of `others` and `ossicles_and_membrane` are (mask, spacing, origin);
    `ct_u8` is (windowed scan, spacing, origin) registered to the labels."""
    mask, spacing, origin = bone
    sp = np.asarray(spacing, float)
    grid_origin = np.asarray(origin, float)
    grid_shape = tuple(int(np.ceil(s * d / GRID_MM)) for s, d in zip(mask.shape, sp))
    bone_g = _to_grid(mask, spacing, origin, grid_origin, grid_shape, "majority")
    ct = _scan_to_grid(*ct_u8, grid_origin, grid_shape)
    excluded = np.zeros(grid_shape, bool)
    for lab in [*others, *ossicles_and_membrane]:
        excluded |= _to_grid(*lab, grid_origin, grid_shape, "any")
    # Walls: bone that is both labelled and bright on the scan (so label beyond the cut block
    # does not count), and every other labelled structure, which closes the cavity at the
    # membrane and the canals.
    bone_any = _to_grid(mask, spacing, origin, grid_origin, grid_shape, "any")
    walls = (bone_any & (ct > WALL_LEVEL)) | excluded
    block = _block(walls)
    if block.sum() * GRID_MM**3 < 1000:
        raise ValueError("no enclosed space found inside the specimen")
    # Air spaces are filled with epoxy in these specimens: darker than bone on the scan.
    space = block & ~bone_g & ~excluded & (ct > 0) & (ct < SPACE_LEVEL)
    lab_, n = ndimage.label(space)
    if n == 0:
        raise ValueError("no air space inside the block")
    sizes = np.bincount(lab_.ravel())
    keep = sizes * GRID_MM**3 >= MIN_PIECE_MM3
    keep[0] = False
    main = keep[lab_]
    pts = grid_origin + np.argwhere(main) * GRID_MM
    anchors = np.vstack(
        [np.asarray(o, float) + np.argwhere(m) * np.asarray(s, float) for m, s, o in ossicles_and_membrane]
    )
    near, _ = cKDTree(anchors).query(pts, distance_upper_bound=NEAR_OSSICLES_MM)
    tympanic_pts = np.isfinite(near)
    idx = np.argwhere(main)
    tympanic = np.zeros(grid_shape, bool)
    tympanic[tuple(idx[tympanic_pts].T)] = True
    cells = main & ~tympanic
    if not tympanic.any() or not cells.any():
        raise ValueError("the air space does not reach both the ossicles and beyond")
    v = GRID_MM**3 / 1000.0  # millilitres per voxel
    report = {
        "grid_mm": GRID_MM,
        "block_ml": round(float(block.sum() * v), 2),
        "bone_in_block_ml": round(float((block & bone_g).sum() * v), 2),
        "air_space_ml": round(float(main.sum() * v), 2),
        "tympanic_cavity_ml": round(float(tympanic.sum() * v), 2),
        "air_cells_ml": round(float(cells.sum() * v), 2),
        "pieces_kept": int(keep.sum()),
        "pieces_dropped": int(n - keep.sum()),
        "space_dropped_ml": round(float((space & ~main).sum() * v), 2),
        "rule": "otopipe/pneumatization.py",
    }
    t = _crop(tympanic, grid_origin)
    c = _crop(cells, grid_origin)
    return AirSpaces(t, c, report)


ANTRUM_BALL_MM = 1.0
ANTRUM_NEAR_MM = 6.0


def _ball(radius_voxels: int) -> np.ndarray:
    g = np.arange(-radius_voxels, radius_voxels + 1)
    x, y, z = np.meshgrid(g, g, g, indexing="ij")
    return x * x + y * y + z * z <= radius_voxels * radius_voxels


def split_antrum(cells, short_process_tip) -> tuple:
    """(antrum, other cells, report) from the air cells (mask, origin on the GRID_MM grid);
    raises ValueError when no large cavity lies near the short process."""
    mask, origin = cells
    origin = np.asarray(origin, float)
    r = round(ANTRUM_BALL_MM / GRID_MM)
    ball = _ball(r)
    opened = ndimage.binary_opening(mask, structure=ball)
    lab, n = ndimage.label(opened)
    tip = np.asarray(short_process_tip, float)
    best = None
    for k in range(1, n + 1):
        idx = np.argwhere(lab == k)
        near = float(np.linalg.norm(origin + idx * GRID_MM - tip, axis=1).min())
        if near <= ANTRUM_NEAR_MM and (best is None or len(idx) > best[1]):
            best = (k, len(idx), near)
    if best is None:
        raise ValueError("no large cavity within 6 mm of the short process")
    antrum = ndimage.binary_dilation(lab == best[0], structure=ball) & mask
    rest = mask & ~antrum
    v = GRID_MM**3 / 1000.0
    report = {
        "antrum_ml": round(float(antrum.sum() * v), 2),
        "antrum_to_short_process_mm": round(best[2], 1),
        "air_cells_without_antrum_ml": round(float(rest.sum() * v), 2),
    }
    return _crop(antrum, origin), _crop(rest, origin), report
