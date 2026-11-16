# Architecture

State at Phase 1. The full rationale is in the Phase 0 plan; this file records what the code does.

## Layout

| Path | Role |
| --- | --- |
| `app/src/i18n` | Message catalogs (`en.ts`, `ar.ts`), language detection, numerals, React provider. No component hard-codes text. |
| `app/src/measure` | Measurement maths. Pure functions, no rendering. Tested against analytic phantoms. |
| `app/src/viewer` | `ViewerCore`: framework-free Three.js viewer with an imperative API. Scene units are millimetres. |
| `app/src/screens`, `components` | React interface shell. Talks to the viewer only through `ViewerCore`. |
| `app/e2e` | Browser smoke tests against the production build. |
| `DATA_PIPELINE/otopipe` | Offline processing: label volume to measured meshes. |
| `DATA_PIPELINE/probe` | Scripts that describe the Zenodo datasets without storing them. |
| `ontology` | Canonical structure list and dataset label mapping. |

## Decisions in force

- **One web build, three wrappers.** Vite builds with a relative base so the same output runs as a
  PWA, inside Capacitor (Android, iPad) and inside Tauri (Windows). Wrappers arrive in Phase 6.
- **Renderer.** Phase 1 uses Three.js `WebGLRenderer` (WebGL2), the baseline every target supports.
  WebGPU is an optional accelerator to be evaluated on real devices; no feature may depend on it.
- **Arabic.** Layout uses CSS logical properties and `dir` on the root element. The Arabic font is
  bundled for offline use. Labels inside the 3D view will be browser-rendered text anchored to 3D
  points, so shaping and bidirectional text come from the browser.
- **Measurement precision.** Point measurements use double precision throughout. Surface queries
  run on 32-bit vertex buffers (about 4e-6 mm resolution at 50 mm) with double-precision
  arithmetic. Measurements are taken on full-resolution geometry only.
- **Mesh error.** Every mesh is measured against its label surface (marching cubes of the binary
  label). LOD0 is Taubin-smoothed and clamped so no vertex lies further from the label surface than
  the limit: 0.05 mm inner ear, 0.10 mm middle ear. Coarser LODs are measured and flagged when they
  exceed the limit.
- **Provenance.** Scene content declares whether it is synthetic. Synthetic content always shows a badge.

## Measured so far (synthetic phantoms)

| Phantom | Voxel | LOD0 Hausdorff to label surface | Coarsest LOD | Volume kept |
| --- | --- | --- | --- | --- |
| Sphere, radius 4 mm | 0.125 mm (OpenEar segmentation voxel) | 0.048 mm | 0.062 mm, flagged over limit | 100.0 % |
| Ring, radii 3.2 and 0.4 mm | 0.06 mm (Bern micro-CT voxel) | 0.025 mm | 0.037 mm, within limit | 100.2 % |

At OpenEar's voxel size the 0.05 mm limit is met at full resolution only because of the clamp, and
decimated levels exceed it. Inner-ear measurements on OpenEar-derived meshes must therefore use LOD0.
