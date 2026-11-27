"""Phase 2B WP1: build the true-colour products of one OpenEar specimen.

    python build_colour.py SPECIMEN out_dir

Reads the micro-slicing volume, levels it, makes the 0.2, 0.15 and 0.1 mm RGBA tiers cropped to the
specimen, measures the colour-to-label shift and orientation (against the labels, and against the
CBCT where the specimen has one), and writes into out_dir:
  <SPEC>_colour_<tier>.bricks / .json   bricked RGBA8 (see otopipe.colour.bricks_encode)
  <SPEC>_normal.bricks / .json          CBCT (or alpha-surface) normals on a 0.4 mm grid
  <SPEC>_colour_meta.json               everything measured, sizes, the shift applied
  <SPEC>_montage.png                    slices for the reviewer, with the bone label outline
  README.md                             source and credit

Colour positions in the files are in the label frame: the measured shift is already taken out of `origin_mm`.
Derived from OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0.
"""
from __future__ import annotations

import datetime
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "DATA_PIPELINE"))
import build_content  # noqa: E402
from otopipe import colour, fetch, openear, scan  # noqa: E402

LABELS = ("Bone", "Sinus Dura", "External Auditory Canal", "Facial Nerve", "Scala Tympani", "Scala Vestibuli",
          "Tympanic Membrane", "Malleus", "Incus", "Stapes", "Carotis Interna")
CREDIT = "Designed under the supervision of Dr. Ali R. Muhammad"
SOURCE = "OpenEar (Sieber et al. 2019, doi:10.5281/zenodo.1473724), CC BY 4.0"
MARGIN_MM = 1.0


def read_colour(specimen: str):
    """uint8 [3, x, y, z] with every axis running in the positive RAS direction, its step and first-voxel centre."""
    import nrrd

    with tempfile.TemporaryDirectory() as tmp:
        path = fetch.fetch_openear_member(specimen, r"re:04_Reconstruction_Microslicing/[^/]*\.nrrd$", tmp)
        data, header = nrrd.read(str(path), index_order="F")
    d = np.asarray(header["space directions"], dtype=float)[-3:]
    if np.abs(d - np.diag(np.diag(d))).max() > 1e-6:
        raise ValueError(f"{specimen}: the micro-slicing volume is oblique, not handled (the specimen stays on meshes)")
    signs = openear._to_ras_signs(str(header["space"]))
    step = np.diag(d) * signs
    first = np.asarray(header["space origin"], dtype=float) * signs
    for ax in range(3):
        if step[ax] < 0:
            data = np.flip(data, axis=ax + 1)
            first[ax] += (data.shape[ax + 1] - 1) * step[ax]
            step[ax] = -step[ax]
    return np.ascontiguousarray(data), step, first, str(header["space"])


def label_sampler(segments: dict):
    """reference_at(points) -> (label id, ok): id 0 outside every structure, later structures overwrite earlier."""
    order = [(i + 1, n) for i, n in enumerate(LABELS) if n in segments]

    def at(points):
        out = np.zeros(len(points), np.float32)
        for i, n in order:
            seg = segments[n]
            q = np.rint((points - np.asarray(seg.origin)) / np.asarray(seg.spacing)).astype(int)
            ok = np.all((q >= 0) & (q < np.array(seg.mask.shape)), 1)
            hit = np.zeros(len(points), bool)
            hit[ok] = seg.mask[tuple(q[ok].T)]
            out[hit] = i
        return out, np.ones(len(points), bool)

    return at, len(LABELS) + 1


def cbct_sampler(u8: np.ndarray, spacing, origin):
    smooth = ndimage.gaussian_filter(u8.astype(np.float32), 0.8)
    sp, org = np.asarray(spacing), np.asarray(origin)

    def at(points):
        q = (points - org) / sp
        ok = np.all((q >= 0) & (q <= np.array(smooth.shape) - 1), 1)
        return ndimage.map_coordinates(smooth, q.clip(0, np.array(smooth.shape) - 1).T, order=1), ok

    return at


def montage(path: Path, specimen: str, rgba, org, step, bone, ref, ref_after, meta_line: str, colour_only_alpha=None) -> None:
    from PIL import Image, ImageDraw

    bg = np.array([58, 58, 62], np.float32)
    a = rgba[3:4].astype(np.float32) / 255
    rgb = (rgba[:3].astype(np.float32) * a + bg[:, None, None, None] * (1 - a)).astype(np.uint8)
    nx, ny, nz = rgb.shape[1:]
    contour = None
    if bone is not None:
        m = colour.sample_mask(bone.mask, bone.origin, bone.spacing, (nx, ny, nz), org, step)
        contour = m & ~ndimage.binary_erosion(m)

    def panel(img, edge=None, height=300):
        im = img.copy()
        if edge is not None:
            im[edge] = [0, 255, 255]
        pil = Image.fromarray(im)
        return pil.resize((max(1, round(pil.width * height / pil.height)), height), Image.NEAREST)

    def axial(k, with_edge):
        return panel(rgb[:, :, :, k].transpose(2, 1, 0), (contour[:, :, k].T if with_edge and contour is not None else None))

    def coronal(j):
        return panel(rgb[:, :, j, :].transpose(2, 1, 0)[::-1], (contour[:, j, :].T[::-1] if contour is not None else None))

    def sagittal(i):
        return panel(rgb[:, i, :, :].transpose(2, 1, 0)[::-1], (contour[i, :, :].T[::-1] if contour is not None else None))

    ks = np.linspace(0.12, 0.88, 5) * nz
    rows = [[axial(int(k), False) for k in ks]]
    if colour_only_alpha is not None:
        a0 = colour_only_alpha[None].astype(np.float32) / 255
        rgb0 = (rgba[:3].astype(np.float32) * a0 + bg[:, None, None, None] * (1 - a0)).astype(np.uint8)
        rows.append([panel(rgb0[:, :, :, int(k)].transpose(2, 1, 0)) for k in ks])
    rows += [
        [axial(int(k), True) for k in ks],
        [coronal(int(ny * f)) for f in (0.3, 0.5, 0.7)] + [sagittal(int(nx * f)) for f in (0.35, 0.65)],
    ]
    w = max(sum(p.width for p in r) + 6 * (len(r) - 1) for r in rows)
    plot_h = 170
    canvas = Image.new("RGB", (w + 12, 40 + sum(max(p.height for p in r) for r in rows) + 6 * 3 + plot_h + 30), (20, 20, 22))
    dr = ImageDraw.Draw(canvas)
    dr.text((8, 6), f"{specimen}  colour tier {step:.2f} mm   {meta_line}", fill=(235, 235, 235))
    dr.text((8, 22), "rows: axial | axial with colour-only alpha (before CBCT) | axial with bone label outline (cyan) | coronal x3, sagittal x2.   " + CREDIT, fill=(170, 170, 175))
    y = 40
    for r in rows:
        x = 6
        for p in r:
            canvas.paste(p, (x, y))
            x += p.width + 6
        y += max(p.height for p in r) + 6
    # epoxy colour per slice, before and after levelling (R, G, B)
    top, left, width = y + 12, 40, w - 60
    dr.rectangle([left, top, left + width, top + plot_h - 20], outline=(90, 90, 95))
    dr.text((8, top - 12), "epoxy colour by slice: thin = before levelling, thick = after (R, G, B)", fill=(170, 170, 175))
    vals = ref[~np.isnan(ref)] if np.isfinite(ref).any() else np.array([150.0, 240.0])
    lo, hi = float(np.floor(vals.min() / 10) * 10 - 10), float(np.ceil(vals.max() / 10) * 10 + 10)
    for c, col in enumerate(((235, 90, 90), (90, 220, 110), (100, 150, 245))):
        for series, wd in ((ref, 1), (ref_after, 3)):
            pts = [(left + width * k / max(len(series) - 1, 1), top + (plot_h - 20) * (1 - (series[k, c] - lo) / (hi - lo)))
                   for k in range(len(series)) if np.isfinite(series[k, c])]
            if len(pts) > 1:
                dr.line(pts, fill=col, width=wd)
    dr.text((4, top), f"{hi:.0f}", fill=(170, 170, 175))
    dr.text((4, top + plot_h - 32), f"{lo:.0f}", fill=(170, 170, 175))
    canvas.save(path, optimize=True)


def main(specimen: str, out: Path) -> None:
    specimen = specimen.upper()
    out.mkdir(parents=True, exist_ok=True)
    meta: dict = {"specimen": f"OPENEAR {specimen}", "source": SOURCE, "credit": CREDIT, "warnings": []}
    vol, step, first, space = read_colour(specimen)
    meta.update(source_space=space, native_step_mm=step.tolist(), native_shape=list(vol.shape), native_origin_mm=first.tolist())
    print(f"{specimen}: colour {vol.shape}, step {step}, first {first}", flush=True)

    # Resin cylinder, epoxy colour per slice, levelling gains (from the 0.2 mm view; gains are per source slice).
    f02 = int(round(0.2 / step[0]))
    coarse = colour.reduce_xy(vol, f02)
    org_c = colour.tier_origin(first, step, f02)
    cyl = colour.fit_cylinder(coarse, 0.2, org_c[:2])
    ref = colour.epoxy_reference(coarse, 0.2, org_c[:2], cyl)
    gains, diag = colour.level_gains(ref)
    meta["cylinder_mm"] = {"cx": round(cyl.cx, 2), "cy": round(cyl.cy, 2), "radius": round(cyl.radius, 2)}
    meta["levelling"] = diag
    ref_after = ref * gains
    del coarse
    print("cylinder", meta["cylinder_mm"], "levelling", diag, flush=True)

    # Stage A: the whole 0.2 mm tier, colour alpha only. Alignment is measured on it.
    full02, org02 = colour.build_tier(vol, step, first, 0.2, gains, cyl)
    colour_alpha02 = full02[3].copy()
    segments, cbct_u8, cbct_sp, cbct_org = {}, None, None, None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            seg_path = fetch.fetch_openear_member(specimen, "06_Segmentation/Segmentation.seg.nrrd", tmp)
            found = openear.read_segmentation(str(seg_path), LABELS)
        segments, _, _ = openear.match_segments(found, LABELS)
        del found
    except Exception as e:  # noqa: BLE001 - reported; the colour products are still made, unshifted
        meta["warnings"].append(f"labels unavailable: {e!r}")
    cb = build_content.load_openear_cbct(specimen)
    ext_lo, ext_hi = org02 - 2.5, org02 + np.array(full02.shape[1:]) * 0.2 + 2.5
    if cb is not None:
        v, name = cb
        sub = scan.crop(v, ext_lo, ext_hi)
        cbct_u8, _, _ = scan.window(sub.data)
        cbct_sp, cbct_org = sub.spacing, sub.origin
        meta["cbct"] = {"file": name, "crop_shape": list(cbct_u8.shape), "spacing_mm": list(cbct_sp)}
        del v, sub
    shift = np.zeros(3)
    meta["alignment"] = {"applied_shift_mm_colour_minus_label": [0.0, 0.0, 0.0], "source": "none"}
    rng = np.random.default_rng(1)
    idx = np.argwhere(ndimage.binary_dilation(full02[3] > 127, iterations=3))
    idx = idx[rng.choice(len(idx), min(200_000, len(idx)), replace=False)]
    pos = org02 + idx * 0.2
    lum = (0.299 * full02[0] + 0.587 * full02[1] + 0.114 * full02[2])[tuple(idx.T)]
    alp = full02[3][tuple(idx.T)].astype(np.float32)
    if segments:
        ref_at, nbins = label_sampler(segments)
        est_l = colour.estimate_shift(pos, lum, ref_at, nbins, (0, nbins))
        est_a = colour.estimate_shift(pos, alp, ref_at, nbins, (0, nbins))
        orient = colour.orientation_check(pos, lum, ref_at, nbins, (0, nbins))
        shift = np.round(np.mean([est_l["shift_mm"], est_a["shift_mm"]], 0) / 0.025) * 0.025
        meta["alignment"] = {
            "applied_shift_mm_colour_minus_label": [round(float(v), 3) for v in shift],
            "source": "labels (mean of luminance and alpha, mutual information, 0.05 mm search grid)",
            "by_luminance": {k: v for k, v in est_l.items() if k not in ("curves", "candidates")},
            "by_alpha": {k: v for k, v in est_a.items() if k not in ("curves", "candidates")},
            "orientation_vs_labels": orient,
        }
        if not orient["identity_wins"]:
            meta["warnings"].append("ORIENTATION: the colour volume does not clearly match the labels as is; check for a flip")
        if est_l["at_search_edge"] or est_a["at_search_edge"]:
            meta["warnings"].append("the shift search reached its edge; the shift is not trustworthy")
    if cbct_u8 is not None:
        cref = cbct_sampler(cbct_u8, cbct_sp, cbct_org)
        est_c = colour.estimate_shift(pos, lum, cref, 32, (0, 256))
        meta["alignment"]["vs_cbct"] = {
            **{k: v for k, v in est_c.items() if k not in ("curves", "candidates")},
            "orientation": colour.orientation_check(pos, lum, cref, 32, (0, 256)),
        }
    print("alignment", json.dumps(meta["alignment"])[:900], flush=True)

    # Stage B: CBCT density makes cortex opaque where its colour is as pale as epoxy.
    cbct_smooth = ndimage.gaussian_filter(cbct_u8.astype(np.float32), 0.8) if cbct_u8 is not None else None
    cap02 = colour.cap_weight(full02.shape[1:3], 0.2, org02[:2], cyl)
    bone_ramp = None
    if cbct_smooth is not None:
        c02 = colour.sample_on_grid(cbct_smooth, cbct_sp, cbct_org, org02 - shift, 0.2, full02.shape[1:])
        levels = colour.cbct_alpha_levels(c02, colour_alpha02, cap02 > 0.99)
        meta["cbct_alpha"] = levels
        print("cbct alpha", levels, flush=True)
        if levels["usable"]:
            bone_ramp = levels["ramp"]
            gained = colour.apply_bone_alpha(full02, c02, bone_ramp, cap02)
            meta["cbct_alpha"]["new_opaque_pct_of_block"] = round(gained * 100, 2)
        else:
            meta["warnings"].append("CBCT density could not be split into epoxy and bone; alpha from colour only")
        del c02
    else:
        meta["warnings"].append("no CBCT: alpha from colour only, pale cortex may be missing")

    # Tiers: the crop box and the tissue mask come from the final 0.2 mm alpha, so every tier covers the same block.
    keep_full = colour.main_tissue(full02[3])
    box = colour.box_of(keep_full, org02, 0.2, MARGIN_MM)
    keep, keep_org = ndimage.binary_dilation(keep_full, iterations=2), org02
    del keep_full
    rgba_t: dict = {}
    for target in colour.TIERS_MM:
        if target == 0.2:
            rgba, org = full02, org02
        else:
            rgba, org = colour.build_tier(vol, step, first, target, gains, cyl)
            if bone_ramp is not None:
                ct = colour.sample_on_grid(cbct_smooth, cbct_sp, cbct_org, org - shift, target, rgba.shape[1:])
                colour.apply_bone_alpha(rgba, ct, bone_ramp, colour.cap_weight(rgba.shape[1:3], target, org[:2], cyl))
                del ct
        rgba, org_t = colour.crop_mm(rgba, org, target, *box)
        region = colour.sample_mask(keep, keep_org, 0.2, rgba.shape[1:], org_t, target)
        rgba = np.ascontiguousarray(rgba)
        rgba[3] = np.where(region, rgba[3], 0)
        rgba[:3] = np.where(region[None], rgba[:3], 0)
        rgba_t[target] = (rgba, org_t)
        print(f"tier {target}: {rgba.shape[1:]} voxels, {100 * (rgba[3] > 127).mean():.1f}% opaque", flush=True)
        del region
    full02 = None
    base, borg = rgba_t[0.2]
    # colour-only alpha at the 0.15 tier, for the reviewer's before/after row
    a015 = colour.alpha_of(rgba_t[0.15][0][:3].astype(np.float32))
    colour_only015 = np.rint(a015 * 255).astype(np.uint8)
    del vol

    # Files. Positions are in the label frame: colour position - shift.
    sizes = {}
    meta["tiers"] = {}
    for target, (rgba, org_t) in rgba_t.items():
        tag = f"{target:.2f}".replace(".", "p")
        blob, index = colour.bricks_encode(rgba)
        index.update(spacing_mm=[target] * 3, origin_mm=(org_t - shift).round(4).tolist(),
                     opaque_pct=round(float((rgba[3] > 127).mean() * 100), 1), source=SOURCE)
        (out / f"{specimen}_colour_{tag}.bricks").write_bytes(blob)
        (out / f"{specimen}_colour_{tag}.json").write_text(json.dumps(index, separators=(",", ":")))
        sizes[tag] = round(len(blob) / 2**20, 2)
        meta["tiers"][tag] = {k: index[k] for k in ("dims", "spacing_mm", "origin_mm", "bricks_total", "bricks_stored", "opaque_pct")}
        meta["tiers"][tag]["bricks_mb"] = sizes[tag]
        print(f"{tag}: {rgba.shape[1:]} {sizes[tag]} MB, bricks {index['bricks_stored']}/{index['bricks_total']}", flush=True)
    dims0 = base.shape[1:]
    if cbct_smooth is not None:
        scalar = colour.sample_on_grid(cbct_smooth, cbct_sp, cbct_org, borg - shift, 0.2, dims0)
        meta["normal_source"] = "cbct"
    else:
        scalar = base[3].astype(np.float32)
        meta["normal_source"] = "alpha surface (this specimen has no CBCT)"
    nrm = colour.normals_volume(scalar, 0.2)
    blob, index = colour.bricks_encode(nrm)
    index.update(spacing_mm=[0.4] * 3, origin_mm=(borg - shift + 0.1).round(4).tolist(), source=SOURCE, normal_source=meta["normal_source"])
    (out / f"{specimen}_normal.bricks").write_bytes(blob)
    (out / f"{specimen}_normal.json").write_text(json.dumps(index, separators=(",", ":")))
    sizes["normal"] = round(len(blob) / 2**20, 2)
    meta["sizes_mb"] = sizes
    meta["build"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
    meta["layout"] = "bricks: see index json; RGBA8 interleaved x fastest; normals RGB = n * 0.5 + 0.5, A = edge strength"
    (out / f"{specimen}_colour_meta.json").write_text(json.dumps(meta, indent=1))

    for target in (0.15, 0.2):
        rg, og = rgba_t[target]
        line = f"shift {np.round(shift, 3).tolist()} mm  levelling {'on' if diag.get('levelled') else 'off'}  tiers MB {sizes}"
        montage(out / f"{specimen}_montage_{target:.2f}.png", specimen, rg, og - shift, target, segments.get("Bone"),
                ref, ref_after, line, colour_only_alpha=colour_only015 if target == 0.15 else None)
    (out / "README.md").write_text(
        f"True-colour volume products of OpenEar specimen {specimen} for OtoAtlas 3D (development build), from "
        f"{SOURCE}; Sieber et al., Scientific Data 2019, doi:10.1038/sdata.2018.297.\n{CREDIT}.\n"
    )
    for p in sorted(out.iterdir()):
        print(p.name, p.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
