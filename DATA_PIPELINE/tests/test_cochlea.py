"""A and B values on a phantom 'basal turn': a flat ring around the modiolus."""
import numpy as np
import pytest

from otopipe import cochlea

SP = (0.05, 0.05, 0.05)


def test_a_and_b_on_a_ring():
    n = 240
    x, y = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    r = np.hypot((x - 120) * 0.05, (y - 120) * 0.05)
    ring = (r >= 2.0) & (r <= 4.5)  # lumen of the basal turn: 2 to 4.5 mm from the axis
    mask = np.repeat(ring[:, :, None], 20, axis=2)
    origin = (-6.0, -6.0, -0.5)
    # Round window on the outer wall at -x; axis along +z; centre at the origin.
    out = cochlea.a_and_b(mask, SP, origin, centre=(0.0, 0.0, 0.0), axis=(0, 0, 1), round_window=(-4.5, 0.0, 0.0))
    assert out["cochlear_a_value"] == pytest.approx(9.0, abs=0.12)
    assert out["cochlear_b_value"] == pytest.approx(9.0, abs=0.12)
