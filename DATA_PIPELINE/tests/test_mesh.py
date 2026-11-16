"""Ground-truth tests: phantoms with analytic surfaces, run through the real pipeline."""
import numpy as np
import pytest

from otopipe import mesh as M
from otopipe import phantoms as P

OPENEAR_SPACING = (0.125, 0.125, 0.125)  # OpenEar segmentations
MICROCT_SPACING = (0.06, 0.06, 0.06)  # Bern micro-CT
CLINICAL_SPACING = (0.15, 0.15, 0.2)  # Bern clinical CT


def radial_error(mesh, radius, centre=(0.0, 0.0, 0.0)):
    return np.abs(np.linalg.norm(mesh.vertices - np.asarray(centre), axis=1) - radius)


@pytest.fixture(scope="module")
def sphere_build():
    mask, origin = P.ellipsoid((4.0, 4.0, 4.0), OPENEAR_SPACING)
    return mask, origin, M.build_lods(mask, OPENEAR_SPACING, origin, limit_mm=M.INNER_EAR_LIMIT_MM)


def test_label_surface_is_closed_and_in_millimetres(sphere_build):
    mask, _, build = sphere_build
    ref = build.label_surface
    assert ref.is_watertight
    voxel_volume = float(np.prod(OPENEAR_SPACING))
    # Marching cubes at 0.5 cuts corners of the outermost voxels, so its volume sits
    # slightly below the voxel count; 2 % covers that for a 4 mm sphere.
    assert ref.volume == pytest.approx(mask.sum() * voxel_volume, rel=0.02)
    assert radial_error(ref, 4.0).max() < max(OPENEAR_SPACING)


def test_lod0_stays_within_the_inner_ear_limit(sphere_build):
    _, _, build = sphere_build
    lod0 = build.lods[0]
    assert lod0.level == 0
    assert lod0.within_limit
    assert lod0.error.max_mm <= M.INNER_EAR_LIMIT_MM + 1e-9


def test_smoothing_preserves_volume_and_moves_towards_the_true_surface(sphere_build):
    _, _, build = sphere_build
    ref, lod0 = build.label_surface, build.lods[0].mesh
    assert lod0.is_watertight
    assert lod0.volume == pytest.approx(ref.volume, rel=0.005)
    # The smoothed mesh must agree with the analytic sphere better than the staircase does.
    assert radial_error(lod0, 4.0).mean() < radial_error(ref, 4.0).mean()
    assert lod0.volume == pytest.approx(4 / 3 * np.pi * 4.0**3, rel=0.01)


def test_lod_chain_is_measured_and_coarser_levels_never_report_less_error(sphere_build):
    _, _, build = sphere_build
    faces = [lod.mesh.faces.shape[0] for lod in build.lods]
    assert faces == sorted(faces, reverse=True)
    assert faces[-1] < 0.15 * faces[0]
    errors = [lod.error.max_mm for lod in build.lods]
    assert all(e > 0 for e in errors)
    assert errors[-1] >= errors[0] - 1e-6
    for lod in build.lods:
        assert lod.within_limit == (lod.error.max_mm <= M.INNER_EAR_LIMIT_MM + 1e-9)


def test_thin_canal_like_torus_at_microct_resolution_keeps_its_volume():
    # Tube radius 0.4 mm is of the order of a semicircular canal lumen; Laplacian
    # smoothing would visibly shrink it. Taubin smoothing with the clamp must not.
    mask, origin = P.torus(major=3.2, minor=0.4, spacing=MICROCT_SPACING)
    build = M.build_lods(mask, MICROCT_SPACING, origin, keep_fractions=(1.0,))
    lod0 = build.lods[0]
    assert lod0.within_limit
    assert lod0.mesh.volume == pytest.approx(build.label_surface.volume, rel=0.01)
    assert lod0.mesh.volume == pytest.approx(2 * np.pi**2 * 3.2 * 0.4**2, rel=0.03)


def test_anisotropic_spacing_and_origin_are_respected():
    centre = (-6.94, -84.35, -54.33)  # a realistic scanner-space offset
    radii = (3.0, 2.0, 1.5)
    mask, origin = P.ellipsoid(radii, CLINICAL_SPACING, centre=centre)
    ref = M.label_surface(mask, CLINICAL_SPACING, origin)
    extent = ref.bounds[1] - ref.bounds[0]
    assert np.allclose(extent, 2 * np.asarray(radii), atol=max(CLINICAL_SPACING))
    assert np.allclose(ref.centroid, centre, atol=0.02)


def test_error_measure_detects_a_known_offset():
    mask, origin = P.ellipsoid((2.0, 2.0, 2.0), OPENEAR_SPACING)
    ref = M.label_surface(mask, OPENEAR_SPACING, origin)
    shifted = ref.copy()
    shifted.apply_translation((0.3, 0.0, 0.0))
    error = M.surface_error(shifted, ref, samples=5000)
    assert error.max_mm == pytest.approx(0.3, abs=0.01)


def test_empty_label_is_rejected():
    with pytest.raises(ValueError):
        M.label_surface(np.zeros((4, 4, 4), dtype=bool), OPENEAR_SPACING)


def rough_sphere():
    """A sphere whose surface voxels are randomly flipped, like a hand-drawn segmentation."""
    from scipy import ndimage as ndi

    mask, origin = P.ellipsoid((2.0, 2.0, 2.0), OPENEAR_SPACING)
    shell = ndi.binary_dilation(mask) & ~ndi.binary_erosion(mask)
    rough = mask.copy()
    rough[shell & (np.random.default_rng(0).random(mask.shape) < 0.3)] ^= True
    labelled, _ = ndi.label(rough)
    return labelled == np.argmax(np.bincount(labelled.ravel())[1:]) + 1, origin


def test_rough_segmentation_stays_within_the_limit_on_both_sides():
    # Regression: on real OpenEar anatomy, clamping each vertex to its *nearest* point on
    # the label surface let one-voxel spikes collapse, and the label surface ended up
    # 0.09 mm from the mesh. Bounding each vertex's own displacement prevents that.
    mask, origin = rough_sphere()
    build = M.build_lods(mask, OPENEAR_SPACING, origin, keep_fractions=(1.0,), samples=20000)
    lod0 = build.lods[0]
    assert lod0.within_limit
    assert lod0.error.max_mm <= M.INNER_EAR_LIMIT_MM
    assert build.clamp_mm <= M.INNER_EAR_LIMIT_MM
    moved = np.linalg.norm(lod0.mesh.vertices - build.label_surface.vertices, axis=1)
    assert moved.max() <= M.INNER_EAR_LIMIT_MM
    assert moved.mean() > 0.01  # it did smooth


def test_first_level_must_be_full_resolution():
    mask, origin = P.ellipsoid((1.0, 1.0, 1.0), OPENEAR_SPACING)
    with pytest.raises(ValueError):
        M.build_lods(mask, OPENEAR_SPACING, origin, keep_fractions=(0.5,))
