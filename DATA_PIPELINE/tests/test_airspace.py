"""The middle ear air space, on a phantom block of bone with known cavities."""
import numpy as np
import pytest

from otopipe import airspace

SP = (0.25, 0.25, 0.25)


def ball(shape, centre, r):
    z, y, x = np.indices(shape)
    return (z - centre[0]) ** 2 + (y - centre[1]) ** 2 + (x - centre[2]) ** 2 <= r * r


def test_keeps_the_cavity_around_the_ossicle_and_its_narrow_outlet_but_not_other_spaces():
    shape = (80, 80, 80)
    bone = np.ones(shape, bool)
    cavity = ball(shape, (40, 40, 40), 10)  # 2.5 mm radius "tympanic cavity"
    cell = ball(shape, (40, 40, 66), 4)  # a separate closed "air cell", not touching the ossicle
    tunnel = np.zeros(shape, bool)
    tunnel[39:42, 39:42, 0:40] = True  # 0.75 mm wide outlet to the block face (like a tube)
    bone &= ~(cavity | cell | tunnel)
    ossicle = ball(shape, (40, 40, 40), 3)
    bone &= ~ossicle
    result = airspace.middle_ear_air(
        (bone, SP, (0.0, 0.0, 0.0)),
        [(ossicle, SP, (0.0, 0.0, 0.0))],
        [(ossicle, SP, (0.0, 0.0, 0.0))],
        closing_mm=1.5,
    )
    expected = (cavity & ~ossicle).sum() * 0.25**3
    # The cavity is kept (the tunnel's sealed part may add a little), the separate cell is not.
    assert result.report["volume_mm3"] == pytest.approx(expected, rel=0.15)
    assert result.report["pieces_dropped"] >= 1
    # Nothing kept lies in the separate cell.
    origin = np.round(np.asarray(result.origin) / 0.25).astype(int)
    full = np.zeros(shape, bool)
    full[origin[0] : origin[0] + result.mask.shape[0], origin[1] : origin[1] + result.mask.shape[1],
         origin[2] : origin[2] + result.mask.shape[2]] = result.mask
    assert not (full & cell).any()


def test_refuses_when_no_ossicle_is_given():
    bone = np.ones((20, 20, 20), bool)
    with pytest.raises(ValueError):
        airspace.middle_ear_air((bone, SP, (0, 0, 0)), [], [(np.zeros((2, 2, 2), bool), SP, (0, 0, 0))])


def test_with_the_scan_only_dark_voxels_count_as_air():
    from otopipe.scan import Volume

    shape = (60, 60, 60)
    bone = np.ones(shape, bool)
    cavity = ball(shape, (30, 30, 30), 12)
    bone &= ~cavity
    ossicle = ball(shape, (30, 30, 30), 3)
    bone &= ~ossicle
    ct = np.full(shape, 1500.0)  # bone
    ct[cavity] = -900.0  # air
    tissue = cavity & (np.indices(shape)[2] > 36)  # one side of the cavity is soft tissue
    ct[tissue] = 40.0
    result = airspace.middle_ear_air(
        (bone, SP, (0.0, 0.0, 0.0)),
        [(ossicle, SP, (0.0, 0.0, 0.0))],
        [(ossicle, SP, (0.0, 0.0, 0.0))],
        closing_mm=1.5,
        ct=Volume(ct, SP, (0.0, 0.0, 0.0)),
    )
    expected = (cavity & ~ossicle & ~tissue).sum() * 0.25**3
    assert result.report["volume_mm3"] == pytest.approx(expected, rel=0.05)
    assert -900 < result.report["ct_air_threshold"] < 40
