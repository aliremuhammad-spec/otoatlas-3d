"""Schematic muscles and ligaments placed on a real specimen (OpenEar ZETA)."""
import numpy as np
from scipy.spatial import cKDTree

from otopipe import membranous as M
from otopipe import ossicles, softtissue
from tests.test_membranous import _setup
from tests.test_ossicles import _labels


def test_all_ten_are_placed_and_none_runs_through_the_nerve_or_labyrinth():  # noqa: C901
    d = _labels()
    st, sv, vestibular, frame = _setup()
    parts = {
        "malleus": ossicles.malleus_parts(d["malleus"], d["tympanic_membrane"], d["incus"], frame).parts,
        "incus": ossicles.incus_parts(d["incus"], d["stapes"], frame).parts,
        "stapes": ossicles.stapes_parts(d["stapes"], d["incus"], vestibular, frame).parts,
    }
    spacings = {k: d[k][1] for k in parts}
    no_bone = (np.zeros((2, 2, 2), bool), (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
    labyrinth = np.vstack([ossicles.points(st), ossicles.points(sv)])
    soft = softtissue.build(parts, spacings, d["facial_nerve"], no_bone, frame, labyrinth)
    assert len(soft.parts) == 10
    nerve = cKDTree(ossicles.points(d["facial_nerve"]))
    lab = cKDTree(labyrinth)
    for name, (mask, origin) in soft.parts.items():
        pts = np.asarray(origin) + np.argwhere(mask) * M.GRID_MM
        assert len(pts), name
        assert nerve.query(pts)[0].min() >= 0.09, name
        if name != "annular_ligament":  # sits on the vestibule by design
            assert lab.query(pts)[0].min() >= 0.09, name
