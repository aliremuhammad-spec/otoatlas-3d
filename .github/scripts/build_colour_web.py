"""Development only (Phase 2B WP0): browser-ready volumes for the ray-march test page.

    python build_colour_web.py products_dir mastoid_dir out_dir [tags]

products_dir: the `dev-data-colour-products` branch (RGBA at 0.1, 0.15 and 0.2 mm, own frame, which
is the specimen frame to within 0.1 mm); mastoid_dir: the `dev-data-mastoid` branch (ZETA.npz with the
registered CBCT). Writes, gzipped and cropped to the tissue block:
  zeta_<tag>_colour[.partN].rgba.gz   RGBA8, x fastest then y then z (colour; alpha 0 for epoxy); parts join by concatenation
  zeta_normal.rgba.gz         RGBA8 on the 0.2 mm grid: CBCT-gradient normal * 0.5 + 0.5, edge strength
  zeta_meta.json              dims, spacing, origin (mm) of each volume and the global shift
Derived from OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0.
"""
from __future__ import annotations

import glob
import gzip
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

# Colour = label + SHIFT, measured on the native ear crop (alignment_native_shifted.json in the report).
SHIFT = np.array([-0.075, -0.05, 0.125])


def load(products: Path, tag: str):
    parts = [np.load(p) for p in sorted(glob.glob(str(products / f"ZETA_rgba_{tag}_part*.npz")))]
    return np.concatenate([p["rgba"] for p in parts], axis=1), np.asarray(parts[0]["spacing"]), np.asarray(parts[0]["origin"])


def write_gz(out: Path, stem: str, arr: np.ndarray, chunk_mb: int = 120) -> list[dict]:
    """Write `arr` [4, x, y, z] as texture bytes (x fastest, z slowest), gzipped in pieces of whole z planes
    so that no file nears GitHub's 100 MB limit; the page joins the pieces by plain concatenation."""
    raw = np.ascontiguousarray(arr.transpose(3, 2, 1, 0))
    plane = raw[0].nbytes
    per = max(1, (chunk_mb * 2**20) // plane)
    files = []
    for i, z0 in enumerate(range(0, raw.shape[0], per)):
        piece = raw[z0 : z0 + per]
        name = f"{stem}.rgba.gz" if raw.shape[0] <= per else f"{stem}.part{i}.rgba.gz"
        with gzip.GzipFile(out / name, "wb", compresslevel=6, mtime=0) as f:
            f.write(piece.tobytes())
        files.append({"name": name, "bytes": int(piece.nbytes)})
        print(name, piece.shape, f"{(out / name).stat().st_size / 2**20:.1f} MB gz", flush=True)
    return files


def main(products: Path, mastoid: Path, out: Path, tags: list[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rgba, sp, org = load(products, "0p20")
    a = ndimage.binary_opening(rgba[3] > 127, iterations=2)
    lab, n = ndimage.label(a)
    keep = lab == 1 + int(np.argmax(ndimage.sum(a, lab, range(1, n + 1))))
    idx = np.argwhere(keep)
    lo_mm, hi_mm = org + idx.min(0) * sp - 1.0, org + idx.max(0) * sp + 1.0
    print("tissue box mm", np.round(lo_mm, 2), np.round(hi_mm, 2))
    meta = {"volumes": {}}

    def crop(tag):
        r, s, o = load(products, tag)
        lo = np.maximum(np.floor((lo_mm - o) / s).astype(int), 0)
        hi = np.minimum(np.ceil((hi_mm - o) / s).astype(int) + 1, r.shape[1:])
        return r[(slice(None),) + tuple(slice(l, h) for l, h in zip(lo, hi))], s, o + lo * s

    sub, s, o = crop("0p20")
    z = np.load(mastoid / "ZETA.npz")
    cb, corg = z["cbct__u8"].astype(np.float32), z["cbct__origin"]
    dims = sub.shape[1:]
    grid = [((o[i] + np.arange(dims[i]) * s[i] - SHIFT[i]) - corg[i]) / 0.125 for i in range(3)]
    c = ndimage.map_coordinates(cb, np.stack(np.meshgrid(*grid, indexing="ij")).reshape(3, -1), order=1, mode="nearest").reshape(dims)
    c = ndimage.gaussian_filter(c, 1.0)
    g = np.stack(np.gradient(c, *s))
    mag = np.linalg.norm(g, axis=0)
    # Normals vary slowly, so they live on a grid twice as coarse (0.4 mm): an eighth of the voxels.
    unit = -g / np.maximum(mag, 1e-6)
    h = [d // 2 * 2 for d in dims]
    def block(a):
        return a[..., : h[0], : h[1], : h[2]].reshape(a.shape[:-3] + (h[0] // 2, 2, h[1] // 2, 2, h[2] // 2, 2)).mean(axis=(-5, -3, -1))
    unit2, mag2 = block(unit), block(mag)
    nrm = np.concatenate(
        [np.clip(np.rint((unit2 * 0.5 + 0.5) * 255), 0, 255),
         np.clip(np.rint(mag2 / np.percentile(mag2, 99.5) * 255), 0, 255)[None]], 0).astype(np.uint8)
    files = write_gz(out, "zeta_normal", nrm)
    meta["normal"] = {"files": files, "dims": [d // 2 for d in h], "spacing_mm": (s * 2).tolist(), "origin_mm": (o + s / 2).tolist()}
    for tag in tags:
        sub, s, o = crop(tag)
        files = write_gz(out, f"zeta_{tag}_colour", sub)
        meta["volumes"][tag] = {"files": files, "dims": list(map(int, sub.shape[1:])), "spacing_mm": s.tolist(), "origin_mm": o.tolist(),
                                "opaque_pct": round(float((sub[3] > 127).mean() * 100), 1)}
    meta.update({
        "build": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y%m%d%H%M%S"),
        "specimen": "OPENEAR ZETA", "shift_mm_colour_minus_label": SHIFT.tolist(),
        "source": "OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0",
        "credit": "Designed under the supervision of Dr. Ali R. Muhammad",
        "layout": "RGBA8, x fastest, then y, then z",
    })
    (out / "zeta_meta.json").write_text(json.dumps(meta, indent=1))
    (out / "README.md").write_text(
        "Browser-ready volumes for the OtoAtlas 3D ray-march test (development only), from OpenEar (Sieber et al., "
        "Scientific Data 2019, doi:10.1038/sdata.2018.297; data doi:10.5281/zenodo.1473724), CC BY 4.0.\n"
        "Designed under the supervision of Dr. Ali R. Muhammad.\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), (sys.argv[4] if len(sys.argv) > 4 else "0p20,0p15,0p10").split(","))
