"""Cochlear A and B values, measured on a specimen's bony labyrinth label.

In the plane of the basal turn (perpendicular to the cochlear axis, through the
modiolus centre C):
- A is the distance from the round window, through the modiolus, to the lateral wall
  of the basal turn on the far side;
- B is the width of the basal turn at right angles to A, through C.

These are the inputs of the published estimation formulas for cochlear duct length;
which formula the app shows is left to the reviewer. The label is sampled every
0.01 mm along each line, so the result is limited by the label's voxel size, not by
the sampling.
"""
from __future__ import annotations

import numpy as np

STEP_MM = 0.01


def _runs(inside: np.ndarray) -> list[tuple[int, int]]:
    """Start and end indices (inclusive) of each run of True."""
    edges = np.flatnonzero(np.diff(np.concatenate(([0], inside.astype(np.int8), [0]))))
    return [(int(a), int(b) - 1) for a, b in zip(edges[::2], edges[1::2])]


def _inside(mask, spacing, origin, points) -> np.ndarray:
    idx = np.rint((points - np.asarray(origin)) / np.asarray(spacing)).astype(int)
    ok = np.all((idx >= 0) & (idx < np.array(mask.shape)), axis=1)
    out = np.zeros(len(points), dtype=bool)
    out[ok] = mask[tuple(idx[ok].T)]
    return out


def a_and_b(mask, spacing, origin, centre, axis, round_window) -> dict:
    """A and B values in mm; `centre`, `axis` (towards the apex) and `round_window` in mm."""
    c = np.asarray(centre, float)
    z = np.asarray(axis, float) / np.linalg.norm(axis)
    rw = np.asarray(round_window, float)
    rw_plane = rw - np.dot(rw - c, z) * z
    d = c - rw_plane
    d /= np.linalg.norm(d)
    e = np.cross(z, d)

    t = np.arange(-1.0, 14.0, STEP_MM)
    along = _inside(mask, spacing, origin, rw_plane + t[:, None] * d)
    runs = _runs(along)
    if not runs:
        raise ValueError("the line from the round window does not cross the labyrinth")
    first = min(runs, key=lambda r: abs(t[r[0]]) if t[r[0]] > 0 else 0.0 if t[r[1]] >= 0 else abs(t[r[1]]))
    a_start = t[first[0]]
    a_end = t[runs[-1][1]]

    s = np.arange(-8.0, 8.0, STEP_MM)
    across = _inside(mask, spacing, origin, c + s[:, None] * e)
    if not across.any():
        raise ValueError("the line across the modiolus does not cross the labyrinth")
    b = s[np.flatnonzero(across)[-1]] - s[np.flatnonzero(across)[0]]
    return {
        "cochlear_a_value": round(float(a_end - a_start), 2),
        "cochlear_b_value": round(float(b), 2),
        "method": "basal-turn plane through the modiolus centre; label sampled every 0.01 mm",
    }
