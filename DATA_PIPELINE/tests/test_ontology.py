"""The ontology must map every dataset label exactly once and flag unreviewed Arabic terms."""
import json
from pathlib import Path

from otopipe.openear import EXPECTED_SEGMENTS

ONTOLOGY = json.loads((Path(__file__).parents[2] / "ontology" / "structures.json").read_text(encoding="utf-8"))


def test_every_openear_label_is_mapped_exactly_once():
    mapped = [src["label"] for s in ONTOLOGY["structures"] for src in s["sources"] if src["dataset"] == "openear"]
    assert sorted(mapped) == sorted(EXPECTED_SEGMENTS)


def test_ids_are_unique_and_parents_exist():
    ids = [s["id"] for s in ONTOLOGY["structures"]] + [g["id"] for g in ONTOLOGY["groups"]]
    assert len(ids) == len(set(ids))
    for s in ONTOLOGY["structures"]:
        assert s["parent"] is None or s["parent"] in ids


def test_nothing_is_marked_verified_without_a_named_reviewer():
    for s in ONTOLOGY["structures"]:
        assert s["ar_status"] in ONTOLOGY["ar_status_values"]
        if s["ar_status"] == "verified" or s["content_status"] == "expert-reviewed":
            assert s["reviewed_by"], s["id"]
