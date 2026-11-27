"""The step that attaches true-colour products to the built packages (.github/scripts/attach_colour.py)."""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "attach_colour.py"
spec = importlib.util.spec_from_file_location("attach_colour", SCRIPT)
attach_colour = importlib.util.module_from_spec(spec)
spec.loader.exec_module(attach_colour)


def staging(tmp_path: Path, warnings=()) -> Path:
    st = tmp_path / "staging"
    st.mkdir()
    for tag, mm in (("colour_0p10", 0.1), ("colour_0p15", 0.15), ("colour_0p20", 0.2), ("normal", 0.4)):
        (st / f"ZETA_{tag}.bricks").write_bytes(b"x" * 100)
        (st / f"ZETA_{tag}.json").write_text(json.dumps({"spacing_mm": [mm] * 3, "dims": [10, 11, 12], "origin_mm": [1.0, 2.0, 3.0]}))
    (st / "ZETA_colour_meta.json").write_text(json.dumps({
        "warnings": list(warnings), "levelling": {"levelled": True}, "cbct_alpha": {"usable": True},
        "alignment": {"applied_shift_mm_colour_minus_label": [-0.15, 0.05, 0.1]}}))
    (st / "ZETA_diag_0p20.npz").write_bytes(b"d")
    return st


def package(tmp_path: Path) -> Path:
    content = tmp_path / "content"
    (content / "OPENEAR-ZETA").mkdir(parents=True)
    (content / "OPENEAR-ZETA" / "manifest.json").write_text(json.dumps({"specimen_id": "OPENEAR-ZETA", "structures": []}))
    return content


def test_attach_writes_the_colour_block_and_files(tmp_path):
    content, st = package(tmp_path), staging(tmp_path)
    assert attach_colour.attach(content, st) == 1
    m = json.loads((content / "OPENEAR-ZETA" / "manifest.json").read_text())
    c = m["colour"]
    assert [t["spacing_mm"] for t in c["tiers"]] == [0.1, 0.15, 0.2]
    assert [t["on_site"] for t in c["tiers"]] == [False, True, True]
    assert c["normals"]["spacing_mm"] == 0.4 and c["alpha_source"] == "colour+cbct" and c["shift_mm"] == [-0.15, 0.05, 0.1]
    assert (content / "OPENEAR-ZETA" / c["tiers"][1]["bricks"]).exists()
    assert not list((content / "OPENEAR-ZETA" / "colour").glob("*diag*"))
    assert "Designed under the supervision of Dr. Ali R. Muhammad" in (content / "OPENEAR-ZETA" / "colour" / "README.md").read_text()


def test_attach_leaves_out_a_specimen_whose_orientation_failed(tmp_path):
    content, st = package(tmp_path), staging(tmp_path, ["ORIENTATION: check for a flip"])
    assert attach_colour.attach(content, st) == 0
    assert "colour" not in json.loads((content / "OPENEAR-ZETA" / "manifest.json").read_text())


def test_attach_skips_packages_without_products(tmp_path):
    content = package(tmp_path)
    (tmp_path / "empty").mkdir()
    assert attach_colour.attach(content, tmp_path / "empty") == 0


def test_finish_takes_the_finest_tier_off_the_site(tmp_path):
    content, st = package(tmp_path), staging(tmp_path)
    attach_colour.attach(content, st)
    folder = content / "OPENEAR-ZETA"
    attach_colour.finish(content)  # no Hugging Face url was written: the tier is dropped
    c = json.loads((folder / "manifest.json").read_text())["colour"]
    assert [t["spacing_mm"] for t in c["tiers"]] == [0.15, 0.2]
    assert not (folder / "colour" / "ZETA_colour_0p10.bricks").exists()
    assert (folder / "colour" / "ZETA_colour_0p15.bricks").exists()


def test_finish_keeps_the_finest_tier_when_it_has_a_url(tmp_path):
    content, st = package(tmp_path), staging(tmp_path)
    attach_colour.attach(content, st)
    folder = content / "OPENEAR-ZETA"
    m = json.loads((folder / "manifest.json").read_text())
    m["colour"]["tiers"][0]["url"] = "https://huggingface.co/datasets/u/r/resolve/" + "a" * 40 + "/p/colour/x.bricks"
    (folder / "manifest.json").write_text(json.dumps(m))
    attach_colour.finish(content)
    c = json.loads((folder / "manifest.json").read_text())["colour"]
    assert [t["spacing_mm"] for t in c["tiers"]] == [0.1, 0.15, 0.2]
    assert not (folder / "colour" / "ZETA_colour_0p10.bricks").exists()
