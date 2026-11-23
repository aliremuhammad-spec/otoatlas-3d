"""Air spaces on a phantom block: bone with round cells, an 'ossicle' in one of them, a
notch cut into the block's outside, and a scan where bone is bright and epoxy is grey."""
import numpy as np
import pytest

from otopipe import pneumatization as PN

SP = (0.125, 0.125, 0.125)


def _phantom():
    n = 160  # 20 mm
    x, y, z = np.meshgrid(*(np.arange(n) * 0.125,) * 3, indexing="ij")
    bone = np.zeros((n, n, n), bool)
    bone[16:144, 16:144, 16:144] = True  # a 16 mm block
    bone[16:60, 16:60, :] = False  # a notch cut into its outside, through its whole height

    def ball(c, r):
        return (x - c[0]) ** 2 + (y - c[1]) ** 2 + (z - c[2]) ** 2 <= r * r

    middle = ball((12, 12, 10), 2.5)  # the 'tympanic cavity'
    cell_a = ball((12, 6, 6), 1.2)
    cell_b = ball((8, 14, 14), 1.0)
    bone &= ~(middle | cell_a | cell_b)
    ossicle = ball((12, 12, 10), 0.8)
    ct = np.full((n, n, n), 115, np.uint8)  # epoxy
    ct[bone] = 230
    ct[:4] = 0  # outside the scanned field
    return bone, ossicle, ct, middle, cell_a, cell_b


def test_cavity_and_cells_are_found_and_the_notch_is_not():
    bone, ossicle, ct, middle, cell_a, cell_b = _phantom()
    r = PN.air_spaces((bone, SP, (0, 0, 0)), [], [(ossicle, SP, (0, 0, 0))], (ct, SP, (0, 0, 0)))
    v_middle = (middle.sum() - ossicle.sum()) * 0.125**3 / 1000
    v_cells = (cell_a.sum() + cell_b.sum()) * 0.125**3 / 1000
    assert r.report["tympanic_cavity_ml"] == pytest.approx(v_middle, rel=0.25)
    assert r.report["air_cells_ml"] == pytest.approx(v_cells, rel=0.3)
    # The notch (about 5.5 x 5.5 x 20 mm of epoxy outside the bone) is not counted.
    assert r.report["air_space_ml"] < v_middle + v_cells + 0.01


def test_no_scan_overlap_is_an_error():
    bone, ossicle, ct, *_ = _phantom()
    with pytest.raises(ValueError):
        PN.air_spaces((bone, SP, (0, 0, 0)), [], [(ossicle, SP, (0, 0, 0))], (np.zeros_like(ct), SP, (0, 0, 0)))
