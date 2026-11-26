"""The facial nerve label divided at the second genu, computed from the specimen's own label.

In the OpenEar labels the facial nerve runs from the geniculate region (in some specimens a
little of the labyrinthine segment) through the tympanic segment and the second genu, and
down the mastoid segment to within a few millimetres of the stylomastoid foramen. Checked
on ALPHA, ETA and ZETA by straightening the registered CBCT along the label: the label's
lower part lies in the dark canal through the mastoid bone all the way.

Rule, nothing drawn by hand:
- centreline: the shortest path inside the label from its most medial voxel to its lowest
  voxel (frame.superior), with steps near the label's surface made dearer so the path keeps
  to the middle; resampled every 0.5 mm and smoothed;
- mastoid direction: the centreline's direction from 12 mm to 2 mm above its lower end
  (the last 2 mm can hook as the nerve leaves the bone);
- tympanic angle: the median angle between the centreline and the mastoid direction,
  20 to 26 mm above the lower end (the tympanic segment);
- second genu: going up from 2.5 mm above the lower end, the first point where the angle
  reaches half the tympanic angle, so the boundary sits in the middle of the bend;
- each voxel goes to the part of its nearest centreline point.

Checks stop the division when the rule clearly failed; the nerve then ships whole.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from . import ossicles

STEP_MM = 0.5
MIN_MASTOID_MM = 8.0
MAX_MASTOID_MM = 25.0
MIN_TYMPANIC_ANGLE = 35.0
PARTS = ("tympanic", "mastoid")


@dataclass
class Division:
    parts: dict[str, tuple[np.ndarray, tuple[float, float, float]]]  # name -> (mask, origin)
    centreline: np.ndarray  # (n, 3) millimetres, from the medial end to the lower end
    genu_index: int
    report: dict = field(default_factory=dict)


def centreline(label, frame) -> np.ndarray:
    """Points every STEP_MM along the middle of the label, medial end first."""
    mask, spacing, origin = label
    sp = np.asarray(spacing, float)
    vox, graph = ossicles._voxel_graph(mask, sp)
    if len(vox) < 50:
        raise ValueError("facial nerve label too small")
    depth = ndimage.distance_transform_edt(mask, sampling=sp)[tuple(vox.T)]
    g = graph.tocoo()
    floor = 0.5 * float(sp.min())
    w = g.data * (1.0 + 0.3 / np.maximum(depth[g.row], floor) + 0.3 / np.maximum(depth[g.col], floor))
    graph = coo_matrix((w, (g.row, g.col)), shape=g.shape).tocsr()
    pts = np.asarray(origin, float) + vox * sp
    rel = pts - frame.umbo
    start = int(np.argmin(rel @ frame.lateral))
    end = int(np.argmin(rel @ frame.superior))
    dist, pred = dijkstra(graph, indices=start, return_predecessors=True)
    if not np.isfinite(dist[end]):
        raise ValueError("facial nerve label is in pieces between its medial and lower ends")
    chain = [end]
    while chain[-1] != start:
        chain.append(int(pred[chain[-1]]))
    path = pts[chain[::-1]]
    along = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    t = np.arange(0.0, along[-1], STEP_MM)
    line = np.stack([np.interp(t, along, path[:, i]) for i in range(3)], axis=1)
    return ndimage.gaussian_filter1d(line, 2.0, axis=0, mode="nearest")


def second_genu(line: np.ndarray) -> tuple[int, float]:
    """Index of the second genu on the centreline, and the tympanic angle in degrees."""
    n = len(line)
    per_mm = int(round(1.0 / STEP_MM))
    if n < 27 * per_mm:
        raise ValueError(f"facial nerve centreline only {(n - 1) * STEP_MM:.1f} mm long")
    tangent = np.gradient(line, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    down = line[-1 - 2 * per_mm] - line[-1 - 12 * per_mm]
    down /= np.linalg.norm(down)
    angle = np.degrees(np.arccos(np.clip(tangent @ down, -1.0, 1.0)))
    tympanic = float(np.median(angle[n - 1 - 26 * per_mm : n - 20 * per_mm]))
    i = n - 1 - int(round(2.5 * per_mm))
    while i > 0 and angle[i] < tympanic / 2:
        i -= 1
    return i + 1, tympanic


def divide(label, frame) -> Division:
    mask, spacing, origin = label
    line = centreline(label, frame)
    genu, tympanic_angle = second_genu(line)
    mastoid_mm = (len(line) - 1 - genu) * STEP_MM
    if tympanic_angle < MIN_TYMPANIC_ANGLE:
        raise ValueError(f"no clear second genu (tympanic angle {tympanic_angle:.0f} degrees)")
    if not MIN_MASTOID_MM <= mastoid_mm <= MAX_MASTOID_MM:
        raise ValueError(f"mastoid part {mastoid_mm:.1f} mm long, outside {MIN_MASTOID_MM}-{MAX_MASTOID_MM} mm")
    vox = np.argwhere(mask)
    pts = np.asarray(origin, float) + vox * np.asarray(spacing, float)
    _, nearest = cKDTree(line).query(pts)
    lower = nearest >= genu
    parts = {}
    for name, keep in (("tympanic", ~lower), ("mastoid", lower)):
        part = np.zeros_like(mask, dtype=bool)
        part[tuple(vox[keep].T)] = True
        parts[name] = (part, tuple(float(v) for v in origin))
    if not parts["mastoid"][0].any() or not parts["tympanic"][0].any():
        raise ValueError("one part of the facial nerve came out empty")
    rel = line[genu] - frame.umbo
    report = {
        "centreline_mm": round((len(line) - 1) * STEP_MM, 1),
        "mastoid_segment_mm": round(mastoid_mm, 1),
        "tympanic_angle_deg": round(tympanic_angle),
        "genu_from_umbo_mm": {
            "lateral": round(float(rel @ frame.lateral), 1),
            "anterior": round(float(rel @ frame.anterior), 1),
            "superior": round(float(rel @ frame.superior), 1),
        },
        "lower_end_below_umbo_mm": round(float(-(line[-1] - frame.umbo) @ frame.superior), 1),
    }
    return Division(parts, line, genu, report)
