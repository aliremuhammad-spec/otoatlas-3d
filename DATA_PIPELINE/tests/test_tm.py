"""Tympanic membrane quadrants on a phantom with known orientation."""
import numpy as np
import pytest

from otopipe import tm

SP = (0.1, 0.1, 0.1)


def test_quadrants_follow_the_handle_and_the_cochlea_side():
    # Membrane: a disc of radius 4 mm in the plane z = 0 (two voxels thick).
    n = 100
    x, y = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    disc2d = (x - 50) ** 2 + (y - 50) ** 2 <= 40**2
    tm_mask = np.repeat(disc2d[:, :, None], 2, axis=2)
    tm_origin = (-5.0, -5.0, 0.0)
    # Malleus: a handle from the centre up along +y, then a heavy head at +y, just medial (z > 0).
    mal = np.zeros((20, 80, 20), bool)
    mal[9:11, 0:60, 3:5] = True  # handle, starting at the umbo
    mal[5:15, 60:80, 3:13] = True  # head
    mal_origin = (-1.0, 0.0, 0.0)
    q = tm.tympanic_quadrants(
        (tm_mask, SP, tm_origin), (mal, SP, mal_origin), cochlea_centre=(6.0, 0.0, 3.0), vestibule_centre=(-6.0, 0.0, 3.0)
    )
    centre = lambda name: np.asarray(q.parts[name][1]) + np.array(q.parts[name][0].shape) * 0.1 / 2  # noqa: E731
    assert centre("anterosuperior")[0] > 0 and centre("anterosuperior")[1] > 0
    assert centre("anteroinferior")[0] > 0 and centre("anteroinferior")[1] < 0
    assert centre("posterosuperior")[0] < 0 and centre("posterosuperior")[1] > 0
    assert centre("posteroinferior")[0] < 0 and centre("posteroinferior")[1] < 0
    assert q.report["vertical_diameter_mm"] == pytest.approx(8.0, abs=0.3)
    assert sum(q.report["area_share"].values()) == pytest.approx(1.0)
    assert sum(int(p[0].sum()) for p in q.parts.values()) == int(tm_mask.sum())
