"""Phase 2B WP1: the true-colour volume of an OpenEar specimen, made ready for the browser.

Source: the micro-slicing stack (3 x 792 x 792 x N, 0.05 x 0.05 x 0.15 mm, already in the specimen
frame; see CLAUDE.md, WP0). This module turns it into
  * a levelled colour volume (per-slice gain from the epoxy, which is the same material everywhere),
  * RGBA tiers at 0.2, 0.15 and 0.1 mm (alpha 0 for epoxy, the cylinder edge and the black surround),
  * bricked, gzipped files (64 voxel bricks, empty bricks left out) with a JSON index,
  * normals from the registered CBCT (or, when a specimen has none, from the alpha surface).
Everything here is a pure function of arrays so that it can be tested without Zenodo.

Positions: voxel i of a volume with origin o and step s is centred at o + i * s (mm, specimen frame).

Derived from OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0.
"""
from __future__ import annotations

import gzip
from dataclasses import dataclass

import numpy as np
from scipy import ndimage

TIERS_MM = (0.2, 0.15, 0.1)
BRICK = 64
CAP_MARGIN_MM = 0.8  # the outer ring of the resin cylinder (edge strips, black notch) is dropped
CAP_RAMP_MM = 0.4


# ----------------------------------------------------------------------------------- colour and alpha
def alpha_of(rgb: np.ndarray) -> np.ndarray:
    """rgb float [3, ...] -> alpha 0..1: epoxy (pale, unsaturated) and the black surround are transparent."""
    mx, mn = rgb.max(0), rgb.min(0)
    sat = (mx - mn) / np.maximum(mx, 1.0)
    a = np.clip((sat - 0.14) / 0.12, 0.0, 1.0)
    a[mx < 40] = 0.0
    return a


@dataclass(frozen=True)
class Cylinder:
    cx: float  # mm, specimen frame
    cy: float
    radius: float


def fit_cylinder(rgb: np.ndarray, step_xy: float, origin_xy, every: int = 12) -> Cylinder:
    """The resin cylinder's axis and radius: median over slices of the filled disk of non-black pixels.
    rgb: [3, x, y, z] at a coarse step (0.2 mm is plenty)."""
    cxs, cys, rs = [], [], []
    for k in range(0, rgb.shape[3], every):
        mx = rgb[:, :, :, k].max(0)
        disk = ndimage.binary_fill_holes(ndimage.binary_opening(mx > 70, iterations=2))
        lab, n = ndimage.label(disk)
        if n == 0:
            continue
        d = lab == 1 + int(np.argmax(ndimage.sum(disk, lab, range(1, n + 1))))
        cx, cy = ndimage.center_of_mass(d)
        cxs.append(origin_xy[0] + cx * step_xy)
        cys.append(origin_xy[1] + cy * step_xy)
        rs.append(np.sqrt(d.sum() / np.pi) * step_xy)
    if len(rs) < 3:
        raise ValueError("no resin cylinder found in the colour volume")
    return Cylinder(float(np.median(cxs)), float(np.median(cys)), float(np.median(rs)))


def cap_weight(shape_xy, step_xy: float, origin_xy, cyl: Cylinder) -> np.ndarray:
    """[x, y] weight: 1 well inside the cylinder, 0 from `CAP_MARGIN_MM` short of its wall, with a short ramp."""
    x = origin_xy[0] + np.arange(shape_xy[0]) * step_xy - cyl.cx
    y = origin_xy[1] + np.arange(shape_xy[1]) * step_xy - cyl.cy
    r = np.hypot(x[:, None], y[None, :])
    return np.clip((cyl.radius - CAP_MARGIN_MM - r) / CAP_RAMP_MM, 0.0, 1.0).astype(np.float32)


def epoxy_reference(rgb: np.ndarray, step_xy: float, origin_xy, cyl: Cylinder, min_pixels: int = 400) -> np.ndarray:
    """Median colour of the epoxy in every slice: float [z, 3], NaN where the slice shows too little epoxy.
    rgb: [3, x, y, z] float."""
    x = origin_xy[0] + np.arange(rgb.shape[1]) * step_xy - cyl.cx
    y = origin_xy[1] + np.arange(rgb.shape[2]) * step_xy - cyl.cy
    inner = np.hypot(x[:, None], y[None, :]) < 0.8 * cyl.radius
    out = np.full((rgb.shape[3], 3), np.nan)
    for k in range(rgb.shape[3]):
        sl = rgb[:, :, :, k]
        mx, mn = sl.max(0), sl.min(0)
        ep = inner & (mx > 170) & ((mx - mn) / np.maximum(mx, 1.0) < 0.12)
        if ep.sum() >= min_pixels:
            out[k] = [np.median(sl[c][ep]) for c in range(3)]
    return out


def level_gains(ref: np.ndarray, limit: float = 0.10) -> tuple[np.ndarray, dict]:
    """Per-slice, per-channel gains that bring the epoxy to its overall median colour.
    The reference is smoothed along z (median of 9, then Gaussian sigma 3 slices) so that tissue-sized
    holes in it do not leak into the picture; gains are limited to 1 +- `limit`.
    Returns (gains [z, 3], diagnostics)."""
    good = ~np.isnan(ref[:, 0])
    diag = {"slices": int(len(ref)), "slices_with_epoxy": int(good.sum())}
    if good.sum() < max(10, 0.3 * len(ref)):
        diag["levelled"] = False
        return np.ones((len(ref), 3), np.float32), diag
    z = np.arange(len(ref))
    filled = np.stack([np.interp(z, z[good], ref[good, c]) for c in range(3)], 1)
    smooth = ndimage.gaussian_filter1d(ndimage.median_filter(filled, size=(9, 1), mode="nearest"), 3, axis=0, mode="nearest")
    target = np.median(smooth, 0)
    gains = np.clip(target / smooth, 1 - limit, 1 + limit).astype(np.float32)
    diag.update(
        levelled=True,
        target_rgb=[round(float(v), 1) for v in target],
        epoxy_range_before=[round(float(np.nanmin(ref)), 1), round(float(np.nanmax(ref)), 1)],
        epoxy_range_after=[round(float(np.nanmin(ref * gains)), 1), round(float(np.nanmax(ref * gains)), 1)],
        gain_min=round(float(gains.min()), 3),
        gain_max=round(float(gains.max()), 3),
    )
    return gains, diag


# --------------------------------------------------------------------------------------- resampling
def reduce_xy(vol: np.ndarray, f: int, gains: np.ndarray | None = None, chunk: int = 40) -> np.ndarray:
    """uint8 [3, x, y, z] -> float32 [3, x // f, y // f, z]: f x f area average in x and y, each source
    slice multiplied by its gain first. Worked in z chunks to keep the float copy small."""
    _, nx, ny, nz = vol.shape
    fx, fy = nx // f, ny // f
    out = np.empty((3, fx, fy, nz), np.float32)
    for z0 in range(0, nz, chunk):
        part = vol[:, : fx * f, : fy * f, z0 : z0 + chunk].astype(np.float32)
        if gains is not None:
            part *= gains[z0 : z0 + chunk].T[:, None, None, :]
        out[..., z0 : z0 + chunk] = part.reshape(3, fx, f, fy, f, part.shape[3]).mean(axis=(2, 4))
    return out


def resample_z(a: np.ndarray, step_z: float, target: float) -> np.ndarray:
    """float [3, x, y, z] at step_z -> the same at `target` mm along z (linear), first plane unchanged."""
    nz = int(np.floor((a.shape[3] - 1) * step_z / target)) + 1
    pos = np.arange(nz) * target / step_z
    i0 = np.minimum(np.floor(pos).astype(int), a.shape[3] - 2)
    w = (pos - i0).astype(np.float32)
    return a[..., i0] * (1 - w) + a[..., i0 + 1] * w


def tier_origin(origin, step, f: int) -> np.ndarray:
    """Centre of the first voxel of a tier built with an f x f block average (origin: native first centre)."""
    return np.asarray(origin, float) + np.array([(f - 1) / 2 * step[0], (f - 1) / 2 * step[1], 0.0])


def build_tier(vol, step, origin, target: float, gains, cyl: Cylinder) -> tuple[np.ndarray, np.ndarray]:
    """uint8 [3, x, y, z] at `step` -> (RGBA uint8 [4, x, y, z] at `target` mm isotropic, origin of its first voxel).
    The cylinder cap is applied to alpha; levelling to colour."""
    f = int(round(target / step[0]))
    if abs(f * step[0] - target) > 1e-6:
        raise ValueError(f"tier {target} mm is not a whole multiple of the in-plane step {step[0]}")
    a = resample_z(reduce_xy(vol, f, gains), step[2], target)
    org = tier_origin(origin, step, f)
    alpha = alpha_of(a) * cap_weight(a.shape[1:3], target, org[:2], cyl)[:, :, None]
    rgba = np.concatenate([np.clip(np.rint(a), 0, 255), np.rint(alpha * 255)[None]], 0).astype(np.uint8)
    return rgba, org


# ----------------------------------------------------------------------------------- tissue and crop
def main_tissue(alpha_u8: np.ndarray) -> np.ndarray:
    """Boolean mask of the specimen: the largest connected tissue body (after an opening), nothing floating."""
    a = ndimage.binary_opening(alpha_u8 > 127, iterations=2)
    lab, n = ndimage.label(a)
    if n == 0:
        raise ValueError("no tissue found in the colour volume")
    return lab == 1 + int(np.argmax(ndimage.sum(a, lab, range(1, n + 1))))


def box_of(mask: np.ndarray, origin, step: float, margin_mm: float) -> tuple[np.ndarray, np.ndarray]:
    """(lo_mm, hi_mm) corners of the mask's bounding box, grown by the margin."""
    idx = np.argwhere(mask)
    org = np.asarray(origin, float)
    return org + idx.min(0) * step - margin_mm, org + idx.max(0) * step + margin_mm


def crop_mm(arr: np.ndarray, origin, step: float, lo_mm, hi_mm) -> tuple[np.ndarray, np.ndarray]:
    """Crop arr [..., x, y, z] to the voxels inside the box (clipped); returns (crop, origin of its first voxel)."""
    org = np.asarray(origin, float)
    lo = np.maximum(np.floor((np.asarray(lo_mm) - org) / step + 1e-6).astype(int), 0)
    hi = np.minimum(np.ceil((np.asarray(hi_mm) - org) / step - 1e-6).astype(int) + 1, arr.shape[-3:])
    sl = (Ellipsis,) + tuple(slice(a, b) for a, b in zip(lo, hi))
    return arr[sl], org + lo * step


def sample_mask(mask, mask_origin, mask_step, shape, origin, step: float) -> np.ndarray:
    """Nearest-neighbour resampling of a boolean mask onto another grid (voxels outside it are False).
    mask_step is one number or one per axis."""
    ms = np.broadcast_to(np.asarray(mask_step, float), (3,))
    idx = []
    for i in range(3):
        p = (np.asarray(origin[i]) + np.arange(shape[i]) * step - mask_origin[i]) / ms[i]
        idx.append(np.rint(p).astype(int))
    ok = [(ix >= 0) & (ix < mask.shape[i]) for i, ix in enumerate(idx)]
    out = np.zeros(shape, bool)
    sub = mask[np.ix_(*[np.clip(ix, 0, mask.shape[i] - 1) for i, ix in enumerate(idx)])]
    out[:] = sub & ok[0][:, None, None] & ok[1][None, :, None] & ok[2][None, None, :]
    return out


# ------------------------------------------------------------------------------------------- bricks
def bricks_encode(arr: np.ndarray, brick: int = BRICK) -> tuple[bytes, dict]:
    """arr uint8 [c, x, y, z] -> (blob, index). Each brick is gzipped on its own, as interleaved
    channels with x fastest (the order a WebGL2 3D texture upload wants), and the blob is their concatenation.
    Bricks whose every value is zero are left out. index: dims, brick size, and for each stored brick
    [bx, by, bz, offset, length]; edge bricks are smaller (their size follows from dims)."""
    c, nx, ny, nz = arr.shape
    parts, entries, off = [], [], 0
    for bz in range(0, nz, brick):
        for by in range(0, ny, brick):
            for bx in range(0, nx, brick):
                piece = arr[:, bx : bx + brick, by : by + brick, bz : bz + brick]
                if not piece.any():
                    continue
                raw = np.ascontiguousarray(piece.transpose(3, 2, 1, 0)).tobytes()  # [z][y][x][c]
                gz = gzip.compress(raw, compresslevel=6, mtime=0)
                parts.append(gz)
                entries.append([bx // brick, by // brick, bz // brick, off, len(gz)])
                off += len(gz)
    index = {
        "channels": int(c),
        "dims": [int(nx), int(ny), int(nz)],
        "brick": int(brick),
        "bricks_total": int(-(-nx // brick) * -(-ny // brick) * -(-nz // brick)),
        "bricks_stored": len(entries),
        "bricks": entries,
        "layout": "per brick: gzip of [z][y][x][channel] uint8; bricks without any non-zero value are not stored",
    }
    return b"".join(parts), index


def bricks_decode(blob: bytes, index: dict) -> np.ndarray:
    """Inverse of bricks_encode: uint8 [c, x, y, z]."""
    c, (nx, ny, nz), b = index["channels"], index["dims"], index["brick"]
    out = np.zeros((c, nx, ny, nz), np.uint8)
    for bx, by, bz, off, ln in index["bricks"]:
        x0, y0, z0 = bx * b, by * b, bz * b
        sx, sy, sz = min(b, nx - x0), min(b, ny - y0), min(b, nz - z0)
        raw = np.frombuffer(gzip.decompress(blob[off : off + ln]), np.uint8).reshape(sz, sy, sx, c)
        out[:, x0 : x0 + sx, y0 : y0 + sy, z0 : z0 + sz] = raw.transpose(3, 2, 1, 0)
    return out


# ------------------------------------------------------------------------------------------ normals
def normals_volume(scalar: np.ndarray, step: float, smooth: float = 1.0, coarsen: int = 2) -> np.ndarray:
    """uint8 [4, x, y, z]: outward-from-bone surface normal * 0.5 + 0.5 (RGB) and edge strength (A), from the
    gradient of a scalar (CBCT value, or the alpha surface) on a grid `coarsen` times coarser than `scalar`.
    Normals vary slowly, so the coarse grid costs an eighth of the voxels."""
    c = ndimage.gaussian_filter(scalar.astype(np.float32), smooth)
    g = np.stack(np.gradient(c, step))
    mag = np.linalg.norm(g, axis=0)
    unit = -g / np.maximum(mag, 1e-6)
    h = [d // coarsen * coarsen for d in c.shape]

    def block(a):
        sh = a.shape[:-3] + (h[0] // coarsen, coarsen, h[1] // coarsen, coarsen, h[2] // coarsen, coarsen)
        return a[..., : h[0], : h[1], : h[2]].reshape(sh).mean(axis=(-5, -3, -1))

    u, m = block(unit), block(mag)
    edge = np.clip(np.rint(m / max(float(np.percentile(m, 99.5)), 1e-6) * 255), 0, 255)[None]
    return np.concatenate([np.clip(np.rint((u * 0.5 + 0.5) * 255), 0, 255), edge], 0).astype(np.uint8)


# ----------------------------------------------------------------------------------------- alignment
def mutual_information(a: np.ndarray, b: np.ndarray, bins_a: int, bins_b: int, range_a, range_b) -> float:
    h, _, _ = np.histogram2d(a, b, bins=[bins_a, bins_b], range=[range_a, range_b])
    p = h / max(h.sum(), 1)
    px, py = p.sum(1, keepdims=True), p.sum(0, keepdims=True)
    nz = p > 0
    return float((p[nz] * np.log(p[nz] / (px @ py)[nz])).sum())


def estimate_shift(positions, colour_vals, reference_at, bins_ref: int, range_ref, search: float = 0.4,
                   step: float = 0.05, rounds: int = 2) -> dict:
    """Global translation `s` (mm) such that colour at p matches the reference at p - s, by mutual information
    (coordinate search, one axis at a time). `reference_at(points) -> (values, ok)`.
    Returns shift, MI at zero and at the optimum, the MI curve of each axis, and whether the search edge was hit."""

    def mi(s):
        v, ok = reference_at(positions - s)
        if ok.sum() < 1000:
            return -1.0
        return mutual_information(v[ok], colour_vals[ok], bins_ref, 32, range_ref, (0, 256))

    s = np.zeros(3)
    mi0 = mi(s)
    cand = np.round(np.arange(-search, search + 1e-9, step), 4)
    curves = [[], [], []]
    for _ in range(rounds):
        for ax in range(3):
            vals = []
            for d in cand:
                q = s.copy()
                q[ax] = d
                vals.append(mi(q))
            s[ax] = cand[int(np.argmax(vals))]
            curves[ax] = [round(v, 5) for v in vals]
    return {
        "shift_mm": [round(float(v), 3) for v in s],
        "mi_zero": round(mi0, 5),
        "mi_best": round(mi(s), 5),
        "at_search_edge": bool((np.abs(s) >= search - 1e-9).any()),
        "curves": curves,
        "candidates": cand.tolist(),
    }


def orientation_check(positions, colour_vals, reference_at, bins_ref: int, range_ref) -> dict:
    """MI of the colour with the reference as is and with each axis mirrored about the sample centre.
    The identity must win clearly, otherwise the colour volume is not in the specimen frame."""
    ctr = positions.mean(0)
    out = {}
    for name, fl in (("identity", (1, 1, 1)), ("flip_x", (-1, 1, 1)), ("flip_y", (1, -1, 1)), ("flip_z", (1, 1, -1))):
        v, ok = reference_at(ctr + (positions - ctr) * np.array(fl))
        out[name] = round(mutual_information(v[ok], colour_vals[ok], bins_ref, 32, range_ref, (0, 256)), 5) if ok.sum() > 1000 else -1.0
    others = max(v for k, v in out.items() if k != "identity")
    out["identity_wins"] = bool(out["identity"] > 1.2 * others)
    return out

# --------------------------------------------------------------------------- CBCT density for alpha
def sample_on_grid(vol, spacing, origin, grid_origin, step: float, shape, chunk: int = 32) -> np.ndarray:
    """Linear sampling of `vol` (indexed [x, y, z], with its own spacing and origin) on a regular grid of
    `shape` voxels at `step` mm starting at `grid_origin`; outside the volume the nearest voxel is used.
    Worked in chunks of z planes so that the coordinate arrays stay small."""
    sp, org, go = np.asarray(spacing, float), np.asarray(origin, float), np.asarray(grid_origin, float)
    qx = (go[0] + np.arange(shape[0]) * step - org[0]) / sp[0]
    qy = (go[1] + np.arange(shape[1]) * step - org[1]) / sp[1]
    out = np.empty(shape, np.float32)
    for z0 in range(0, shape[2], chunk):
        qz = (go[2] + np.arange(z0, min(z0 + chunk, shape[2])) * step - org[2]) / sp[2]
        coords = np.stack(np.meshgrid(qx, qy, qz, indexing="ij")).reshape(3, -1)
        out[:, :, z0 : z0 + len(qz)] = ndimage.map_coordinates(vol, coords, order=1, mode="nearest").reshape(shape[0], shape[1], len(qz))
    return out


def two_class_threshold(values: np.ndarray, iterations: int = 50) -> float:
    """Isodata threshold: the midpoint between the means of the two classes it separates. Unlike Otsu it is not
    pulled towards the larger class, which matters here (epoxy is most of the pale voxels, cortex a minority)."""
    v = np.asarray(values, np.float64)
    t = float(np.median(v))
    for _ in range(iterations):
        lo, hi = v[v <= t], v[v > t]
        if len(lo) == 0 or len(hi) == 0:
            break
        nt = (lo.mean() + hi.mean()) / 2
        if abs(nt - t) < 0.05:
            break
        t = float(nt)
    return t


def cbct_alpha_levels(cbct_on_grid: np.ndarray, colour_alpha_u8: np.ndarray, inside_xy: np.ndarray) -> dict:
    """Epoxy and bone CBCT levels from the pale voxels (colour alpha under half) inside the cylinder:
    epoxy dominates them, cortex is the bright minority, so a two-class threshold splits the two.
    Returns epoxy level, threshold, ramp (lo, hi) and how many voxels the sample held; `usable` False when
    the two classes are not clearly apart."""
    amb = (colour_alpha_u8 < 128) & inside_xy[:, :, None]
    vals = cbct_on_grid[amb]
    if len(vals) < 5000:
        return {"usable": False, "reason": "too few pale voxels"}
    e = float(np.median(vals))
    t = two_class_threshold(vals)
    d = max(6.0, 0.25 * (t - e))
    ok = t > e + 8.0
    return {"usable": bool(ok), "epoxy_level": round(e, 1), "threshold": round(t, 1), "ramp": [round(t - d, 1), round(t + d, 1)],
            "sample_voxels": int(len(vals)), "pale_above_threshold_pct": round(float((vals > t).mean() * 100), 1)}


def apply_bone_alpha(rgba: np.ndarray, cbct_on_grid: np.ndarray, ramp, cap_xy: np.ndarray) -> float:
    """Raise alpha where the CBCT says bone (ramp from ramp[0] to ramp[1]), inside the cylinder cap.
    In place; returns the share of voxels that became opaque only because of the CBCT."""
    ba = np.clip((cbct_on_grid - ramp[0]) / (ramp[1] - ramp[0]), 0.0, 1.0) * cap_xy[:, :, None]
    new = np.rint(ba * 255).astype(np.uint8)
    gained = float(((new > 127) & (rgba[3] <= 127)).mean())
    rgba[3] = np.maximum(rgba[3], new)
    return gained

def radial_distance(shape_xy, step_xy: float, origin_xy, cyl: Cylinder) -> np.ndarray:
    """[x, y] distance (mm) from the cylinder axis."""
    x = origin_xy[0] + np.arange(shape_xy[0]) * step_xy - cyl.cx
    y = origin_xy[1] + np.arange(shape_xy[1]) * step_xy - cyl.cy
    return np.hypot(x[:, None], y[None, :])


def radial_profile(cbct: np.ndarray, epoxy: np.ndarray, r_xy: np.ndarray, width: float = 1.0, rounds: int = 3):
    """CBCT value of the epoxy by distance from the cylinder axis (cupping: the embedding medium reads darker towards
    the wall on some scans, ETA most). Per radial bin the median of the confident-epoxy voxels, with voxels more than
    two robust sigmas above it dropped over a few rounds so that cortex that looks like epoxy cannot lift it.
    Returns (bin centres mm, profile); bins with too few voxels are filled by interpolation."""
    edges = np.arange(0.0, float(r_xy.max()) + width, width)
    centres = (edges[:-1] + edges[1:]) / 2
    idx = np.clip(np.digitize(r_xy, edges) - 1, 0, len(centres) - 1)
    sel = epoxy.copy()
    prof = np.full(len(centres), np.nan)
    for _ in range(rounds):
        sig = np.full(len(centres), np.nan)
        for k in range(len(centres)):
            v = cbct[sel & (idx == k)[:, :, None]]
            if len(v) >= 200:
                prof[k] = np.median(v)
                sig[k] = max(1.4826 * np.median(np.abs(v - prof[k])), 2.0)
        good = ~np.isnan(prof)
        if good.sum() < 3:
            raise ValueError("too little epoxy to measure the CBCT baseline")
        pxy = np.interp(r_xy, centres[good], prof[good])
        sxy = np.interp(r_xy, centres[good], np.where(np.isnan(sig), np.nanmedian(sig), sig)[good])
        sel = epoxy & (cbct < (pxy + 2 * sxy)[:, :, None])
    good = ~np.isnan(prof)
    return centres, np.interp(centres, centres[good], prof[good])


def baseline_xy(centres: np.ndarray, profile: np.ndarray, r_xy: np.ndarray) -> np.ndarray:
    """[x, y] baseline from a radial profile (constant beyond its ends)."""
    return np.interp(r_xy, centres, profile).astype(np.float32)
