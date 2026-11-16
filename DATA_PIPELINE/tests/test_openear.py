"""OpenEar segmentation reader, tested on a synthetic file with the real header layout."""
import numpy as np
import nrrd
import pytest

from otopipe import mesh as M
from otopipe.openear import EXPECTED_SEGMENTS, read_segmentation


def write_seg(path, layers, names, space="right-anterior-superior", origin=(-17.3, -7.4, -0.1), step=0.125):
    header = {
        "space": space,
        "kinds": ["list", "domain", "domain", "domain"],
        "space directions": np.array([[np.nan] * 3, [step, 0, 0], [0, step, 0], [0, 0, step]]),
        "space origin": np.array(origin),
        "encoding": "gzip",
    }
    for i, name in enumerate(names):
        header[f"Segment{i}_Name"] = name
    nrrd.write(str(path), np.stack(layers).astype(np.uint8), header, index_order="F")


def ball(shape, centre, radius_vox):
    g = np.indices(shape)
    return sum((g[i] - centre[i]) ** 2 for i in range(3)) <= radius_vox**2


def test_reads_named_segments_cropped_and_positioned_in_millimetres(tmp_path):
    shape = (60, 50, 40)
    a = ball(shape, (20, 25, 20), 8)  # 1.0 mm radius at 0.125 mm
    b = ball(shape, (45, 20, 15), 4)
    path = tmp_path / "Segmentation.seg.nrrd"
    write_seg(path, [a, b], ["Malleus", "Incus"])
    segs = read_segmentation(str(path))
    assert set(segs) == {"Malleus", "Incus"}
    m = segs["Malleus"]
    assert m.mask.shape == (17, 17, 17)
    assert m.spacing == pytest.approx((0.125, 0.125, 0.125))
    surface = M.label_surface(m.mask, m.spacing, m.origin)
    expected_centre = np.array([-17.3, -7.4, -0.1]) + 0.125 * np.array([20, 25, 20])
    assert np.allclose(surface.centroid, expected_centre, atol=0.01)
    assert np.allclose(surface.bounds[1] - surface.bounds[0], 2.0, atol=0.125)


def test_left_posterior_superior_files_are_converted_to_the_same_frame(tmp_path):
    shape = (40, 40, 40)
    a = ball(shape, (10, 12, 20), 5)
    ras, lps = tmp_path / "ras.seg.nrrd", tmp_path / "lps.seg.nrrd"
    write_seg(ras, [a], ["Stapes"], origin=(5.0, 6.0, 7.0))
    # The same physical volume stored in LPS: x and y axes and origin change sign.
    header_step = -0.125
    header = {
        "space": "left-posterior-superior",
        "kinds": ["list", "domain", "domain", "domain"],
        "space directions": np.array([[np.nan] * 3, [header_step, 0, 0], [0, header_step, 0], [0, 0, 0.125]]),
        "space origin": np.array([-5.0, -6.0, 7.0]),
        "encoding": "gzip",
        "Segment0_Name": "Stapes",
    }
    nrrd.write(str(lps), a[None].astype(np.uint8), header, index_order="F")
    s1, s2 = read_segmentation(str(ras))["Stapes"], read_segmentation(str(lps))["Stapes"]
    assert np.allclose(s1.origin, s2.origin)
    assert np.array_equal(s1.mask, s2.mask)


def test_oblique_and_unnamed_volumes_are_rejected(tmp_path):
    a = ball((20, 20, 20), (10, 10, 10), 4)
    oblique = tmp_path / "oblique.seg.nrrd"
    header = {
        "space": "right-anterior-superior",
        "kinds": ["list", "domain", "domain", "domain"],
        "space directions": np.array([[np.nan] * 3, [0.125, 0.01, 0], [0, 0.125, 0], [0, 0, 0.125]]),
        "space origin": np.zeros(3),
        "Segment0_Name": "Incus",
    }
    nrrd.write(str(oblique), a[None].astype(np.uint8), header, index_order="F")
    with pytest.raises(ValueError, match="oblique"):
        read_segmentation(str(oblique))
    unnamed = tmp_path / "unnamed.seg.nrrd"
    write_seg(unnamed, [a], [])
    with pytest.raises(ValueError, match="Segment0_Name"):
        read_segmentation(str(unnamed))


def test_expected_segment_list_matches_what_the_files_contain():
    assert len(EXPECTED_SEGMENTS) == 13
    assert "Cochleovestibular nerve" in EXPECTED_SEGMENTS
