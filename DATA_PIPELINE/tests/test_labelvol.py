import numpy as np
import pytest

from otopipe import labelvol as L


def box(shape, lo, hi):
    m = np.zeros(shape, bool)
    m[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]] = True
    return m


def at(vol: L.LabelVolume, p):
    """Value at the position p (mm) of the volume (array is [z, y, x])."""
    i = [int(round((p[k] - vol.origin_mm[k]) / vol.spacing_mm)) for k in range(3)]
    nz, ny, nx = vol.data.shape
    if not (0 <= i[0] < nx and 0 <= i[1] < ny and 0 <= i[2] < nz):
        return 0  # outside the cropped volume
    return int(vol.data[i[2], i[1], i[0]])


def test_voxel_centres_line_up_across_different_grids():
    # A 10 mm cube on a 0.25 mm grid starting at x=2 mm, and a thin plate on a 0.125 mm grid inside it.
    big = L.Item("bone", box((60, 60, 60), (0, 0, 0), (40, 40, 40)), (0.25,) * 3, (2.0, 3.0, 4.0))
    plate = L.Item("plate", box((80, 80, 80), (40, 40, 40), (48, 48, 48)), (0.125,) * 3, (5.0, 6.0, 7.0))
    vol = L.build([big, plate])
    vals = vol.values
    assert set(vals) == {"bone", "plate"}
    assert at(vol, (2.0, 3.0, 4.0)) == vals["bone"]  # first voxel centre of the big one
    assert at(vol, (11.5, 12.5, 13.5)) == vals["bone"]
    assert at(vol, (12.5, 13.5, 14.5)) == 0  # past the cube (40 voxels * 0.25 = 10 mm; last centre 11.75)
    # The plate is centred at 5 + 40 * 0.125 = 10 mm ... 10.875 mm; its own voxels win where they overlap the bone.
    assert at(vol, (10.0, 11.0, 12.0)) == vals["plate"]
    assert at(vol, (10.875, 11.875, 12.875)) == vals["plate"]
    assert at(vol, (9.75, 11.0, 12.0)) == vals["bone"]


def test_smaller_structure_wins_an_overlap_whatever_the_order():
    a = L.Item("a_large", box((20, 20, 20), (0, 0, 0), (20, 20, 20)), (0.125,) * 3, (0.0, 0.0, 0.0))
    b = L.Item("b_small", box((20, 20, 20), (5, 5, 5), (10, 10, 10)), (0.125,) * 3, (0.0, 0.0, 0.0))
    for items in ([a, b], [b, a]):
        vol = L.build(items)
        assert at(vol, (0.625, 0.625, 0.625)) == vol.values["b_small"]
        assert at(vol, (0.125, 0.125, 0.125)) == vol.values["a_large"]


def test_empty_masks_get_no_id_and_a_volume_of_nothing_is_refused():
    a = L.Item("a", box((10, 10, 10), (2, 2, 2), (5, 5, 5)), (0.125,) * 3, (1.0, 1.0, 1.0))
    e = L.Item("empty", np.zeros((10, 10, 10), bool), (0.125,) * 3, (0.0, 0.0, 0.0))
    vol = L.build([a, e])
    assert "empty" not in vol.values
    # The volume is cropped to what is there: a 3 voxel cube.
    assert vol.dims == (3, 3, 3)
    assert vol.origin_mm == pytest.approx((1.25, 1.25, 1.25))
    with pytest.raises(ValueError):
        L.build([e])


def test_too_many_structures_are_refused():
    m = box((4, 4, 4), (0, 0, 0), (2, 2, 2))
    with pytest.raises(ValueError, match="8-bit"):
        L.build([L.Item(f"s{i}", m, (0.125,) * 3, (0.0, 0.0, 0.0)) for i in range(256)])


def test_file_round_trip_and_manifest_block():
    a = L.Item("a", box((12, 9, 7), (1, 1, 1), (11, 8, 6)), (0.125,) * 3, (0.0, 0.0, 0.0))
    vol = L.build([a])
    blob = L.encode(vol)
    back = L.decode(blob, vol.dims)
    assert np.array_equal(back, vol.data)
    block = L.manifest_block(vol, blob, "labels.u8.gz", ["membranous_x"])
    assert block["dims"] == list(vol.dims)
    assert block["structures"] == [{"id": "a", "value": 1}]
    assert block["excluded_schematic"] == ["membranous_x"]
    assert block["bytes"] == len(blob)
