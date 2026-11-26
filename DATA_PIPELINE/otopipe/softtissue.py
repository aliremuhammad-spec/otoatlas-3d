"""Schematic muscles, tendons and ligaments of the middle ear, placed on the specimen.

No dataset labels these soft tissues. Each one is drawn as a tube of textbook thickness,
and only its ends come from the specimen, by these rules (directions from the anatomical
frame of otopipe/ossicles.py):

Ligaments run from a point on an ossicle part, in a stated direction, to the first bone
of the specimen's bone label met within a stated reach (or the full reach when none is met):
- superior malleal: top of the malleus head, upwards, 4 mm;
- anterior malleal: most anterior point of the malleus neck, forwards, 5 mm;
- lateral malleal: most lateral point of the malleus neck, outwards and a little up, 4 mm;
- superior incudal: top of the incus body, upwards, 4 mm;
- posterior incudal: tip of the incus short process, backwards, 3 mm;
- annular ligament: a 0.2 mm ring around the footplate's rim, in the footplate's plane.

Tendons and muscles:
- stapedius tendon: from the back of the stapes head and neck to a point 2 mm behind and
  0.5 mm below it (the pyramidal eminence); the muscle: from there down 7 mm, following the
  descending part of the facial nerve 1 mm in front of and medial to it;
- tensor tympani tendon: from the upper end of the malleus handle on its medial side,
  medially to the first bone (the cochleariform process on the medial wall), 4 mm at most;
  the muscle: from there forwards 12 mm, medially and downwards along its semicanal, in
  whichever of a few directions near the textbook one crosses the nerve and labyrinth least.

Mucosal folds and the tympanic plexus:
- anterior and posterior malleal folds: thin sheets (0.08 mm) spanning the triangle between
  the tip of the lateral process, the middle of the malleus neck, and the front or back
  end of the membrane's upper rim (the tympanic spines at the notch of Rivinus);
- tympanic plexus (Jacobson's nerve): a 0.12 mm thread 0.35 mm off the surface of the
  promontory (the most lateral part of the cochlea within 3 mm of the umbo): from 3 mm
  below the promontory's summit, over it, up 2.5 mm, then forwards and up 5 mm as the
  lesser petrosal nerve, pushed off the nerve and labyrinth where it comes within 0.35 mm.

Where a tube would still pass through the specimen's facial nerve or labyrinth, those voxels
are removed, so it lies against them rather than through them.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from .membranous import GRID_MM, _densify, _tube


@dataclass(frozen=True)
class SoftTissue:
    parts: dict  # name -> (mask, origin) on GRID_MM
    report: dict


def _pts(mask, spacing, origin) -> np.ndarray:
    return np.asarray(origin, float) + np.argwhere(mask) * np.asarray(spacing, float)


def _unit(v) -> np.ndarray:
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


class _Bone:
    """Look-ups in the bone label: is a point in bone?"""

    def __init__(self, label):
        self.mask, sp, org = label
        self.sp = np.asarray(sp, float)
        self.org = np.asarray(org, float)

    def inside(self, p) -> bool:
        i = np.rint((np.asarray(p) - self.org) / self.sp).astype(int)
        if (i < 0).any() or (i >= self.mask.shape).any():
            return False
        return bool(self.mask[tuple(i)])

    def reach(self, start, direction, max_mm, skip_mm=0.3, stop_near=None) -> tuple[np.ndarray, bool]:
        """First bone along a ray (after skip_mm, so the ossicle's own neighbourhood does not
        count), or the first point within 1 mm of `stop_near` (a KD-tree), or the end of the
        ray. Returns the end point and whether a wall was met."""
        d = _unit(direction)
        for t in np.arange(skip_mm, max_mm + 1e-9, 0.1):
            p = np.asarray(start) + t * d
            if self.inside(p) or (stop_near is not None and stop_near.query(p)[0] <= 1.0):
                return p, True
        return np.asarray(start) + max_mm * d, False


def _clearance(a, b, tree) -> float:
    """Smallest distance from the segment a-b to the points in `tree`."""
    path = _densify(np.array([a, b]), 0.1)
    return float(tree.query(path)[0].min())


def _tube_tapered(points: np.ndarray, radii: np.ndarray):
    """Like a tube, with a radius for every path point."""
    r = float(radii.max())
    lo = points.min(axis=0) - r - 2 * GRID_MM
    hi = points.max(axis=0) + r + 2 * GRID_MM
    shape = tuple(int(v) for v in np.ceil((hi - lo) / GRID_MM) + 1)
    seed = np.full(shape, -1, int)
    idx = np.rint((points - lo) / GRID_MM).astype(int)
    seed[tuple(idx.T)] = np.arange(len(points))
    dist, nearest = ndimage.distance_transform_edt(seed < 0, sampling=GRID_MM, return_indices=True)
    which = seed[tuple(nearest)]
    return dist <= radii[which], tuple(float(v) for v in lo)


def _band(a, b, radius):
    return _tube(_densify(np.array([a, b]), GRID_MM / 2), radius)


def _sheet(a, b, c, thickness):
    """A flat triangle a-b-c of the given thickness on the fine grid."""
    tri = np.array([a, b, c], float)
    lo = tri.min(axis=0) - thickness - 2 * GRID_MM
    hi = tri.max(axis=0) + thickness + 2 * GRID_MM
    shape = tuple(int(v) for v in np.ceil((hi - lo) / GRID_MM) + 1)
    g = lo + np.stack(np.indices(shape), axis=-1) * GRID_MM
    n = np.cross(b - a, c - a)
    n /= np.linalg.norm(n)
    near_plane = np.abs((g - a) @ n) <= thickness / 2 + GRID_MM / 2
    # Inside the triangle: barycentric coordinates of the point's projection.
    v0, v1 = b - a, c - a
    w = g - a
    d00, d01, d11 = v0 @ v0, v0 @ v1, v1 @ v1
    d20, d21 = w @ v0, w @ v1
    den = d00 * d11 - d01 * d01
    v = (d11 * d20 - d01 * d21) / den
    u = (d00 * d21 - d01 * d20) / den
    inside = (v >= 0) & (u >= 0) & (u + v <= 1)
    return near_plane & inside, tuple(float(x) for x in lo)


def build(parts: dict, spacings: dict, facial_nerve, bone, frame, labyrinth_points, membrane=None,
          cochlea_points=None) -> SoftTissue:
    """`parts` maps bone name ('malleus', 'incus', 'stapes') to its part masks and origins
    (from otopipe.ossicles), `spacings` maps bone name to its voxel spacing; `facial_nerve`
    and `bone` are (mask, spacing, origin) labels."""
    L, A, S = frame.lateral, frame.anterior, frame.superior
    B = _Bone(bone)
    labyrinth = cKDTree(labyrinth_points)
    nerve = cKDTree(_pts(*facial_nerve))
    out, report = {}, {"rule": "otopipe/softtissue.py", "grid_mm": GRID_MM}

    def part(bone_name, part_name):
        mask, origin = parts[bone_name][part_name]
        return _pts(mask, spacings[bone_name], origin)

    def ligament(name, start, direction, reach, radius):
        end, met = B.reach(start, direction, reach)
        out[name] = _band(start, end, radius)
        report[name] = {"length_mm": round(float(np.linalg.norm(end - start)), 2), "reached_bone": met}

    if "malleus" in parts:
        head, neck, handle = part("malleus", "head"), part("malleus", "neck"), part("malleus", "handle")
        ligament("superior_malleal_ligament", head[np.argmax(head @ S)], S, 4.0, 0.15)
        ligament("anterior_malleal_ligament", neck[np.argmax(neck @ A)], A, 5.0, 0.2)
        ligament("lateral_malleal_ligament", neck[np.argmax(neck @ L)], L + 0.5 * S, 4.0, 0.15)
        # Tensor tympani: upper handle, medial side, then medially to the medial wall
        # (bone, or the labyrinth's surface where the bone label has a gap).
        # Where the label has no wall, the nerve and the labyrinth still must not be crossed:
        # among a few starting heights and directions, the one that keeps clear of both.
        for pct in (80, 70, 60, 50):
            top = handle[handle @ S >= np.percentile(handle @ S, pct)]
            start = top[np.argmin(top @ L)]
            end, met = B.reach(start, -L, 4.0, stop_near=labyrinth)
            if _clearance(start, end, nerve) >= 0.75:
                break
        out["tensor_tympani_tendon"] = _band(start, end, 0.15)
        # Forwards along its semicanal, above and parallel to the Eustachian tube, sloping
        # down as it goes forwards; textbook direction first, then the clearest nearby one.
        # The semicanal runs above the cochlea's basal turn: the muscle may start up to 1.5 mm
        # above the tendon's medial end, the least lift that keeps it off the labyrinth wins.
        wall = end
        best = None
        for lift in (0.0, 0.5, 1.0, 1.5):
            origin_pt = end + lift * S
            for a in (-0.35, -0.2, -0.05):  # never lateral: the semicanal runs forwards and medially
                for b in (-0.5, -0.3, -0.15, 0.0):
                    tip = origin_pt + 12.0 * _unit(A + a * L + b * S)
                    path = _densify(np.array([origin_pt, tip]), 0.2)
                    radii = np.clip(0.2 + np.linalg.norm(path - origin_pt, axis=1) * 0.1, 0.2, 0.45)
                    near = np.minimum(nerve.query(path)[0], labyrinth.query(path)[0])
                    crossing = float(np.mean(near < radii + 0.1)) + 0.05 * lift
                    if best is None or crossing < best[0] - 0.02:
                        best = (crossing, tip, origin_pt)
        end = best[2]
        tip = best[1]
        if np.linalg.norm(end - wall) > 1e-6:  # the tendon turns up at the wall to the muscle's start
            out["tensor_tympani_tendon"] = _tube(_densify(np.array([start, wall, end]), GRID_MM / 2), 0.15)
        # Thin where it leaves the cochleariform process, the belly about 0.9 mm across (drawn
        # slimmer than life, about 2 mm, so it stays in its narrow corridor).
        path = _densify(np.array([end, tip]), GRID_MM / 2)
        along = np.linalg.norm(path - end, axis=1)
        out["tensor_tympani_muscle"] = _tube_tapered(path, np.clip(0.2 + along * 0.1, 0.2, 0.45))
        report["tensor_tympani"] = {"tendon_mm": round(float(np.linalg.norm(end - start)), 2), "reached_bone": met}
        report["tensor_tympani"]["muscle_path_touching"] = round(best[0], 2)
    if "malleus" in parts and membrane is not None:
        lp = part("malleus", "lateral_process")
        tip = lp[np.argmax(lp @ L)]
        neck_mid = part("malleus", "neck").mean(axis=0)
        tm = _pts(*membrane)
        rim = tm[tm @ S >= np.percentile(tm @ S, 92)]  # the membrane's upper rim
        for name, pick in (("anterior_malleal_fold", np.argmax), ("posterior_malleal_fold", np.argmin)):
            spine = rim[pick(rim @ A)]
            out[name] = _sheet(tip, neck_mid, spine, 0.08)
            report[name] = {"to_spine_mm": round(float(np.linalg.norm(spine - tip)), 2)}
    if cochlea_points is not None and len(cochlea_points):
        cochlea = cKDTree(cochlea_points)
        # The promontory faces the membrane: its summit is the most lateral cochlear point
        # within 3 mm (forwards, backwards, up, down) of the umbo.
        rel = cochlea_points - frame.umbo
        facing = cochlea_points[(np.abs(rel @ A) < 3.0) & (np.abs(rel @ S) < 3.0)]
        if len(facing) == 0:
            facing = cochlea_points
        summit = facing[np.argmax(facing @ L)]

        def on_surface(p):
            # Nearest promontory point, then 0.35 mm out along the surface's outward normal.
            q = cochlea_points[cochlea.query(p + 3.0 * L)[1]]
            local = cochlea_points[cochlea.query_ball_point(q, 1.5)]
            normal = q - local.mean(axis=0)
            normal = _unit(normal) if np.linalg.norm(normal) > 1e-6 else L
            return q + 0.35 * normal

        course = [on_surface(summit - 3.0 * S + t * S) for t in np.arange(0.0, 5.51, 0.25)]
        top = course[-1]
        course += [top + t * _unit(A + 0.6 * S) for t in np.arange(0.25, 5.01, 0.25)]
        path = np.array(course)
        # Pushed off the nerve and the labyrinth wherever it comes closer than 0.35 mm.
        for _ in range(5):
            for tree in (labyrinth, nerve):
                d, j = tree.query(path)
                close = d < 0.35
                if close.any():
                    away = path[close] - tree.data[j[close]]
                    away /= np.maximum(np.linalg.norm(away, axis=1, keepdims=True), 1e-6)
                    path[close] += (0.35 - d[close])[:, None] * away
        out["tympanic_plexus"] = _tube(_densify(path, GRID_MM / 2), 0.12)
        report["tympanic_plexus"] = {"summit": [round(float(x), 2) for x in summit]}
    if "incus" in parts:
        body, short = part("incus", "body"), part("incus", "short_process")
        ligament("superior_incudal_ligament", body[np.argmax(body @ S)], S, 4.0, 0.15)
        ligament("posterior_incudal_ligament", short[np.argmin(short @ A)], -A, 3.0, 0.2)
    if "stapes" in parts:
        fp_mask, fp_origin = parts["stapes"]["footplate"]
        sp = np.asarray(spacings["stapes"], float)
        fp = _pts(fp_mask, sp, fp_origin)
        c = fp.mean(axis=0)
        _, _, vt = np.linalg.svd(fp - c, full_matrices=False)
        normal = vt[2]
        # Ring: around the rim, in the footplate's plane, 0.2 mm wide.
        rel = fp - c
        u, v = rel @ vt[0], rel @ vt[1]
        angles = np.linspace(0, 2 * np.pi, 72, endpoint=False)
        rim = []
        for a in angles:
            d = np.cos(a) * vt[0] + np.sin(a) * vt[1]
            reach = float(np.max(rel @ d))
            rim.append(c + (reach + 0.1) * d)
        rim.append(rim[0])
        out["annular_ligament"] = _tube(_densify(np.array(rim), GRID_MM / 2), 0.12)
        report["annular_ligament"] = {"footplate_extent_mm": [round(float(np.ptp(u)), 2), round(float(np.ptp(v)), 2)],
                                      "normal": [round(float(x), 3) for x in normal]}
        # Stapedius: the pyramidal eminence lies about 2 mm behind the stapes head and a
        # little below it; the tendon runs forwards from it to the back of the neck. The
        # muscle descends from the eminence in its own canal, in front of and medial to the
        # descending (mastoid) part of the facial nerve, which it follows 1 mm away.
        hn = part("stapes", "head_neck")
        start = hn[np.argmin(hn @ A)]
        pyramid = start - 2.0 * A - 0.5 * S
        out["stapedius_tendon"] = _band(start, pyramid, 0.12)
        fn = _pts(*facial_nerve)
        behind = fn[(fn - pyramid) @ A < 1.0]
        offset = _unit(0.8 * A - 0.5 * L)
        gap = 1.6  # from the nerve's centre: its radius about 0.65 mm, the muscle's 0.3 mm, space between
        course = [pyramid]
        for k in np.arange(1.0, 7.01, 0.5):
            level = behind[np.abs((behind - pyramid) @ S + k) < 0.3]
            if len(level) == 0:
                break
            course.append(level.mean(axis=0) + gap * offset)
        if len(course) < 4:  # no descending nerve found below: straight down
            course = [pyramid, pyramid - 6.0 * S]
        out["stapedius_muscle"] = _tube(_densify(np.array(course), GRID_MM / 2), 0.3)
        report["stapedius"] = {"tendon_mm": 2.06, "muscle_follows_nerve_points": len(course) - 1}
    # A schematic tube never runs through the specimen's own nerve or labyrinth: where one
    # would, those voxels are taken out and the tube hugs the structure instead.
    for name, (mask, origin) in list(out.items()):
        idx = np.argwhere(mask)
        pts = np.asarray(origin) + idx * GRID_MM
        clash = nerve.query(pts)[0] < 0.1
        if name != "annular_ligament":  # the ring sits on the vestibule by design
            clash |= labyrinth.query(pts)[0] < 0.1
        if clash.any():
            mask = mask.copy()
            mask[tuple(idx[clash].T)] = False
            out[name] = (mask, origin)
            report.setdefault("carved_voxels", {})[name] = int(clash.sum())
    return SoftTissue(out, report)

