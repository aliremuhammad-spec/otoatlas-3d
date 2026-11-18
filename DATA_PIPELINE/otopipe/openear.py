"""Reader for OpenEar segmentations (3D Slicer `.seg.nrrd`, one binary layer per segment).

Layout confirmed on specimen ZETA: a 4D array `[segment, i, j, k]` of unsigned char,
0.125 mm isotropic, in right-anterior-superior space, with header keys
`Segment<N>_Name`. Thirteen segments are present.
"""
from __future__ import annotations

import re
import zlib
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


CHUNK_BYTES = 256 * 1024 * 1024


def _plane_chunks(path: str, header: dict, data_start: int, plane_bytes: int, dtype: np.dtype, planes: int):
    """Yield (first_plane, block) over the data, a few planes along the slowest axis at a time.

    The data is read as a stream (gzip or raw), so a segmentation larger than memory
    can still be read: DELTA's would not fit when loaded whole.
    """
    encoding = str(header.get("encoding", "raw")).lower()
    if encoding not in ("raw", "gzip", "gz"):
        raise ValueError(f"unsupported NRRD encoding: {encoding!r}")
    per = max(1, CHUNK_BYTES // plane_bytes)
    with open(path, "rb") as fh:
        fh.seek(data_start)
        inflate = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding != "raw" else None
        pending = bytearray()
        z = 0
        while z < planes:
            want = min(per, planes - z) * plane_bytes
            while len(pending) < want:
                raw = fh.read(16 * 1024 * 1024)
                if not raw:
                    raise ValueError("segmentation data ends early")
                pending.extend(inflate.decompress(raw) if inflate else raw)
            block = bytes(pending[:want])
            del pending[:want]
            yield z, np.frombuffer(block, dtype=dtype)
            z += want // plane_bytes


def read_segmentation(path: str) -> dict[str, Segment]:
    """Read every segment as a cropped boolean mask in the specimen frame (RAS, mm).

    Handles both Slicer layouts: one layer per segment (4D, as in ZETA) and segments
    sharing layers with a label value each. The data is streamed twice, once for each
    segment's bounding box and once to fill it, so only the cropped masks are held.

    Only axis-aligned volumes are accepted: OpenEar's are, and silently resampling
    an oblique volume would blur sub-voxel detail.
    """
    with open(path, "rb") as fh:
        header = nrrd.read_header(fh)
        data_start = fh.tell()
    if int(header.get("line skip", 0)) or int(header.get("byte skip", 0)):
        raise ValueError("NRRD line or byte skips are not supported")
    sizes = [int(v) for v in header["sizes"]]
    print(f"segmentation: sizes {sizes}, type {header.get('type')}, encoding {header.get('encoding')}", flush=True)
    if len(sizes) not in (3, 4):
        raise ValueError("expected a 3D or 4D segmentation")
    layered = len(sizes) == 4
    layers = sizes[0] if layered else 1
    nx, ny, nz = sizes[-3:]
    directions = np.asarray(header["space directions"], dtype=np.float64)
    directions = directions[1:] if layered else directions
    off_diagonal = directions - np.diag(np.diag(directions))
    if np.abs(off_diagonal).max() > 1e-9:
        raise ValueError("oblique volumes are not supported")
    signs = _to_ras_signs(str(header["space"]))
    step = np.diag(directions) * signs
    first = np.asarray(header["space origin"], dtype=np.float64) * signs
    if (step <= 0).any():
        raise ValueError("volume axes must run in the positive RAS direction")
    dtype = nrrd.reader._determine_datatype(header)

    # Which layer and which value make up each segment.
    count = layers if layered else 0
    while f"Segment{count}_Name" in header:
        count += 1
    specs = []
    for n in range(count):
        name = str(header.get(f"Segment{n}_Name", "")).strip()
        if not name:
            raise ValueError(f"layer {n} has no Segment{n}_Name")
        layer = int(header.get(f"Segment{n}_Layer", n if layered else 0))
        value = header.get(f"Segment{n}_LabelValue")
        if not 0 <= layer < layers:
            raise ValueError(f"segment {name!r} names layer {layer}, which does not exist")
        specs.append((name, layer, None if value is None else int(value)))

    plane_bytes = layers * nx * ny * dtype.itemsize

    def masks_of(block: np.ndarray):
        # File order is layer fastest, then x, y, z: as C order that is [z, y, x, layer].
        grid = block.reshape(-1, ny, nx, layers)
        for name, layer, value in specs:
            plane = grid[..., layer]
            yield name, ((plane == value) if value is not None else (plane > 0)).transpose(2, 1, 0)

    bounds: dict[str, list] = {}
    for z0, block in _plane_chunks(path, header, data_start, plane_bytes, dtype, nz):
        for name, m in masks_of(block):
            if not m.any():
                continue
            xs, ys, zs = (np.flatnonzero(m.any(axis=a)) for a in ((1, 2), (0, 2), (0, 1)))
            lo = np.array([xs[0], ys[0], zs[0] + z0])
            hi = np.array([xs[-1], ys[-1], zs[-1] + z0]) + 1
            if name in bounds:
                bounds[name] = [np.minimum(bounds[name][0], lo), np.maximum(bounds[name][1], hi)]
            else:
                bounds[name] = [lo, hi]

    crops = {name: np.zeros(tuple(hi - lo), dtype=bool) for name, (lo, hi) in bounds.items()}
    for z0, block in _plane_chunks(path, header, data_start, plane_bytes, dtype, nz):
        for name, m in masks_of(block):
            if name not in crops:
                continue
            lo, hi = bounds[name]
            za, zb = max(lo[2], z0), min(hi[2], z0 + m.shape[2])
            if za >= zb:
                continue
            crops[name][:, :, za - lo[2] : zb - lo[2]] = m[lo[0] : hi[0], lo[1] : hi[1], za - z0 : zb - z0]

    return {
        name: Segment(name, crops[name], tuple(step), tuple(first + bounds[name][0] * step))
        for name, _, _ in specs
        if name in crops
    }


def _letters(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


# Other spellings seen in the OpenEar files, by the name used here (checked on all eight
# specimens, 2026-11-17). Typos in the files ("Vestibucochlear") are kept as found.
ALIASES = {
    "Carotis Interna": ["Carotis", "Carotide"],
    "External Auditory Canal": ["EAC", "Outer Auditory Canal", "Outer Ear Canal", "External Ear Canal"],
    "Chorda Tympani": ["Chorda"],
    "Sinus Dura": ["Sinus"],
    "Tympanic Membrane": ["Tympanic Drum"],
    "Cochleovestibular nerve": ["Vestibulocochlear nerve", "Vestibulcochlear Nerve", "Vestibucochlear Nerve"],
    "Bone": ["Bone 1300"],
}


def match_segments(found: dict, wanted) -> tuple[dict, dict, list[str]]:
    """Key the file's segments by the wanted names, ignoring case, spaces and punctuation.

    Each wanted name also matches its ALIASES. Returns the matched segments under the
    wanted names, the file name each came from, and the file names that matched none.
    Two file segments that could both be one structure are refused.
    """
    by_letters: dict[str, str] = {}
    for name in found:
        key = _letters(name)
        if key in by_letters:
            raise ValueError(f"segments {by_letters[key]!r} and {name!r} cannot be told apart")
        by_letters[key] = name
    matched, source = {}, {}
    for w in wanted:
        hits = [by_letters[k] for k in dict.fromkeys(_letters(n) for n in [w, *ALIASES.get(w, [])]) if k in by_letters]
        if len(hits) > 1:
            raise ValueError(f"{w!r} matches several segments: {hits}")
        if hits:
            matched[w], source[w] = found[hits[0]], hits[0]
    return matched, source, sorted(set(found) - set(source.values()))
