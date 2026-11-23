"""Parts of the three ossicles, computed from the specimen's own labels by stated rules.

Nothing here is drawn by hand. Each bone's label is divided along its own shape, and the
reviewer checks the result by looking at it:

Malleus: the long axis is the label's principal axis, measured from the tip of the handle.
Cross-section area along it is small along the handle, swells at the lateral process,
narrows at the neck and swells again at the head.
- head: from the narrowest cross-section between the lateral-process swelling and the
  incudomalleolar joint upwards;
- lateral process: within 0.6 mm (along the axis) of the lateral-process swelling, the
  voxels standing out laterally (more than 0.25 mm beyond the section's centre, towards the
  membrane) and within 0.6 mm of the tympanic membrane label;
- neck: between the swelling and the head, apart from the lateral process;
- handle (manubrium): below the swelling.
The anterior process is not resolved as a separate projection in these labels.

Incus: distances are measured inside the bone (along a voxel graph), from the tip of the
long process (the voxel nearest the stapes) and from the tip of the short process (the
most posterior voxel).
- long process: from its tip until the cross-section, which is steady along the process,
  doubles where it joins the body;
- lenticular process: the last 0.6 mm at the tip of the long process;
- short process: from its tip until the cross-section reaches half of the body's largest;
- body: the rest.

Stapes: the footplate is where the bone meets the vestibule label; a plane is fitted to
that contact. Sections parallel to the plane are counted from the head (the voxel nearest
the incus).
- footplate: the sections next to the vestibule that keep at least 45 % of the
  footplate's largest section and are one piece;
- crura: the longest run of sections that fall into two separate pieces; the piece on the
  anterior side (towards the cochlea) is the anterior crus;
- head and neck: from the head to the crura.

Plausibility checks stop a bone from being divided when a rule clearly failed; that bone
then ships whole.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

MALLEUS_PARTS = ("head", "neck", "lateral_process", "handle")
INCUS_PARTS = ("body", "short_process", "long_process", "lenticular_process")
STAPES_PARTS = ("head_neck", "anterior_crus", "posterior_crus", "footplate")

Label = tuple  # (mask, spacing, origin)


@dataclass(frozen=True)
class Frame:
    """Anatomical directions in the specimen frame, from the labels alone."""

    lateral: np.ndarray  # vestibule towards the tympanic membrane
    anterior: np.ndarray  # vestibule towards the cochlea, at right angles to lateral
    superior: np.ndarray  # right-handed for a right ear; sign fixed by the malleus head
    side: str  # "right" or "left", from the handedness of the three directions
    umbo: np.ndarray


@dataclass
class Parts:
    parts: dict[str, tuple[np.ndarray, tuple[float, float, float]]]  # name -> (mask, origin)
    report: dict = field(default_factory=dict)


def points(label: Label) -> np.ndarray:
    mask, spacing, origin = label
    return np.asarray(origin, float) + np.argwhere(mask) * np.asarray(spacing, float)


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        raise ValueError("degenerate direction")
    return v / n


def anatomical_frame(vestibule_centre, cochlea_centre, tm: Label, malleus: Label) -> Frame:
    """Lateral: vestibule towards the membrane's centre. Superior: the malleus's long axis
    (towards its head), at right angles to lateral; this follows the ossicular chain rather
    than the head's true vertical, which the labels cannot give, and stands within about
    20 degrees of it. Anterior: completes the frame, on the side of the cochlea."""
    tm_pts = points(tm)
    tm_centre = tm_pts.mean(axis=0)
    vest = np.asarray(vestibule_centre, float)
    lateral = _unit(tm_centre - vest)
    m = points(malleus)
    umbo = m[np.argmin(np.linalg.norm(m - tm_centre, axis=1))]
    _, _, vt = np.linalg.svd(m - m.mean(axis=0), full_matrices=False)
    axis = vt[0] if (m.mean(axis=0) - umbo) @ vt[0] > 0 else -vt[0]
    superior = _unit(axis - (axis @ lateral) * lateral)
    anterior = np.cross(superior, lateral)  # right-handed: lateral x anterior = superior in a right ear
    ahead = np.asarray(cochlea_centre, float) - vest
    # The cochlea lies anterior to the vestibule in every ear; whichever way the frame turns out
    # to point there tells the side.
    side = "right" if ahead @ anterior > 0 else "left"
    if side == "left":
        anterior = -anterior
    return Frame(lateral, anterior, superior, side, umbo)


def _split(label: Label, names: np.ndarray, order) -> dict:
    """Voxel masks per part name, each cropped to its own box."""
    mask, _, origin = label
    spacing = np.asarray(label[1], float)
    idx = np.argwhere(mask)
    out = {}
    for name in order:
        sel = idx[names == name]
        if len(sel) == 0:
            raise ValueError(f"part {name!r} is empty")
        lo, hi = sel.min(axis=0), sel.max(axis=0) + 1
        part = np.zeros(tuple(hi - lo), bool)
        part[tuple((sel - lo).T)] = True
        out[name] = (part, tuple(float(v) for v in np.asarray(origin, float) + lo * spacing))
    return out


def _smooth(a: np.ndarray) -> np.ndarray:
    return np.convolve(a, [1 / 3, 1 / 3, 1 / 3], mode="same")


# --- malleus -------------------------------------------------------------------------------


def malleus_parts(malleus: Label, tm: Label, incus: Label, frame: Frame, step: float = 0.2) -> Parts:
    x = points(malleus)
    vv = float(np.prod(malleus[1]))
    c = x.mean(axis=0)
    _, _, vt = np.linalg.svd(x - c, full_matrices=False)
    axis = vt[0] if vt[0] @ frame.superior > 0 else -vt[0]
    t = (x - x[np.argmin(x @ axis)]) @ axis
    b = np.floor(t / step).astype(int)
    nb = int(b.max()) + 1
    area = _smooth(np.bincount(b, minlength=nb) * vv / step)
    d_tm, _ = cKDTree(points(tm)).query(x)
    d_inc, _ = cKDTree(points(incus)).query(x)
    if not (d_inc < 0.3).any():
        raise ValueError("the malleus label does not meet the incus label")
    k_joint = int(b[d_inc < 0.3].min())
    if k_joint < 3:
        raise ValueError("incus joint at the tip of the malleus: axis not found")
    k_lp = int(np.argmax(area[:k_joint]))
    k_neck = k_lp + int(np.argmin(area[k_lp : k_joint + 1]))
    lat = frame.lateral - (frame.lateral @ axis) * axis
    lat = _unit(lat)
    centres = np.zeros((nb, 3))
    for k in range(nb):
        if (b == k).any():
            centres[k] = x[b == k].mean(axis=0)
    off = (x - centres[b]) @ lat
    names = np.full(len(x), "handle", dtype=object)
    names[b >= k_lp] = "neck"
    names[b >= k_neck] = "head"
    near = np.abs(t - (k_lp + 0.5) * step) <= 0.6
    names[near & (off > 0.25) & (d_tm < 0.6)] = "lateral_process"
    length = float(t.max())
    handle_len = float(k_lp * step)
    report = {
        "length_mm": round(length, 2),
        "handle_length_mm": round(handle_len, 2),
        "lateral_process_at_mm": round((k_lp + 0.5) * step, 2),
        "neck_at_mm": round((k_neck + 0.5) * step, 2),
        "rule": "otopipe/ossicles.py, malleus",
    }
    if not 6.0 <= length <= 10.5:
        raise ValueError(f"malleus length {length:.2f} mm is implausible")
    if not k_lp < k_neck < k_joint + 1:
        raise ValueError("lateral process, neck and head are not in order")
    if not 2.0 <= handle_len <= 6.0:
        raise ValueError(f"handle length {handle_len:.2f} mm is implausible")
    return Parts(_split(malleus, names, MALLEUS_PARTS), report)


# --- incus ---------------------------------------------------------------------------------

_OFFSETS = [o for o in np.ndindex(3, 3, 3) if o > (1, 1, 1)]


def _voxel_graph(mask: np.ndarray, spacing) -> tuple[np.ndarray, object]:
    sp = np.asarray(spacing, float)
    idx = -np.ones(mask.shape, int)
    p = np.argwhere(mask)
    idx[tuple(p.T)] = np.arange(len(p))
    rows, cols, w = [], [], []
    for o in _OFFSETS:
        off = np.asarray(o) - 1
        q = p + off
        ok = (q >= 0).all(axis=1) & (q < mask.shape).all(axis=1)
        a = np.flatnonzero(ok)
        j = idx[tuple(q[ok].T)]
        good = j >= 0
        rows.append(a[good])
        cols.append(j[good])
        w.append(np.full(int(good.sum()), float(np.linalg.norm(off * sp))))
    r, c, ww = np.concatenate(rows), np.concatenate(cols), np.concatenate(w)
    g = coo_matrix((np.r_[ww, ww], (np.r_[r, c], np.r_[c, r])), shape=(len(p), len(p))).tocsr()
    return p, g


def _fill_unreached(g: np.ndarray, x: np.ndarray, reached: np.ndarray) -> np.ndarray:
    """Voxels not joined to the bone's main piece take the distance of the nearest joined one."""
    if reached.all():
        return g
    _, j = cKDTree(x[reached]).query(x[~reached])
    g = g.copy()
    g[~reached] = g[reached][j]
    return g


def incus_parts(incus: Label, stapes: Label, frame: Frame, step: float = 0.2) -> Parts:
    mask, spacing, origin = incus
    vv = float(np.prod(spacing))
    p, graph = _voxel_graph(mask, spacing)
    x = np.asarray(origin, float) + p * np.asarray(spacing, float)
    d_st, _ = cKDTree(points(stapes)).query(x)
    long_tip = int(np.argmin(d_st))
    if d_st[long_tip] > 0.5:
        raise ValueError("the incus label does not reach the stapes label")
    g_long = dijkstra(graph, indices=long_tip)
    reached = np.isfinite(g_long)
    g_long = _fill_unreached(g_long, x, reached)
    short_tip = int(np.argmin(np.where(reached, (x - frame.umbo) @ frame.anterior, np.inf)))
    g_short = _fill_unreached(dijkstra(graph, indices=short_tip), x, reached)

    def shells(g):
        return _smooth(np.bincount(np.floor(g / step).astype(int)) * vv / step)

    a_long = shells(g_long)
    plateau = float(np.median(a_long[int(0.6 / step) : int(2.2 / step)]))
    n0 = int(1.6 / step)
    over = np.flatnonzero(a_long[n0:] > 2.0 * plateau)
    if len(over) == 0:
        raise ValueError("long process never widens into the body")
    k_long = n0 + int(over[0])
    a_short = shells(g_short)
    k_short = int(np.flatnonzero(a_short > 0.5 * a_short.max())[0])
    names = np.full(len(x), "body", dtype=object)
    names[g_long < k_long * step] = "long_process"
    names[g_long < 0.6] = "lenticular_process"
    names[g_short < k_short * step] = "short_process"
    report = {
        "long_process_length_mm": round(k_long * step, 2),
        "short_process_length_mm": round(k_short * step, 2),
        "tip_to_tip_inside_bone_mm": round(float(g_long[short_tip]), 2),
        "rule": "otopipe/ossicles.py, incus",
    }
    if not 1.6 <= k_long * step <= 5.5:
        raise ValueError(f"long process length {k_long * step:.2f} mm is implausible")
    if not 1.5 <= k_short * step <= 5.0:
        raise ValueError(f"short process length {k_short * step:.2f} mm is implausible")
    return Parts(_split(incus, names, INCUS_PARTS), report)


# --- stapes --------------------------------------------------------------------------------


def stapes_parts(stapes: Label, incus: Label, vestibule: Label, frame: Frame) -> Parts:
    _, spacing, _ = stapes
    x = points(stapes)
    d_inc, _ = cKDTree(points(incus)).query(x)
    head = x[np.argmin(d_inc)]
    d_v, _ = cKDTree(points(vestibule)).query(x)
    seed = x[d_v < 0.3]
    if len(seed) < 20:
        raise ValueError("the stapes label does not meet the vestibule")
    c0 = seed.mean(axis=0)
    _, _, vt = np.linalg.svd(seed - c0, full_matrices=False)
    u = vt[2] if (c0 - head) @ vt[2] > 0 else -vt[2]  # head towards footplate
    t = (x - head) @ u
    t = t - t.min()
    e1 = _unit(frame.anterior - (frame.anterior @ u) * u)
    e2 = np.cross(u, e1)
    step = max(0.1, float(np.max(spacing)))
    cell = float(np.max(spacing))
    nb = int(t.max() / step) + 1
    b = np.minimum((t / step).astype(int), nb - 1)
    two = np.zeros(nb, bool)
    piece = np.zeros(len(x), int)  # 1 anterior, 2 posterior
    for k in range(nb):
        sel = np.flatnonzero(b == k)
        if len(sel) < 4:
            continue
        q = np.c_[(x[sel] - head) @ e1, (x[sel] - head) @ e2]
        ij = np.floor((q - q.min(axis=0)) / cell).astype(int)
        grid = np.zeros(tuple(ij.max(axis=0) + 1), bool)
        grid[ij[:, 0], ij[:, 1]] = True
        lab, n = ndimage.label(grid, structure=np.ones((3, 3)))
        if n < 2:
            continue
        l = lab[ij[:, 0], ij[:, 1]]
        sizes = np.bincount(l)
        big = np.argsort(sizes[1:])[::-1][:2] + 1
        if sizes[big[1]] < 0.2 * len(sel):
            continue
        two[k] = True
        first_is_anterior = q[l == big[0], 0].mean() > q[l == big[1], 0].mean()
        ant, post = (big[0], big[1]) if first_is_anterior else (big[1], big[0])
        piece[sel[l == ant]] = 1
        piece[sel[l == post]] = 2
    # Footplate: the whole sections at the vestibular end.
    counts = np.bincount(b, minlength=nb)
    tail = max(2, int(np.ceil(0.8 / step)))
    peak = counts[nb - tail :].max()
    k_fp = nb - 1
    while k_fp - 1 >= 0 and counts[k_fp - 1] >= 0.45 * peak and not two[k_fp - 1]:
        k_fp -= 1
    two[k_fp:] = False
    bridged = two.copy()
    for k in range(1, nb - 1):
        if not two[k] and two[k - 1] and two[k + 1]:
            bridged[k] = True
    runs, k = [], 0
    while k < nb:
        if bridged[k]:
            j = k
            while j + 1 < nb and bridged[j + 1]:
                j += 1
            runs.append((k, j))
            k = j + 1
        else:
            k += 1
    if not runs:
        raise ValueError("no section falls into two pieces: the crura are not resolved")
    k0, k1 = max(runs, key=lambda r: r[1] - r[0])
    names = np.full(len(x), "head_neck", dtype=object)
    names[b > k1] = "footplate"
    zone = (b >= k0) & (b <= k1)
    known = zone & (piece > 0)
    loose = np.flatnonzero(zone & (piece == 0))
    if len(loose):
        _, j = cKDTree(x[known]).query(x[loose])
        piece[loose] = piece[known][j]
    names[zone & (piece == 1)] = "anterior_crus"
    names[zone & (piece == 2)] = "posterior_crus"
    fp = x[names == "footplate"]
    if len(fp) < 10:
        raise ValueError("footplate too small to measure")
    _, _, fvt = np.linalg.svd(fp - fp.mean(axis=0), full_matrices=False)
    ext = [float(np.ptp((fp - fp.mean(axis=0)) @ fvt[i])) for i in range(3)]
    report = {
        "height_mm": round(float(t.max()), 2),
        "crura_from_head_mm": [round(k0 * step, 2), round((k1 + 1) * step, 2)],
        "footplate_length_mm": round(ext[0], 2),
        "footplate_width_mm": round(ext[1], 2),
        "footplate_thickness_mm": round(ext[2], 2),
        "rule": "otopipe/ossicles.py, stapes",
    }
    if not (2.2 <= ext[0] <= 3.8 and 0.8 <= ext[1] <= 2.0 and ext[2] <= 0.8):
        raise ValueError(f"footplate {ext[0]:.2f} x {ext[1]:.2f} x {ext[2]:.2f} mm is implausible")
    return Parts(_split(stapes, names, STAPES_PARTS), report)
