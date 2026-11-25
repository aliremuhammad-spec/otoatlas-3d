"""A schematic membranous labyrinth, placed on the specimen's own bony labyrinth.

None of this is in the datasets: no specimen has the membranous labyrinth labelled. The
shapes are schematic and always shown as such; only where they sit comes from the
specimen's labels, by these rules:

- cochlear duct: a tube of 0.3 mm radius along the outer edge of the boundary between the
  scala tympani and scala vestibuli labels (where the basilar membrane meets the spiral
  ligament), from the basal end of that boundary to its apical end, nudged 0.15 mm
  towards the scala vestibuli, on whose side the duct lies;
- semicircular ducts: tubes of 0.2 mm radius along the centre lines of the bony canals
  (the skeleton of the vestibular label beyond 2.5 mm of the vestibule's centre, with
  spurs under 1 mm pruned);
- utricle: an ellipsoid of 2.6 x 1.6 x 1.2 mm in the vestibule, moved 0.8 mm from its
  centre towards the canals (the elliptical recess);
- saccule: an ellipsoid of 1.8 x 1.2 x 0.6 mm, moved 1.0 mm from the centre towards the
  cochlea (the spherical recess);
both clipped to the vestibule. Sizes are textbook adult averages, not measurements.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter1d
from scipy.sparse.csgraph import dijkstra
from skimage.morphology import skeletonize

from .ossicles import _voxel_graph

GRID_MM = 0.05
DUCT_RADIUS_MM = 0.3
SCC_DUCT_RADIUS_MM = 0.2
CANAL_FROM_CENTRE_MM = 2.5


@dataclass(frozen=True)
class Membranous:
    parts: dict  # name -> (mask, origin) on GRID_MM
    report: dict


def _common(a, b):
    """Two labels with the same spacing placed into one grid: (mask a, mask b, spacing, origin)."""
    (ma, sa, oa), (mb, sb, ob) = a, b
    sp = np.asarray(sa, float)
    if not np.allclose(sp, sb, atol=1e-6):
        raise ValueError("the scalae have different spacings")
    oa, ob = np.asarray(oa, float), np.asarray(ob, float)
    lo = np.minimum(oa, ob)
    hi = np.maximum(oa + np.array(ma.shape) * sp, ob + np.array(mb.shape) * sp)
    shape = tuple(int(v) for v in np.ceil((hi - lo) / sp) + 1)

    def put(m, o):
        g = np.zeros(shape, bool)
        off = np.rint((o - lo) / sp).astype(int)
        g[off[0] : off[0] + m.shape[0], off[1] : off[1] + m.shape[1], off[2] : off[2] + m.shape[2]] = m
        return g

    return put(ma, oa), put(mb, ob), sp, lo


def _largest(mask: np.ndarray) -> np.ndarray:
    lab, n = ndimage.label(mask, structure=np.ones((3, 3, 3)))
    if n == 0:
        return mask
    return lab == int(np.argmax(np.bincount(lab.ravel())[1:])) + 1


def _tube(points: np.ndarray, radius: float) -> tuple[np.ndarray, tuple[float, float, float]]:
    """Voxels of GRID_MM within `radius` of a sampled path (points closer together than the grid)."""
    lo = points.min(axis=0) - radius - 2 * GRID_MM
    hi = points.max(axis=0) + radius + 2 * GRID_MM
    shape = tuple(int(v) for v in np.ceil((hi - lo) / GRID_MM) + 1)
    seed = np.zeros(shape, bool)
    idx = np.rint((points - lo) / GRID_MM).astype(int)
    seed[tuple(idx.T)] = True
    far = ndimage.distance_transform_edt(~seed, sampling=GRID_MM)
    return far <= radius, tuple(float(v) for v in lo)


def _densify(points: np.ndarray, step: float) -> np.ndarray:
    out = [points[0]]
    for a, b in itertools.pairwise(points):
        n = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        out.extend(a + (b - a) * (i / n) for i in range(1, n + 1))
    return np.array(out)


def cochlear_duct(st, sv) -> tuple[tuple, dict]:
    tympani, vestibuli, sp, origin = _common(st, sv)
    boundary = _largest(tympani & ndimage.binary_dilation(vestibuli))
    if boundary.sum() < 200:
        raise ValueError("the scalae barely meet: no boundary to follow")
    idx, graph = _voxel_graph(boundary, sp)
    pts = origin + idx * sp
    centre = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - centre, full_matrices=False)
    axis = vt[2]

    def radius(p):
        rel = p - centre
        return np.linalg.norm(rel - np.outer(rel @ axis, axis), axis=1)

    g0 = dijkstra(graph, indices=0)
    e1 = int(np.argmax(np.where(np.isfinite(g0), g0, -1)))
    g1 = dijkstra(graph, indices=e1)
    e2 = int(np.argmax(np.where(np.isfinite(g1), g1, -1)))
    base = e1 if radius(pts[[e1]])[0] > radius(pts[[e2]])[0] else e2
    g = dijkstra(graph, indices=base)
    ok = np.isfinite(g)
    r = radius(pts)
    step = 0.3
    bins = np.floor(np.where(ok, g, 0) / step).astype(int)
    path = []
    for k in range(int(bins[ok].max()) + 1):
        m = ok & (bins == k)
        if m.sum() < 3:
            continue
        rr = r[m]
        path.append(pts[m][rr >= np.percentile(rr, 85)].mean(axis=0))
    path = np.array(path)
    if len(path) < 20:
        raise ValueError("boundary too short to follow")
    path = np.stack([gaussian_filter1d(path[:, i], 2, mode="nearest") for i in range(3)], axis=1)
    # Towards the scala vestibuli: the duct lies on that side of the basilar membrane.
    sv_centre = origin + np.argwhere(vestibuli).mean(axis=0) * sp
    st_centre = origin + np.argwhere(tympani).mean(axis=0) * sp
    toward = sv_centre - st_centre
    toward /= np.linalg.norm(toward)
    path = path + 0.15 * toward
    length = float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum())
    mask, lo = _tube(_densify(path, GRID_MM / 2), DUCT_RADIUS_MM)
    return (mask, lo), {"path_points": len(path), "path_length_mm": round(length, 1)}


def _prune(skel: np.ndarray, spur_voxels: int) -> np.ndarray:
    """Remove end branches shorter than `spur_voxels` by peeling end points that many times,
    then growing the surviving branches back along the original skeleton."""
    s = skel.copy()
    kernel = np.ones((3, 3, 3), int)
    kernel[1, 1, 1] = 0
    for _ in range(spur_voxels):
        neighbours = ndimage.convolve(s.astype(int), kernel, mode="constant")
        s &= ~(s & (neighbours <= 1))
    for _ in range(spur_voxels):
        s |= ndimage.binary_dilation(s, structure=np.ones((3, 3, 3))) & skel
    return s


def semicircular_ducts(vestibular, vestibule_centre) -> tuple[tuple, dict]:
    mask, spacing, origin = vestibular
    sp = np.asarray(spacing, float)
    origin = np.asarray(origin, float)
    grid = origin + np.stack(np.indices(mask.shape), axis=-1) * sp
    canals = mask & (np.linalg.norm(grid - np.asarray(vestibule_centre), axis=-1) > CANAL_FROM_CENTRE_MM)
    canals = ndimage.binary_opening(canals, iterations=1)
    if canals.sum() * np.prod(sp) < 3.0:
        raise ValueError("too little canal beyond the vestibule")
    skel = skeletonize(canals)
    skel = _prune(skel, round(1.0 / float(sp.min())))
    pts = origin + np.argwhere(skel) * sp
    if len(pts) < 30:
        raise ValueError("canal centre lines not found")
    # Join each skeleton voxel to its neighbours at the fine grid by a tube around every point.
    dense = []
    idx = np.argwhere(skel)
    lookup = {tuple(v) for v in idx}
    for v in idx:
        for o in np.ndindex(3, 3, 3):
            w = tuple(v + np.array(o) - 1)
            if w != tuple(v) and w in lookup:
                a = origin + v * sp
                b = origin + np.array(w) * sp
                dense.extend(a + (b - a) * t for t in np.linspace(0, 1, 4))
    dense = np.array(dense) if dense else pts
    tube, lo = _tube(dense, SCC_DUCT_RADIUS_MM)
    return (tube, lo), {"centre_line_mm": round(len(idx) * float(sp.mean()), 1)}


def _ellipsoid(centre, axes_dirs, semi_axes, clip) -> tuple[np.ndarray, tuple[float, float, float]]:
    reach = max(semi_axes) + 2 * GRID_MM
    lo = np.asarray(centre) - reach
    n = int(np.ceil(2 * reach / GRID_MM)) + 1
    g = lo + np.stack(np.indices((n, n, n)), axis=-1) * GRID_MM
    rel = g - centre
    inside = np.zeros((n, n, n), bool)
    s = sum(((rel @ d) / a) ** 2 for d, a in zip(axes_dirs, semi_axes))
    inside = s <= 1.0
    cmask, csp, corg = clip
    ci = np.rint((g - np.asarray(corg)) / np.asarray(csp)).astype(int)
    valid = (ci >= 0).all(axis=-1) & (ci < np.array(cmask.shape)).all(axis=-1)
    inside &= valid
    inside[valid] &= cmask[tuple(ci[valid].T)]
    return inside, tuple(float(v) for v in lo)


def vestibular_sacs(vestibular, vestibule_centre, cochlea_centre, frame) -> tuple[dict, dict]:
    mask, spacing, origin = vestibular
    sp = np.asarray(spacing, float)
    origin = np.asarray(origin, float)
    grid_pts = origin + np.argwhere(mask) * sp
    vc = np.asarray(vestibule_centre, float)
    far = np.linalg.norm(grid_pts - vc, axis=1) > CANAL_FROM_CENTRE_MM
    if far.sum() < 50:
        raise ValueError("no canals to place the utricle by")
    to_canals = grid_pts[far].mean(axis=0) - vc
    to_canals /= np.linalg.norm(to_canals)
    to_cochlea = np.asarray(cochlea_centre, float) - vc
    to_cochlea /= np.linalg.norm(to_cochlea)
    # The vestibule shrunk by 0.1 mm keeps both sacs off the bony wall.
    inner = ndimage.binary_erosion(mask, iterations=1)
    clip = (inner, sp, origin)
    sup, ant, lat = frame.superior, frame.anterior, frame.lateral
    utricle = _ellipsoid(vc + 0.8 * to_canals, (ant, sup, lat), (1.3, 0.8, 0.6), clip)
    saccule = _ellipsoid(vc + 1.0 * to_cochlea, (ant, sup, lat), (0.6, 0.9, 0.3), clip)
    v = GRID_MM**3
    report = {
        "utricle_mm3": round(float(utricle[0].sum() * v), 2),
        "saccule_mm3": round(float(saccule[0].sum() * v), 2),
    }
    if utricle[0].sum() * v < 0.2 or saccule[0].sum() * v < 0.05:
        raise ValueError(f"the sacs barely fit inside the vestibule: {report}")
    return {"utricle": utricle, "saccule": saccule}, report


def vestibule_centre(vestibular) -> np.ndarray:
    """The deepest point of the vestibular label: the middle of the vestibule, not pulled
    towards the canals as the label's centroid is."""
    mask, spacing, origin = vestibular
    depth = ndimage.distance_transform_edt(mask, sampling=spacing)
    return np.asarray(origin, float) + np.array(np.unravel_index(np.argmax(depth), depth.shape)) * np.asarray(spacing)


def build(st, sv, vestibular, frame) -> Membranous:
    """Every part that can be placed; a part whose rule fails is left out and reported."""
    centre = vestibule_centre(vestibular)
    cochlea = np.asarray(st[2], float) + np.argwhere(st[0]).mean(axis=0) * np.asarray(st[1], float)
    parts, report = {}, {"rule": "otopipe/membranous.py", "grid_mm": GRID_MM}
    try:
        parts["cochlear_duct"], report["cochlear_duct"] = cochlear_duct(st, sv)
    except ValueError as e:
        report["cochlear_duct"] = {"left_out": str(e)}
    try:
        parts["semicircular_ducts"], report["semicircular_ducts"] = semicircular_ducts(vestibular, centre)
    except ValueError as e:
        report["semicircular_ducts"] = {"left_out": str(e)}
    try:
        sacs, report["sacs"] = vestibular_sacs(vestibular, centre, cochlea, frame)
        parts.update(sacs)
    except ValueError as e:
        report["sacs"] = {"left_out": str(e)}
    return Membranous(parts, report)
