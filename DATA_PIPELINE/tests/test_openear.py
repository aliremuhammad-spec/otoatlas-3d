"""OpenEar segmentation reader, tested on a synthetic file with the real header layout."""
import numpy as np
import nrrd
import pytest

from otopipe import mesh as M
from otopipe import openear
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


def test_segment_names_match_ignoring_case_spaces_and_punctuation():
    found = {"Facial nerve": 1, "scala_tympani": 2, "Bone": 3, "Extra": 4}
    matched, source, unused = openear.match_segments(found, ["Facial Nerve", "Scala Tympani", "Bone", "Malleus"])
    assert matched == {"Facial Nerve": 1, "Scala Tympani": 2, "Bone": 3}
    assert source["Facial Nerve"] == "Facial nerve"
    assert unused == ["Extra"]


def test_other_spellings_in_the_files_match_by_alias():
    found = {"EAC": 1, "Tympanic Drum": 2, "Vestibucochlear Nerve": 3, "Bone 1300": 4, "RW": 5}
    matched, source, unused = openear.match_segments(
        found, ["External Auditory Canal", "Tympanic Membrane", "Cochleovestibular nerve", "Bone"]
    )
    assert matched == {"External Auditory Canal": 1, "Tympanic Membrane": 2, "Cochleovestibular nerve": 3, "Bone": 4}
    assert unused == ["RW"]


def test_a_name_and_its_alias_both_present_is_refused():
    with pytest.raises(ValueError):
        openear.match_segments({"Sinus Dura": 1, "Sinus": 2}, ["Sinus Dura"])


def test_two_segments_that_cannot_be_told_apart_are_refused():
    with pytest.raises(ValueError):
        openear.match_segments({"Bone": 1, "bone": 2}, ["Bone"])


def test_coarsen_keeps_a_block_when_most_of_it_is_inside_and_moves_the_origin_to_block_centres():
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location("build_content", pathlib.Path(__file__).parents[1] / "build_content.py")
    bc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bc)
    m = np.zeros((4, 4, 4), bool)
    m[:2, :2, :2] = True  # one full block
    m[2, 2, 2] = True  # one voxel of another block: minority
    out, sp, org = bc.coarsen(m, (0.05, 0.05, 0.05), (1.0, 2.0, 3.0), 2)
    assert out.shape == (2, 2, 2) and out[0, 0, 0] and out.sum() == 1
    assert sp == (0.1, 0.1, 0.1)
    assert org == pytest.approx((1.025, 2.025, 3.025))


def test_streamed_reading_matches_across_chunks_raw_and_label_value_layouts(tmp_path, monkeypatch):
    from otopipe import openear as O

    shape = (30, 20, 25)
    a, b = ball(shape, (10, 10, 5), 4), ball(shape, (20, 8, 18), 5)
    # Tiny chunks force a segment to span several reads.
    monkeypatch.setattr(O, "CHUNK_BYTES", 3 * 30 * 20 * 2)
    for encoding in ("gzip", "raw"):
        path = tmp_path / f"layers-{encoding}.seg.nrrd"
        write_seg(path, [a, b], ["Malleus", "Incus"])
        if encoding == "raw":
            data, header = nrrd.read(str(path), index_order="F")
            header["encoding"] = "raw"
            nrrd.write(str(path), data, header, index_order="F")
        segs = O.read_segmentation(str(path))
        assert np.array_equal(segs["Malleus"].mask, a[6:15, 6:15, 1:10])
        assert segs["Incus"].mask.sum() == b.sum()
    # One shared layer, each segment its own label value (newer Slicer files).
    labels = a.astype(np.uint8) + 2 * b.astype(np.uint8)
    header = {
        "space": "right-anterior-superior",
        "space directions": np.diag([0.125] * 3),
        "space origin": np.zeros(3),
        "encoding": "gzip",
        "Segment0_Name": "Malleus", "Segment0_Layer": "0", "Segment0_LabelValue": "1",
        "Segment1_Name": "Incus", "Segment1_Layer": "0", "Segment1_LabelValue": "2",
    }
    path = tmp_path / "shared.seg.nrrd"
    nrrd.write(str(path), labels, header, index_order="F")
    segs = O.read_segmentation(str(path))
    assert segs["Malleus"].mask.sum() == (labels == 1).sum()
    assert segs["Incus"].mask.sum() == (labels == 2).sum()
