"""The schematic membranous labyrinth placed on a real specimen (OpenEar ZETA)."""
import numpy as np
from scipy import ndimage

from otopipe import membranous as M
from otopipe import ossicles
from tests.test_ossicles import _labels


def _setup():
    d = _labels()
    st, sv = d["scala_tympani"], d["scala_vestibuli"]
    tymp, vest, sp, origin = M._common(st, sv)
    far = ndimage.distance_transform_edt(~tymp, sampling=sp) > 1.0
    vestibular = (M._largest(vest & far), tuple(sp), tuple(origin))
    centre = M.vestibule_centre(vestibular)
    cochlea = ossicles.points(st).mean(axis=0)
    frame = ossicles.anatomical_frame(centre, cochlea, d["tympanic_membrane"], d["malleus"])
    return st, sv, vestibular, frame


def test_every_part_is_placed():
    st, sv, vestibular, frame = _setup()
    mem = M.build(st, sv, vestibular, frame)
    assert set(mem.parts) == {"cochlear_duct", "semicircular_ducts", "utricle", "saccule"}
    assert 24 <= mem.report["cochlear_duct"]["path_length_mm"] <= 40


def test_sacs_sit_inside_the_vestibule_and_the_saccule_nearer_the_cochlea():
    st, _, vestibular, frame = _setup()
    centre = M.vestibule_centre(vestibular)
    cochlea = ossicles.points(st).mean(axis=0)
    sacs, _ = M.vestibular_sacs(vestibular, centre, cochlea, frame)
    vmask, vsp, vorg = vestibular
    for mask, origin in sacs.values():
        pts = np.asarray(origin) + np.argwhere(mask) * M.GRID_MM
        idx = np.rint((pts - np.asarray(vorg)) / np.asarray(vsp)).astype(int)
        assert vmask[tuple(idx.T)].mean() > 0.99

    def mid(name):
        mask, origin = sacs[name]
        return (np.asarray(origin) + np.argwhere(mask) * M.GRID_MM).mean(axis=0)

    assert np.linalg.norm(mid("saccule") - cochlea) < np.linalg.norm(mid("utricle") - cochlea)
