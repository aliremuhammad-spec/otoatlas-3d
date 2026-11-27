"""Phase 2B WP1: the colour pipeline on synthetic volumes (no Zenodo needed)."""
import numpy as np
import pytest
from scipy import ndimage

from otopipe import colour

STEP = (0.2, 0.2, 0.6)  # coarse stand-in for 0.05 x 0.05 x 0.15 mm, same 1:1:3 anisotropy


def synthetic(nx=100, ny=100, nz=40, drift=0.0, seed=0):
    """A resin cylinder (cream epoxy), a brown tissue block and a black surround, in uint8 [3, x, y, z]."""
    rng = np.random.default_rng(seed)
    x, y = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
    cx, cy, R = nx / 2 - 0.5, ny / 2 - 0.5, 0.45 * nx
    disk = np.hypot(x - cx, y - cy) < R
    vol = np.zeros((3, nx, ny, nz), np.float32)
    for k in range(nz):
        g = 1 + drift * np.sin(k / nz * 2 * np.pi)
        sl = np.zeros((3, nx, ny), np.float32)
        sl[:, disk] = np.array([222, 224, 208])[:, None]
        tissue = (abs(x - cx) < 0.18 * nx) & (abs(y - cy) < 0.2 * ny)
        sl[:, tissue] = np.array([170, 140, 70])[:, None]
        vol[:, :, :, k] = np.clip(sl * g + rng.normal(0, 1.5, sl.shape), 0, 255)
    return vol.astype(np.uint8), Cyl(cx * STEP[0], cy * STEP[1], R * STEP[0])


Cyl = colour.Cylinder


def test_alpha_epoxy_tissue_black():
    rgb = np.array([[222, 170, 5], [224, 140, 5], [208, 70, 5]], np.float32)[:, :, None]
    a = colour.alpha_of(rgb)[:, 0]
    assert a[0] == 0.0 and a[1] == 1.0 and a[2] == 0.0


def test_fit_cylinder_recovers_axis_and_radius():
    vol, cyl = synthetic()
    got = colour.fit_cylinder(vol.astype(np.float32), STEP[0], (0.0, 0.0), every=4)
    assert abs(got.cx - cyl.cx) < 0.15 and abs(got.cy - cyl.cy) < 0.15
    assert abs(got.radius - cyl.radius) < 0.2


def test_cap_weight_zero_near_wall_one_inside():
    cyl = Cyl(10.0, 10.0, 8.0)
    w = colour.cap_weight((100, 100), 0.2, (0.0, 0.0), cyl)
    assert w[50, 50] == 1.0 and w[50, 98] == 0.0 and w[0, 0] == 0.0
    assert w[50, 50 + int(round((8.0 - 0.9) / 0.2))] == 1.0 or w[50, 50 + 34] > 0.5


def test_levelling_removes_epoxy_drift():
    vol, cyl = synthetic(drift=0.06)
    f = vol.astype(np.float32)
    ref = colour.epoxy_reference(f, STEP[0], (0.0, 0.0), cyl)
    before = np.nanmax(ref[:, 0]) - np.nanmin(ref[:, 0])
    gains, diag = colour.level_gains(ref)
    assert diag["levelled"]
    after = ref * gains
    assert np.nanmax(after[:, 0]) - np.nanmin(after[:, 0]) < 0.35 * before
    assert gains.min() >= 0.9 - 1e-6 and gains.max() <= 1.1 + 1e-6


def test_levelling_leaves_data_alone_without_epoxy():
    gains, diag = colour.level_gains(np.full((50, 3), np.nan))
    assert not diag["levelled"] and np.all(gains == 1)


def test_tier_voxel_centres_match_positions():
    """A colour ramp along x and z: the tier value at a voxel centre equals the ramp at that position."""
    nx, ny, nz = 80, 80, 30
    step = (0.05, 0.05, 0.15)
    xs = (np.arange(nx) * step[0])[:, None, None]
    zs = (np.arange(nz) * step[2])[None, None, :]
    vol = np.zeros((3, nx, ny, nz), np.uint8)
    vol[0] = np.broadcast_to(np.clip(xs * 50, 0, 255), (nx, ny, nz))
    vol[1] = np.broadcast_to(np.clip(zs * 40, 0, 255), (nx, ny, nz))
    vol[2] = 90
    cyl = Cyl(2.0, 2.0, 1000.0)  # cap far away: no effect
    for target in (0.2, 0.15, 0.1):
        rgba, org = colour.build_tier(vol, step, (0.0, 0.0, 0.0), target, None, cyl)
        i, k = 7, 5
        px, pz = org[0] + i * target, org[2] + k * target
        assert abs(rgba[0, i, 3, 3] - px * 50) < 1.0, target
        assert abs(rgba[1, 3, 3, k] - pz * 40) < 1.0, target


def test_tier_rejects_non_multiple():
    vol = np.zeros((3, 20, 20, 6), np.uint8)
    with pytest.raises(ValueError):
        colour.build_tier(vol, (0.05, 0.05, 0.15), (0, 0, 0), 0.12, None, Cyl(0, 0, 1))


def test_main_tissue_drops_floaters_and_crop_box():
    a = np.zeros((60, 60, 60), np.uint8)
    a[10:30, 10:30, 10:30] = 255
    a[50:53, 50:53, 50:53] = 255  # debris
    keep = colour.main_tissue(a)
    assert keep[20, 20, 20] and not keep[51, 51, 51]
    lo, hi = colour.box_of(keep, (1.0, 1.0, 1.0), 0.2, 0.0)
    assert np.allclose(lo, 1.0 + 10 * 0.2) and np.allclose(hi, 1.0 + 29 * 0.2)
    sub, org = colour.crop_mm(a, (1.0, 1.0, 1.0), 0.2, lo, hi)
    assert sub.shape == (20, 20, 20) and np.allclose(org, lo)


def test_sample_mask_between_grids():
    m = np.zeros((20, 20, 20), bool)
    m[5:10, 5:10, 5:10] = True
    out = colour.sample_mask(m, (0, 0, 0), 0.4, (40, 40, 40), (0, 0, 0), 0.2)
    assert out[12, 12, 12] and not out[2, 2, 2] and not out[30, 30, 30]


def test_bricks_roundtrip_and_empty_bricks_left_out():
    rng = np.random.default_rng(1)
    arr = np.zeros((4, 150, 90, 70), np.uint8)
    arr[:, 0:50, 0:50, 0:40] = rng.integers(1, 255, (4, 50, 50, 40))
    blob, idx = colour.bricks_encode(arr)
    assert idx["bricks_stored"] < idx["bricks_total"]
    assert idx["bricks_total"] == 3 * 2 * 2
    assert np.array_equal(colour.bricks_decode(blob, idx), arr)


def test_bricks_all_zero_stores_nothing():
    blob, idx = colour.bricks_encode(np.zeros((4, 70, 70, 70), np.uint8))
    assert blob == b"" and idx["bricks_stored"] == 0


def smooth_asymmetric(shape=(60, 70, 50), seed=3):
    v = ndimage.gaussian_filter(np.random.default_rng(seed).normal(size=shape), 3)
    return (255 * (v - v.min()) / (v.max() - v.min())).astype(np.float32)


def test_estimate_shift_recovers_known_translation():
    ref = smooth_asymmetric()
    step, org = 0.2, np.zeros(3)
    true = np.array([0.15, -0.10, 0.05])  # colour at p matches reference at p - true

    def reference_at(pts):
        q = (pts - org) / step
        ok = np.all((q >= 0) & (q <= np.array(ref.shape) - 1), 1)
        return ndimage.map_coordinates(ref, q.clip(0, np.array(ref.shape) - 1).T, order=1), ok

    rng = np.random.default_rng(4)
    pts = org + rng.uniform(3, 8, (40000, 3))
    colour_vals = reference_at(pts - true)[0]
    got = colour.estimate_shift(pts, colour_vals, reference_at, 32, (0, 256), search=0.3)
    assert np.allclose(got["shift_mm"], true, atol=0.051)
    assert got["mi_best"] >= got["mi_zero"]


def test_orientation_check_identity_wins_and_flip_is_caught():
    ref = smooth_asymmetric()
    step = 0.2

    def reference_at(pts):
        q = pts / step
        ok = np.all((q >= 0) & (q <= np.array(ref.shape) - 1), 1)
        return ndimage.map_coordinates(ref, q.clip(0, np.array(ref.shape) - 1).T, order=1), ok

    pts = np.random.default_rng(5).uniform(2, 9, (40000, 3))
    vals = reference_at(pts)[0]
    assert colour.orientation_check(pts, vals, reference_at, 32, (0, 256))["identity_wins"]
    flipped = reference_at(pts.mean(0) + (pts - pts.mean(0)) * np.array([-1, 1, 1]))[0]
    assert not colour.orientation_check(pts, flipped, reference_at, 32, (0, 256))["identity_wins"]


def test_normals_point_away_from_a_bright_ball():
    n = 40
    g = np.indices((n, n, n)).astype(np.float32) - n / 2
    ball = (np.linalg.norm(g, axis=0) < 10) * 200.0
    nrm = colour.normals_volume(ball, 0.2, smooth=1.0, coarsen=2)
    assert nrm.shape == (4, 20, 20, 20)
    # a point on the +x side of the ball, outside surface: the normal's x component is positive
    assert nrm[0, 15, 10, 10] > 140 and nrm[0, 5, 10, 10] < 115


def test_sample_on_grid_matches_positions():
    g = np.indices((30, 30, 30)).astype(np.float32)
    vol = g[0] * 2 + g[2] * 0.5  # linear ramp: exact under linear interpolation
    got = colour.sample_on_grid(vol, (0.2, 0.2, 0.3), (1.0, 1.0, 1.0), (1.4, 1.2, 1.9), 0.1, (10, 8, 40), chunk=7)
    x = (1.4 + np.arange(10) * 0.1 - 1.0) / 0.2
    z = (1.9 + np.arange(40) * 0.1 - 1.0) / 0.3
    assert np.allclose(got[:, 3, 5], x * 2 + z[5] * 0.5, atol=1e-3)


def test_two_class_threshold_splits_unbalanced_modes():
    rng = np.random.default_rng(0)
    v = np.concatenate([rng.normal(60, 5, 9000), rng.normal(200, 10, 1000)])
    assert 100 < colour.two_class_threshold(v) < 160


def test_cbct_alpha_lifts_pale_bone_but_not_epoxy():
    rng = np.random.default_rng(2)
    shape = (40, 40, 20)
    cb = rng.normal(60, 4, shape).astype(np.float32)
    cb[10:20, 10:20, :] = rng.normal(210, 8, (10, 10, 20))  # dense, pale bone
    alpha = np.zeros(shape, np.uint8)  # the colour alone makes everything transparent
    rgba = np.zeros((4,) + shape, np.uint8)
    inside = np.ones(shape[:2], bool)
    lv = colour.cbct_alpha_levels(cb, alpha, inside)
    assert lv["usable"] and 60 < lv["threshold"] < 210
    gained = colour.apply_bone_alpha(rgba, cb, lv["ramp"], np.ones(shape[:2], np.float32))
    assert rgba[3, 15, 15, 5] == 255 and rgba[3, 30, 30, 5] == 0
    assert 0.04 < gained < 0.08


def test_cbct_alpha_unusable_without_two_classes():
    cb = np.random.default_rng(3).normal(60, 4, (40, 40, 20)).astype(np.float32)
    lv = colour.cbct_alpha_levels(cb, np.zeros(cb.shape, np.uint8), np.ones(cb.shape[:2], bool))
    assert not lv["usable"]


def test_radial_baseline_rescues_a_cupped_cbct():
    """Epoxy reads 100 at the axis and 60 at the wall; pale cortex is +45 above the local epoxy. A single global
    threshold cannot separate them, the radial baseline can."""
    rng = np.random.default_rng(7)
    n = 80
    cyl = Cyl(8.0, 8.0, 7.5)
    r = colour.radial_distance((n, n), 0.2, (0.0, 0.0), cyl)
    base = 100 - 40 * (r / 7.5) ** 2
    cb = base[:, :, None] + rng.normal(0, 3, (n, n, 12))
    bone = np.zeros((n, n, 12), bool)
    bone[30:40, 10:25, :] = True      # near the axis
    bone[55:65, 40:60, :] = True      # near the wall
    cb[bone] += 45
    epoxy = ~bone & (r < 7.0)[:, :, None]
    centres, prof = colour.radial_profile(cb, epoxy, r)
    assert abs(np.interp(0.0, centres, prof) - 100) < 4 and abs(np.interp(6.5, centres, prof) - 70) < 8
    resid = cb - colour.baseline_xy(centres, prof, r)[:, :, None]
    inside = r < 7.0
    lv = colour.cbct_alpha_levels(resid, np.zeros(cb.shape, np.uint8), inside)
    assert lv["usable"] and 10 < lv["threshold"] < 40
    # the same data without the baseline: not separable
    assert not colour.cbct_alpha_levels(cb, np.zeros(cb.shape, np.uint8), inside)["usable"]


def test_cbct_alpha_ignores_real_air_among_the_pale_voxels():
    rng = np.random.default_rng(11)
    shape = (60, 60, 30)
    cb = rng.normal(0, 4, shape).astype(np.float32)          # epoxy, residual about 0
    cb[:, :18, :] = rng.normal(-60, 6, (60, 18, 30))         # air cells: a sixth of the pale voxels
    cb[10:25, 30:45, :] = rng.normal(55, 6, (15, 15, 30))    # pale cortex
    lv = colour.cbct_alpha_levels(cb, np.zeros(shape, np.uint8), np.ones(shape[:2], bool))
    assert lv["usable"] and 10 < lv["threshold"] < 45, lv
