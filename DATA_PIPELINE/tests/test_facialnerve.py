"""The facial nerve divides at the middle of its second bend, on a synthetic nerve of known shape."""
import numpy as np
import pytest

from otopipe import facialnerve
from otopipe.ossicles import Frame

SP = 0.2


def tube(points, radius=0.6, pad=2.0):
    lo = points.min(axis=0) - pad
    shape = np.ceil((points.max(axis=0) + pad - lo) / SP).astype(int)
    grid = np.stack(np.meshgrid(*[np.arange(n) * SP for n in shape], indexing="ij"), axis=-1) + lo
    mask = np.zeros(shape, bool)
    for p in points:
        mask |= np.linalg.norm(grid - p, axis=-1) <= radius
    return mask, (SP, SP, SP), tuple(lo)


FRAME = Frame(lateral=np.array([1.0, 0, 0]), anterior=np.array([0, 1.0, 0]), superior=np.array([0, 0, 1.0]),
              side="right", umbo=np.zeros(3))


def nerve(tympanic_mm=16.0, mastoid_mm=15.0, bend_radius=2.0):
    """Medial start, tympanic part running back (-anterior) and slightly down and out, a quarter-circle
    bend, then the mastoid part running down. Returns the points and the bend's middle."""
    t = np.linspace(0, tympanic_mm, int(tympanic_mm / 0.25))
    tymp = np.stack([-6 + 0.1 * t, 5 - t, 4 - 0.15 * t], axis=1)
    end = tymp[-1]
    a = np.linspace(0, np.pi / 2, 20)
    centre = end + np.array([0, 0, -bend_radius])
    bend = np.stack([np.full_like(a, end[0]), centre[1] - bend_radius * np.sin(a), centre[2] + bend_radius * np.cos(a)], axis=1)
    s = np.linspace(0, mastoid_mm, int(mastoid_mm / 0.25))
    start = bend[-1]
    mast = np.stack([start[0] + 0.1 * s, np.full_like(s, start[1]), start[2] - s], axis=1)
    return np.vstack([tymp, bend, mast]), bend[len(bend) // 2]


def test_divides_in_the_middle_of_the_bend():
    pts, middle = nerve()
    d = facialnerve.divide(tube(pts[::2]), FRAME)
    genu = d.centreline[d.genu_index]
    assert np.linalg.norm(genu - middle) < 1.5
    assert 13.0 <= d.report["mastoid_segment_mm"] <= 18.0
    assert d.report["tympanic_angle_deg"] > 60
    assert set(d.parts) == {"tympanic", "mastoid"}
    lows = {k: (np.argwhere(m)[:, 2] * SP + o[2]).mean() for k, (m, o) in d.parts.items()}
    assert lows["mastoid"] < lows["tympanic"]


def test_a_straight_label_is_not_divided():
    t = np.linspace(0, 30, 120)
    pts = np.stack([np.zeros_like(t), -t * 0.2, 5 - t], axis=1)
    with pytest.raises(ValueError):
        facialnerve.divide(tube(pts[::2]), FRAME)
