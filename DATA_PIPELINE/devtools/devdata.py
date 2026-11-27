"""Development helpers for checking pipeline rules on real specimens without the full build.

The extracts are small .npz files made by the dev-extract workflows and kept on two branches
of this repository (OpenEar, CC BY 4.0):

    git clone -b dev-data-mastoid --depth 1 https://github.com/aliremuhammad-spec/otoatlas-3d devm
        # ZETA, ETA, ALPHA: every label at full resolution + the registered CBCT (u8)
    git clone -b dev-data --depth 1 https://github.com/aliremuhammad-spec/otoatlas-3d devdata
        # eight specimens, labels around the middle ear only, no CBCT

Use:
    import sys; sys.path.insert(0, "DATA_PIPELINE")
    from devtools import devdata as dd
    labels, ct = dd.load("ZETA", "devm")       # labels: name -> (mask, spacing, origin)
    f = dd.frame(labels)                       # an otopipe.ossicles.Frame, same axes as the build
    dd.render("out.png", [(dd.pts(labels["facial_nerve"]), "y", "VII")], f)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from otopipe.ossicles import Frame


def load(specimen: str, folder: str | Path):
    """Labels as name -> (bool mask, spacing, origin); the CBCT as (u8 volume, spacing, origin) or None."""
    z = np.load(Path(folder) / f"{specimen}.npz")
    names = sorted({k.split("__")[0] for k in z.files if not k.startswith("cbct")})
    labels = {}
    for n in names:
        shape = tuple(int(v) for v in z[f"{n}__shape"])
        mask = np.unpackbits(z[f"{n}__bits"])[: int(np.prod(shape))].reshape(shape).astype(bool)
        labels[n] = (mask, tuple(float(v) for v in z[f"{n}__spacing"]), tuple(float(v) for v in z[f"{n}__origin"]))
    ct = None
    if "cbct__u8" in z.files:
        ct = (z["cbct__u8"], tuple(float(v) for v in z["cbct__spacing"]), tuple(float(v) for v in z["cbct__origin"]))
    return labels, ct


def pts(label) -> np.ndarray:
    """Voxel centres of a label in millimetres."""
    mask, spacing, origin = label
    return np.asarray(origin) + np.argwhere(mask) * np.asarray(spacing)


def _unit(v):
    return v / np.linalg.norm(v)


def frame(labels) -> Frame:
    """A quick anatomical frame from the labels (lateral = vestibule to membrane centre, anterior towards
    the cochlea, superior completing it, side from the malleus). Close to, not identical with, the build's
    otopipe.ossicles.anatomical_frame, which uses the malleus long axis for superior."""
    st, sv = pts(labels["scala_tympani"]), pts(labels["scala_vestibuli"])
    dist, _ = cKDTree(st[::3]).query(sv, k=1)
    vest, coch = sv[dist > 1.5].mean(axis=0), st.mean(axis=0)
    tmc = pts(labels["tympanic_membrane"]).mean(axis=0)
    lateral = _unit(tmc - vest)
    anterior = coch - vest
    anterior = _unit(anterior - (anterior @ lateral) * lateral)
    malleus = pts(labels["malleus"])
    umbo = malleus[np.argmin(np.linalg.norm(malleus - tmc, axis=1))]
    superior = np.cross(lateral, anterior)
    side = "right" if (malleus.mean(axis=0) - umbo) @ superior > 0 else "left"
    if side == "left":
        superior = -superior
    return Frame(lateral=lateral, anterior=anterior, superior=superior, side=side, umbo=umbo)


def render(path, groups, f: Frame, title: str = "") -> None:
    """Point clouds in three views: from lateral (A,S), from anterior (L,S), from above (A,L).
    groups: list of (points, colour, legend label)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    axes = {"L": f.lateral, "A": f.anterior, "S": f.superior}
    fig, axs = plt.subplots(1, 3, figsize=(15, 5.5))
    for ax, (u, v, name) in zip(axs, [("A", "S", "from lateral"), ("L", "S", "from anterior"), ("A", "L", "from above")]):
        for p, c, lab in groups:
            q = p - f.umbo
            ax.scatter(q @ axes[u], q @ axes[v], s=1, c=c, label=lab, alpha=0.5)
        ax.set_aspect("equal")
        ax.set_title(name)
        ax.set_xlabel(u)
        ax.set_ylabel(v)
    axs[0].legend(markerscale=8, fontsize=7)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=70)
    plt.close(fig)


def straighten(volume, line: np.ndarray, across: np.ndarray, half_width_mm: float = 5.0, step_mm: float = 0.1):
    """A curved planar reformation: samples `volume` (array, spacing, origin) along a centreline, across it in
    the direction `across` (made perpendicular to the line at each point). Returns (len(line), n) image.
    Used on 26 November to check that the facial nerve label follows its canal through the mastoid."""
    from scipy import ndimage

    arr, spacing, origin = volume
    tangent = np.gradient(line, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    normal = across - (tangent @ across)[:, None] * tangent
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    offsets = np.arange(-half_width_mm, half_width_mm + 1e-9, step_mm)
    grid = line[:, None, :] + offsets[None, :, None] * normal[:, None, :]
    coords = ((grid.reshape(-1, 3) - np.asarray(origin)) / np.asarray(spacing)).T
    return ndimage.map_coordinates(arr.astype(np.float32), coords, order=1, cval=0).reshape(len(line), len(offsets))
