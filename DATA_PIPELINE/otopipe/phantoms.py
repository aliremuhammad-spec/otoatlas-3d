"""Synthetic label volumes with analytic ground truth, for testing the pipeline."""
from __future__ import annotations

import numpy as np


def _grid(shape: tuple[int, int, int], spacing: tuple[float, float, float], origin: tuple[float, float, float]):
    axes = [origin[i] + spacing[i] * np.arange(shape[i]) for i in range(3)]
    return np.meshgrid(*axes, indexing="ij")


def ellipsoid(
    radii: tuple[float, float, float],
    spacing: tuple[float, float, float],
    centre: tuple[float, float, float] = (0.0, 0.0, 0.0),
    margin_voxels: int = 3,
):
    """Binary ellipsoid. Returns (mask, origin): `origin` is the centre of voxel (0, 0, 0)."""
    half = [int(np.ceil(radii[i] / spacing[i])) + margin_voxels for i in range(3)]
    shape = tuple(2 * h + 1 for h in half)
    origin = tuple(centre[i] - half[i] * spacing[i] for i in range(3))
    x, y, z = _grid(shape, spacing, origin)
    mask = (
        ((x - centre[0]) / radii[0]) ** 2
        + ((y - centre[1]) / radii[1]) ** 2
        + ((z - centre[2]) / radii[2]) ** 2
    ) <= 1.0
    return mask, origin


def torus(major: float, minor: float, spacing: tuple[float, float, float], margin_voxels: int = 3):
    """Binary torus around the z axis, centred on the origin. Returns (mask, origin)."""
    reach = (major + minor, major + minor, minor)
    half = [int(np.ceil(reach[i] / spacing[i])) + margin_voxels for i in range(3)]
    shape = tuple(2 * h + 1 for h in half)
    origin = tuple(-half[i] * spacing[i] for i in range(3))
    x, y, z = _grid(shape, spacing, origin)
    mask = (np.sqrt(x**2 + y**2) - major) ** 2 + z**2 <= minor**2
    return mask, origin
