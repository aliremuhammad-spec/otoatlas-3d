"""Reader for OpenEar segmentations (3D Slicer `.seg.nrrd`, one binary layer per segment).

Layout confirmed on specimen ZETA: a 4D array `[segment, i, j, k]` of unsigned char,
0.125 mm isotropic, in right-anterior-superior space, with header keys
`Segment<N>_Name`. Thirteen segments are present.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
import nrrd

# Segment names exactly as they appear in the OpenEar files.
EXPECTED_SEGMENTS = (
    "Scala Tympani",
    "Scala Vestibuli",
    "Malleus",
    "Incus",
    "Stapes",
    "Cochleovestibular nerve",
    "Facial Nerve",
    "Chorda Tympani",
    "Bone",
    "Tympanic Membrane",
    "External Auditory Canal",
    "Sinus Dura",
    "Carotis Interna",
)


@dataclass(frozen=True)
class Segment:
    name: str
    mask: np.ndarray  # cropped to the segment's bounding box
    spacing: tuple[float, float, float]
    origin: tuple[float, float, float]  # centre of mask voxel (0, 0, 0), specimen frame, mm


def _to_ras_signs(space: str) -> np.ndarray:
    space = space.lower().replace("_", "-")
    if space in ("right-anterior-superior", "ras"):
        return np.array([1.0, 1.0, 1.0])
    if space in ("left-posterior-superior", "lps"):
        return np.array([-1.0, -1.0, 1.0])
    raise ValueError(f"unsupported NRRD space: {space!r}")


def read_segmentation(path: str) -> dict[str, Segment]:
    """Read every segment as a cropped boolean mask in the specimen frame (RAS, mm).

    Only axis-aligned volumes are accepted: OpenEar's are, and silently resampling
    an oblique volume would blur sub-voxel detail.
    """
    data, header = nrrd.read(path, index_order="F")
    if data.ndim != 4:
        raise ValueError("expected a 4D segmentation with one layer per segment")
    directions = np.asarray(header["space directions"][1:], dtype=np.float64)
    off_diagonal = directions - np.diag(np.diag(directions))
    if np.abs(off_diagonal).max() > 1e-9:
        raise ValueError("oblique volumes are not supported")
    signs = _to_ras_signs(str(header["space"]))
    step = np.diag(directions) * signs
    first = np.asarray(header["space origin"], dtype=np.float64) * signs
    if (step <= 0).any():
        raise ValueError("volume axes must run in the positive RAS direction")

    segments: dict[str, Segment] = {}
    for layer in range(data.shape[0]):
        name = str(header.get(f"Segment{layer}_Name", "")).strip()
        if not name:
            raise ValueError(f"layer {layer} has no Segment{layer}_Name")
        volume = data[layer] > 0
        if not volume.any():
            continue
        idx = np.argwhere(volume)
        lo, hi = idx.min(axis=0), idx.max(axis=0) + 1
        mask = volume[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]].copy()
        origin = first + lo * step
        segments[name] = Segment(name, mask, tuple(step), tuple(origin))
    return segments


def _letters(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def match_segments(found: dict, wanted) -> tuple[dict, list[str]]:
    """Key the file's segments by the wanted names they match, ignoring case, spaces and punctuation.

    Returns the matched segments under the wanted names, and the file names that matched none.
    """
    by_letters: dict[str, str] = {}
    for name in found:
        key = _letters(name)
        if key in by_letters:
            raise ValueError(f"segments {by_letters[key]!r} and {name!r} cannot be told apart")
        by_letters[key] = name
    matched = {w: found[by_letters[_letters(w)]] for w in wanted if _letters(w) in by_letters}
    used = {by_letters[_letters(w)] for w in wanted if _letters(w) in by_letters}
    return matched, sorted(set(found) - used)
