"""Quadrants of the tympanic membrane, computed from the specimen's own labels.

Clinically the membrane is divided by a line along the handle of the malleus and a line
at right angles to it through the umbo, into anterosuperior, anteroinferior,
posterosuperior and posteroinferior quadrants. Here:

- the membrane's plane is the best-fit plane of its label;
- the umbo is the point of the malleus label nearest the membrane's centre;
- "superior" is the malleus's long axis, projected onto that plane and pointing from
  the umbo towards the bulk of the malleus (its head);
- "anterior" is the direction from the vestibule to the cochlea, projected onto the
  plane: the cochlea lies anterior to the vestibule in every ear, so no side or scanner
  orientation is needed.

The division is computed by rule, not drawn by an expert; the reviewer checks it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

QUADRANTS = ("anterosuperior", "anteroinferior", "posterosuperior", "posteroinferior")


@dataclass(frozen=True)
class Quadrants:
    parts: dict[str, tuple[np.ndarray, tuple[float, float, float]]]  # name -> (mask, origin)
    report: dict


def _points(mask, spacing, origin) -> np.ndarray:
    return np.asarray(origin) + np.argwhere(mask) * np.asarray(spacing)


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n < 1e-9:
        raise ValueError("degenerate direction")
    return v / n


def tympanic_quadrants(tm, malleus, cochlea_centre, vestibule_centre) -> Quadrants:
    """`tm` and `malleus` are (mask, spacing, origin); the centres are millimetre points."""
    mask, spacing, origin = tm
    p = _points(mask, spacing, origin)
    centre = p.mean(axis=0)
    # Best-fit plane: the normal is the direction of least spread.
    _, _, vt = np.linalg.svd(p - centre, full_matrices=False)
    normal = vt[2]

    m = _points(*malleus)
    umbo = m[np.argmin(np.linalg.norm(m - centre, axis=1))]
    _, _, mvt = np.linalg.svd(m - m.mean(axis=0), full_matrices=False)
    axis = mvt[0]
    if np.dot(m.mean(axis=0) - umbo, axis) < 0:
        axis = -axis
    superior = _unit(axis - np.dot(axis, normal) * normal)

    ahead = np.asarray(cochlea_centre, float) - np.asarray(vestibule_centre, float)
    ahead = ahead - np.dot(ahead, normal) * normal
    anterior = _unit(ahead - np.dot(ahead, superior) * superior)

    d = p - umbo
    up = d @ superior
    fwd = d @ anterior
    choose = {
        "anterosuperior": (fwd >= 0) & (up >= 0),
        "anteroinferior": (fwd >= 0) & (up < 0),
        "posterosuperior": (fwd < 0) & (up >= 0),
        "posteroinferior": (fwd < 0) & (up < 0),
    }
    idx = np.argwhere(mask)
    sp = np.asarray(spacing)
    parts = {}
    for name, sel in choose.items():
        if not sel.any():
            raise ValueError(f"the {name} quadrant is empty")
        q = idx[sel]
        lo, hi = q.min(axis=0), q.max(axis=0) + 1
        sub = np.zeros(tuple(hi - lo), dtype=bool)
        sub[tuple((q - lo).T)] = True
        parts[name] = (sub, tuple(float(v) for v in np.asarray(origin) + lo * sp))

    voxel = float(np.prod(sp))
    report = {
        "method": "plane of best fit; umbo = malleus point nearest the membrane centre; "
        "superior along the malleus axis; anterior from vestibule to cochlea",
        "umbo_mm": [round(float(v), 3) for v in umbo],
        # Diameters across the membrane along and across the handle, from the label's extent.
        "vertical_diameter_mm": round(float(up.max() - up.min()), 2),
        "horizontal_diameter_mm": round(float(fwd.max() - fwd.min()), 2),
        "angle_handle_to_plane_deg": round(float(np.degrees(np.arcsin(min(1.0, abs(np.dot(axis, normal)))))), 1),
        "area_share": {k: round(float(v.sum()) * voxel / (mask.sum() * voxel), 3) for k, v in choose.items()},
    }
    return Quadrants(parts, report)
