"""Label volume to surface mesh, with the geometric error measured and bounded.

Terms used here
---------------
label surface
    The marching-cubes surface of the binary label at iso-level 0.5. It is the
    most literal reading of the segmentation: a staircase that follows voxel faces.
    Every error in this module is a distance to this surface, in millimetres.

The true anatomical boundary lies somewhere within about half a voxel of the label
surface. Smoothing removes the staircase; the clamp below guarantees that doing so
never moves a vertex further from the label surface than the stated limit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh
from skimage import measure

# Limits from the product brief, in millimetres.
INNER_EAR_LIMIT_MM = 0.05
MIDDLE_EAR_LIMIT_MM = 0.10


@dataclass(frozen=True)
class SurfaceError:
    """Two-sided distance between a mesh and the label surface, in millimetres."""

    max_mm: float
    p95_mm: float
    mean_mm: float
    samples: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "hausdorff_mm": round(self.max_mm, 5),
            "p95_mm": round(self.p95_mm, 5),
            "mean_mm": round(self.mean_mm, 5),
            "samples": self.samples,
        }


@dataclass(frozen=True)
class Lod:
    level: int
    mesh: trimesh.Trimesh
    error: SurfaceError
    within_limit: bool


@dataclass(frozen=True)
class MeshBuild:
    label_surface: trimesh.Trimesh
    lods: list[Lod] = field(default_factory=list)
    clamp_mm: float = 0.0


def label_surface(
    mask: np.ndarray,
    spacing: tuple[float, float, float],
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> trimesh.Trimesh:
    """Marching-cubes surface of a binary label, in millimetres.

    `spacing` is the voxel size along each array axis and `origin` the position of
    the centre of voxel (0, 0, 0). The mask is padded so that labels touching the
    volume edge still produce a closed surface.
    """
    if mask.ndim != 3:
        raise ValueError("mask must be a 3D array")
    if not mask.any():
        raise ValueError("mask is empty")
    padded = np.pad(mask.astype(np.float32), 1)
    verts, faces, _, _ = measure.marching_cubes(padded, level=0.5, spacing=spacing)
    verts = verts - np.asarray(spacing) + np.asarray(origin)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    if mesh.volume < 0:
        mesh.invert()
    return mesh


def _closest_distance(surface: trimesh.Trimesh, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    closest, distance, _ = trimesh.proximity.closest_point(surface, points)
    return closest, distance


def taubin(surface: trimesh.Trimesh, iterations: int = 20, lamb: float = 0.5, nu: float = 0.53) -> trimesh.Trimesh:
    """Taubin smoothing: alternating shrink and inflate steps, volume-preserving to first order.

    Plain Laplacian smoothing is not used because it shrinks thin structures.
    """
    smoothed = surface.copy()
    trimesh.smoothing.filter_taubin(smoothed, lamb=lamb, nu=nu, iterations=iterations)
    return smoothed


def smooth_within(surface: trimesh.Trimesh, max_deviation_mm: float, iterations: int = 20) -> trimesh.Trimesh:
    """Taubin-smooth `surface` without letting any vertex travel more than `max_deviation_mm`.

    The bound is on each vertex's displacement from its own starting position, not on
    its distance to the nearest part of the surface. That distinction matters on real,
    rough segmentations: a vertex on a one-voxel spike can slide down to the spike's
    base and still be "close to the surface" while the spike itself has vanished.
    Bounding the displacement keeps every point of the label surface within
    `max_deviation_mm` of the mesh and the mesh within `max_deviation_mm` of it,
    because both share one triangulation and displacement varies linearly on a triangle.
    """
    smoothed = taubin(surface, iterations)
    start = np.asarray(surface.vertices, dtype=np.float64)
    move = np.asarray(smoothed.vertices, dtype=np.float64) - start
    length = np.linalg.norm(move, axis=1)
    over = length > max_deviation_mm
    move[over] *= (max_deviation_mm / length[over])[:, None]
    return trimesh.Trimesh(vertices=start + move, faces=surface.faces, process=False)


def surface_error(
    mesh: trimesh.Trimesh,
    reference: trimesh.Trimesh,
    samples: int = 20000,
    seed: int = 0,
) -> SurfaceError:
    """Two-sided, sampled Hausdorff distance between `mesh` and `reference`.

    Points are the vertices of each mesh plus area-weighted random samples on its
    faces; each point is measured exactly to the other mesh's triangles. The
    reported maximum is therefore a lower bound on the true Hausdorff distance that
    tightens as `samples` grows.
    """
    def one_way(a: trimesh.Trimesh, b: trimesh.Trimesh) -> np.ndarray:
        sampled, _ = trimesh.sample.sample_surface(a, samples, seed=seed)
        points = np.vstack([a.vertices, sampled])
        return _closest_distance(b, points)[1]

    d = np.concatenate([one_way(mesh, reference), one_way(reference, mesh)])
    return SurfaceError(float(d.max()), float(np.percentile(d, 95)), float(d.mean()), int(d.size))


def decimate(mesh: trimesh.Trimesh, keep_fraction: float) -> trimesh.Trimesh:
    """Quadric decimation that keeps roughly `keep_fraction` of the triangles."""
    import fast_simplification

    if not 0 < keep_fraction <= 1:
        raise ValueError("keep_fraction must be in (0, 1]")
    if keep_fraction == 1:
        return mesh
    verts, faces = fast_simplification.simplify(
        np.asarray(mesh.vertices, dtype=np.float64),
        np.asarray(mesh.faces, dtype=np.int64),
        target_reduction=1 - keep_fraction,
    )
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def build_lods(
    mask: np.ndarray,
    spacing: tuple[float, float, float],
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
    limit_mm: float = INNER_EAR_LIMIT_MM,
    keep_fractions: tuple[float, ...] = (1.0, 0.5, 0.25, 0.1),
    samples: int = 20000,
) -> MeshBuild:
    """Build the level-of-detail chain for one label and measure every level.

    LOD0 is the full-resolution mesh, smoothed with every vertex held within `limit_mm`
    of its starting position, and then measured to confirm it. Coarser levels are decimated from LOD0; each is
    measured against the label surface and flagged when it exceeds the limit, so
    the app can refuse to measure on it.
    """
    if not keep_fractions or keep_fractions[0] != 1.0:
        raise ValueError("the first level must keep every triangle")
    reference = label_surface(mask, spacing, origin)
    # A hair under the limit so that floating-point rounding cannot tip the measured value over it.
    clamp = limit_mm * 0.98
    lod0 = smooth_within(reference, clamp)
    lod0_error = surface_error(lod0, reference, samples=samples)
    if lod0_error.max_mm > limit_mm:
        raise RuntimeError(f"smoothed mesh is {lod0_error.max_mm:.4f} mm from its label surface, over the {limit_mm} mm limit")
    lods: list[Lod] = [Lod(0, lod0, lod0_error, True)]
    for level, fraction in enumerate(keep_fractions[1:], start=1):
        mesh = decimate(lod0, fraction)
        error = surface_error(mesh, reference, samples=samples)
        lods.append(Lod(level, mesh, error, error.max_mm <= limit_mm + 1e-9))
    return MeshBuild(reference, lods, clamp)
