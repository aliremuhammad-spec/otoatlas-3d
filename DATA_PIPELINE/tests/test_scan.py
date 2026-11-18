"""Packaging a specimen scan: axes, cropping, windowing and the file layout."""
import gzip

import numpy as np
import pytest

from otopipe import scan


def test_negative_axes_are_flipped_and_the_origin_moves_to_the_new_first_voxel():
    data = np.arange(24).reshape(2, 3, 4)
    v = scan.to_positive_axes(data, (-0.5, 0.25, 1.0), (10.0, 0.0, 0.0))
    assert v.spacing == (0.5, 0.25, 1.0)
    assert v.origin == pytest.approx((9.5, 0.0, 0.0))
    # The voxel at x = 9.5 mm was the second one along x before the flip.
    assert v.data[0, 0, 0] == data[1, 0, 0]


def test_crop_keeps_voxel_centres_inside_the_box_and_reports_their_origin():
    v = scan.Volume(np.zeros((10, 10, 10)), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
    c = scan.crop(v, (2.0, -5.0, 8.5), (4.0, 3.0, 20.0))
    assert c.data.shape == (3, 4, 2)
    assert c.origin[0] == pytest.approx(2.0) and c.origin[1] == pytest.approx(0.0)
    with pytest.raises(ValueError):
        scan.crop(v, (20.0, 20.0, 20.0), (30.0, 30.0, 30.0))


def test_window_spans_the_range_and_the_file_is_x_fastest(tmp_path):
    data = np.zeros((4, 3, 2), dtype=np.int16)
    data[3, 0, 0] = 1000
    data[0, 2, 1] = 500
    v = scan.Volume(data, (0.1, 0.1, 0.1), (1.0, 2.0, 3.0))
    entry = scan.write_scan(tmp_path, v, "CBCT", "test")
    assert entry["shape"] == [4, 3, 2]
    raw = np.frombuffer(gzip.open(tmp_path / scan.SCAN_FILE).read(), dtype=np.uint8)
    assert raw.size == 24
    grid = raw.reshape(2, 3, 4)  # z, y, x
    assert grid[0, 0, 3] == 255  # x = 3 is the brightest voxel
    assert grid[1, 2, 0] > 0
    assert entry["window"]["high"] > entry["window"]["low"]


def test_box_around_adds_the_margin_to_every_label():
    m = np.zeros((5, 5, 5), bool)
    m[1:3, 1:3, 1:3] = True
    lo, hi = scan.box_around([(m, (0.5, 0.5, 0.5), (10.0, 0.0, 0.0))], 1.0)
    assert lo == pytest.approx((9.5, -0.5, -0.5))
    assert hi == pytest.approx((12.0, 2.0, 2.0))
