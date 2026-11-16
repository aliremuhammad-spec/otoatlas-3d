"""Cochlear coordinate frame of the Bern Human Bony Labyrinth dataset.

Definition, from Wimmer et al. (Data in Brief 27, 2019, doi:10.1016/j.dib.2019.104782)
and checked here against the axes shipped in the dataset's own descriptor files:

    origin  C, the centre of the cochlear basal turn
    z       from C towards the helicotrema A (the modiolar axis)
    x       from C towards the round-window centre RW, made orthogonal to z
    y       completes the frame; the dataset mirrors it for left ears, so that y
            has the same anatomical meaning on both sides

The descriptors give the axes to two decimals only, which is not orthonormal enough
to measure with. This module recomputes them from the landmarks at full precision.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

LANDMARK_NAMES = ("RW", "C", "A", "OW", "V")


@dataclass(frozen=True)
class CochlearFrame:
    origin: np.ndarray
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray

    def to_frame(self, points_mm: np.ndarray) -> np.ndarray:
        """Scanner-space points (N, 3) in millimetres to cochlear-frame coordinates."""
        rotation = np.stack([self.x, self.y, self.z])
        return (np.asarray(points_mm, dtype=np.float64) - self.origin) @ rotation.T


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n == 0:
        raise ValueError("landmarks coincide; the frame is undefined")
    return v / n


def cochlear_frame(landmarks: dict[str, list[float]], side: str) -> CochlearFrame:
    """Orthonormal cochlear frame from the dataset landmarks.

    `side` is the descriptor's SIDE field, "LEFT" or "RIGHT".
    """
    side = side.upper()
    if side not in ("LEFT", "RIGHT"):
        raise ValueError(f"unknown side: {side!r}")
    c = np.asarray(landmarks["C"], dtype=np.float64)
    z = _unit(np.asarray(landmarks["A"], dtype=np.float64) - c)
    towards_rw = np.asarray(landmarks["RW"], dtype=np.float64) - c
    x = _unit(towards_rw - np.dot(towards_rw, z) * z)
    # Left ears use x cross z, confirmed on specimens F01 and T01. Right ears use the
    # mirrored product; that branch is checked against each right-ear descriptor at build time.
    y = np.cross(x, z) if side == "LEFT" else np.cross(z, x)
    return CochlearFrame(c, x, _unit(y), z)


def max_axis_disagreement(frame: CochlearFrame, descriptor_coord: dict[str, list[float]]) -> float:
    """Largest component difference between the computed axes and the descriptor's.

    The descriptor rounds to two decimals and derives x before orthogonalisation,
    so differences up to a few hundredths are expected. A value near 1 or 2 means
    an axis is flipped and the specimen must not be built until that is resolved.
    """
    pairs = ((frame.x, "XAXIS"), (frame.y, "YAXIS"), (frame.z, "ZAXIS"))
    return max(
        float(np.abs(axis - np.asarray(descriptor_coord[key], dtype=np.float64)).max())
        for axis, key in pairs
    )
