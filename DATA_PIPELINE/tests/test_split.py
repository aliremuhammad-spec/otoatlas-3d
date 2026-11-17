"""Splitting a label by distance to a reference label, on phantoms with known answers."""
import numpy as np
import pytest

from otopipe import split


def box(shape, lo, hi):
    m = np.zeros(shape, bool)
    m[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]] = True
    return m


SP = (0.125, 0.125, 0.125)


def test_piece_near_the_reference_is_cochlear_and_far_piece_is_vestibular():
    # Label: a near slab (touching the reference) joined by a thin bridge to a far block.
    label = np.zeros((80, 20, 20), bool)
    label[0:8] = True  # 1 mm thick slab beside the reference
    label[8:60, 8:12, 8:12] = True  # bridge running away from it
    label[60:80] = True  # far block, 7.5 mm or more away
    reference = np.ones((8, 20, 20), bool)  # sits just before the label along x
    result = split.split_by_reach(label, (0.0, 0.0, 0.0), reference, (-1.0, 0.0, 0.0), SP, reach_mm=1.0)
    c, v = result.cochlear, result.vestibular
    # Everything within 1 mm of the reference: slab (x 0 to 0.875) and bridge up to x = 0.875.
    assert c.mask.shape[0] == 8 and c.origin[0] == pytest.approx(0.0)
    assert v.origin[0] == pytest.approx(1.0)
    assert int(c.mask.sum()) + int(v.mask.sum()) == int(label.sum())
    assert result.report["vestibular_pieces"] == 1


def test_isolated_near_fragment_is_not_kept_as_cochlear():
    label = np.zeros((40, 40, 10), bool)
    label[0:4, 0:20] = True  # large piece near the reference
    label[0:2, 30:32] = True  # tiny separate piece also near it
    reference = np.ones((4, 40, 10), bool)
    result = split.split_by_reach(label, (0.0, 0.0, 0.0), reference, (-0.5, 0.0, 0.0), SP, reach_mm=1.0)
    assert int(result.cochlear.mask.sum()) == 4 * 20 * 10
    assert result.report["near_pieces_dropped"] == 1


def test_labels_on_different_grids_are_refused():
    m = np.ones((4, 4, 4), bool)
    with pytest.raises(ValueError):
        split.split_by_reach(m, (0.0, 0.0, 0.0), m, (0.05, 0.0, 0.0), SP)
