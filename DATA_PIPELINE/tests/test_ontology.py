"""The ontology must map every dataset label exactly once and flag unreviewed Arabic terms."""
import json
from pathlib import Path

from otopipe.openear import EXPECTED_SEGMENTS

ONTOLOGY = json.loads((Path(__file__).parents[2] / "ontology" / "structures.json").read_text(encoding="utf-8"))


def test_every_openear_label_is_mapped_and_no_label_part_twice():
    keys = [(src["label"], src.get("part")) for s in ONTOLOGY["structures"] for src in s["sources"] if src["dataset"] == "openear"]
    assert len(keys) == len(set(keys))
    assert {label for label, _ in keys} == set(EXPECTED_SEGMENTS)
    # A split label maps by parts only, never also as a whole.
    for label in {label for label, part in keys if part}:
        assert (label, None) not in keys, label


def test_scala_vestibuli_is_split_into_cochlear_and_vestibular_parts():
    parts = {src.get("part"): s["id"] for s in ONTOLOGY["structures"] for src in s["sources"] if src["label"] == "Scala Vestibuli"}
    assert parts == {"cochlear": "scala_vestibuli", "vestibular": "vestibule_and_semicircular_canals"}


def test_ids_are_unique_and_parents_exist():
    ids = [s["id"] for s in ONTOLOGY["structures"]] + [g["id"] for g in ONTOLOGY["groups"]]
    assert len(ids) == len(set(ids))
    for s in ONTOLOGY["structures"]:
        assert s["parent"] is None or s["parent"] in ids


def test_nothing_is_marked_verified_without_a_named_reviewer():
    for s in ONTOLOGY["structures"]:
        assert s["ar_status"] in ONTOLOGY["ar_status_values"]
        if s["ar_status"] == "verified":
            assert s.get("ar_reviewed_by") and s.get("ar_reviewed_on"), s["id"]
        if s["content_status"] == "expert-reviewed":
            assert s["reviewed_by"], s["id"]


def test_default_opacity_when_given_is_between_zero_and_one():
    for s in ONTOLOGY["structures"]:
        assert 0.0 <= s.get("default_opacity", 1.0) <= 1.0, s["id"]
