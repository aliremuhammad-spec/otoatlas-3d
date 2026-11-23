"""Package building and fetching helpers, on synthetic data."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import trimesh

from otopipe import fetch, package
from otopipe import phantoms as P

ONTOLOGY = package.load_ontology(Path(__file__).parents[2] / "ontology" / "structures.json")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("pkg")
    spacing = (0.125, 0.125, 0.125)
    a, oa = P.ellipsoid((1.5, 1.0, 1.0), spacing, centre=(0.0, 0.0, 0.0))
    b, ob = P.ellipsoid((1.0, 1.0, 1.0), spacing, centre=(5.0, 0.0, 0.0))
    labels = [package.LabelInput("Malleus", a, spacing, oa), package.LabelInput("Scala Tympani", b, spacing, ob)]
    manifest = package.build_package(out, "TEST-01", "openear", labels, ONTOLOGY, samples=4000)
    return out, manifest


def test_manifest_records_names_limits_and_measured_error(built):
    out, manifest = built
    assert json.loads((out / "manifest.json").read_text(encoding="utf-8")) == manifest
    by_id = {s["id"]: s for s in manifest["structures"]}
    assert set(by_id) == {"malleus", "scala_tympani"}
    assert by_id["malleus"]["names"] == {"en": "Malleus", "ar": "المطرقة", "latin": "Malleus"}
    assert by_id["malleus"]["mesh_error_limit_mm"] == 0.10
    assert by_id["scala_tympani"]["mesh_error_limit_mm"] == 0.05
    assert manifest["attribution"]["license"] == "CC BY 4.0"
    assert manifest["synthetic"] is False
    for s in manifest["structures"]:
        lod0 = s["lods"][0]
        assert lod0["within_limit"] and 0 < lod0["hausdorff_mm"] <= s["mesh_error_limit_mm"]
        assert s["ar_status"] == "verified"  # confirmed by the reviewer on 2026-11-17
        assert s["default_opacity"] == 1.0 and s["default_visible"] is True
        assert s["description"]["status"] == "draft" and s["description"]["ar"]
        assert s["display_level"] == 0  # small meshes are shown at full resolution


def test_meshes_are_written_in_the_specimen_frame(built):
    out, manifest = built
    scala = next(s for s in manifest["structures"] if s["id"] == "scala_tympani")
    mesh = trimesh.load(out / scala["lods"][0]["file"], force="mesh")
    assert np.allclose(mesh.centroid, (5.0, 0.0, 0.0), atol=0.02)
    assert mesh.faces.shape[0] == scala["lods"][0]["triangles"]
    assert scala["volume_mm3"] == pytest.approx(4 / 3 * np.pi, rel=0.03)


def test_unknown_labels_are_an_error_not_a_silent_skip(tmp_path):
    mask, origin = P.ellipsoid((1, 1, 1), (0.125,) * 3)
    with pytest.raises(KeyError):
        package.build_package(tmp_path, "X", "openear", [package.LabelInput("Mystery", mask, (0.125,) * 3, origin)], ONTOLOGY)


def test_checksum_verification():
    data = b"temporal bone"
    fetch.verify_md5(data, "md5:" + hashlib.md5(data).hexdigest())
    with pytest.raises(OSError):
        fetch.verify_md5(data + b"!", "md5:" + hashlib.md5(data).hexdigest())
    with pytest.raises(ValueError):
        fetch.verify_md5(data, "sha1:abc")


def test_archive_member_lookup_requires_exactly_one_match():
    names = ["06_Segmentation/Segmentation.seg.nrrd", "05_X/Accuracy Analysis/Segmentation_Outline.seg.nrrd"]
    assert fetch.find_member(names, "06_Segmentation/Segmentation.seg.nrrd") == names[0]
    assert fetch.find_member(["Dataset/ZETA/" + names[0]], "06_Segmentation/Segmentation.seg.nrrd").startswith("Dataset")
    with pytest.raises(LookupError):
        fetch.find_member(names, ".seg.nrrd")
    with pytest.raises(LookupError):
        fetch.find_member(names, "missing.nrrd")


def test_large_meshes_are_displayed_at_the_finest_level_under_the_budget():
    lods = [{"level": 0, "triangles": 7_000_000}, {"level": 1, "triangles": 1_750_000}, {"level": 2, "triangles": 700_000}]
    assert package.display_level(lods) == 2
    assert package.display_level(lods[:2]) == 1  # nothing fits: the coarsest level
    assert package.display_level([{"level": 0, "triangles": 50_000}] + lods[1:]) == 0


def test_publish_shown_only_keeps_one_file_per_structure_but_every_measurement(tmp_path):
    spacing = (0.125, 0.125, 0.125)
    a, oa = P.ellipsoid((1.5, 1.0, 1.0), spacing, centre=(0.0, 0.0, 0.0))
    manifest = package.build_package(
        tmp_path, "TEST-02", "openear", [package.LabelInput("Malleus", a, spacing, oa)], ONTOLOGY,
        samples=2000, publish_shown_only=True,
    )
    lods = manifest["structures"][0]["lods"]
    assert [l["published"] for l in lods] == [True, False, False]
    assert sorted(p.name for p in tmp_path.glob("*.glb")) == ["malleus.lod0.glb"]
    assert all("hausdorff_mm" in l for l in lods)



def test_parts_carry_their_whole_structure_as_group():
    by_id = {s["id"]: s for s in ONTOLOGY["structures"]}
    assert package.group_of(ONTOLOGY, by_id["stapes_footplate"]) == {
        "id": "stapes", "names": {"en": "Stapes", "ar": "الركاب", "latin": "Stapes"}
    }
    assert package.group_of(ONTOLOGY, by_id["tympanic_membrane_anterosuperior"])["id"] == "tympanic_membrane"
    # A whole bone's parent is a group of structures, not a structure: no group entry.
    assert package.group_of(ONTOLOGY, by_id["malleus"]) is None
