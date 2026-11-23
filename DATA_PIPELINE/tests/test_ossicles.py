"""Ossicle parts on a real specimen (OpenEar ZETA, right ear) and on its mirror image."""
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial import cKDTree

from otopipe import ossicles

DATA = Path(__file__).parent / "data" / "openear_zeta_ossicles.npz"


def _labels(mirror: bool = False) -> dict:
    z = np.load(DATA)
    out = {}
    for name in {k.split("__")[0] for k in z.files}:
        shape = tuple(int(v) for v in z[f"{name}__shape"])
        mask = np.unpackbits(z[f"{name}__bits"])[: int(np.prod(shape))].reshape(shape).astype(bool)
        spacing = tuple(float(v) for v in z[f"{name}__spacing"])
        origin = np.array(z[f"{name}__origin"], float)
        if mirror:  # a left ear: x reversed
            mask = mask[::-1]
            origin[0] = -(origin[0] + (shape[0] - 1) * spacing[0])
        out[name] = (mask, spacing, tuple(origin))
    return out


def _setup(mirror: bool):
    d = _labels(mirror)
    st = ossicles.points(d["scala_tympani"])
    sv_mask, sp, sv_origin = d["scala_vestibuli"]
    sv = ossicles.points(d["scala_vestibuli"])
    far, _ = cKDTree(st).query(sv)
    vest_mask = np.zeros_like(sv_mask)
    vest_mask[tuple(np.argwhere(sv_mask)[far > 1.5].T)] = True
    vestibule = (vest_mask, sp, sv_origin)
    frame = ossicles.anatomical_frame(sv[far > 1.5].mean(axis=0), st.mean(axis=0), d["tympanic_membrane"], d["malleus"])
    return d, vestibule, frame


@pytest.mark.parametrize("mirror, side", [(False, "right"), (True, "left")])
def test_side_from_anatomy(mirror, side):
    _, _, frame = _setup(mirror)
    assert frame.side == side  # ZETA was confirmed a right ear by the reviewer


@pytest.mark.parametrize("mirror", [False, True])
def test_parts_partition_each_bone(mirror):
    d, vestibule, frame = _setup(mirror)
    results = {
        "malleus": ossicles.malleus_parts(d["malleus"], d["tympanic_membrane"], d["incus"], frame),
        "incus": ossicles.incus_parts(d["incus"], d["stapes"], frame),
        "stapes": ossicles.stapes_parts(d["stapes"], d["incus"], vestibule, frame),
    }
    expected = {"malleus": ossicles.MALLEUS_PARTS, "incus": ossicles.INCUS_PARTS, "stapes": ossicles.STAPES_PARTS}
    for bone, r in results.items():
        assert tuple(r.parts) == expected[bone]
        assert sum(int(m.sum()) for m, _ in r.parts.values()) == int(d[bone][0].sum())
    m, i, s = (results[k].report for k in ("malleus", "incus", "stapes"))
    assert 7.6 <= m["length_mm"] <= 9.5
    assert m["handle_length_mm"] < m["neck_at_mm"] < m["length_mm"]
    assert 2.0 <= i["long_process_length_mm"] <= 4.5
    assert 2.6 <= s["footplate_length_mm"] <= 3.4 and 1.1 <= s["footplate_width_mm"] <= 1.8


def test_anterior_crus_lies_towards_the_cochlea():
    d, vestibule, frame = _setup(False)
    r = ossicles.stapes_parts(d["stapes"], d["incus"], vestibule, frame)

    def centre(name):
        mask, origin = r.parts[name]
        return ossicles.points((mask, d["stapes"][1], origin)).mean(axis=0)

    assert (centre("anterior_crus") - centre("posterior_crus")) @ frame.anterior > 0.3


def test_head_is_above_the_handle():
    d, _, frame = _setup(False)
    r = ossicles.malleus_parts(d["malleus"], d["tympanic_membrane"], d["incus"], frame)

    def centre(name):
        mask, origin = r.parts[name]
        return ossicles.points((mask, d["malleus"][1], origin)).mean(axis=0)

    assert (centre("head") - centre("handle")) @ frame.superior > 3.0
    assert (centre("lateral_process") - centre("neck")) @ frame.lateral > 0.2
