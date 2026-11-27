# OtoAtlas 3D: handoff for the next session

Last updated 28 November 2026, WP0 and WP1 finished (merged to `main`), WP2 part 1 (surgical view as its own entry, colour renderer) is merged and live; WP2 part 2 (labels) next in a new session. Read this file first;
it replaces re-reading the long earlier conversations. Update the "State" and "Next step"
sections at the end of every session.

## Rules that never change

- **The credit is a release blocker.** «تم تصميم التطبيق بإشراف د. علي ر. محمد» /
  "Designed under the supervision of Dr. Ali R. Muhammad" stays on the splash, home footer,
  About, topics footer, README and every published data README. Tests check it.
- **The user is the medical reviewer and translator** (Dr. Ali R. Muhammad). He writes in
  Syrian Arabic; answer him in Arabic. Keep his email private. He does not draw: geometry is
  computed from the specimens, or shown as "schematic" with a badge and never measurable.
- **Everything is draft until he approves it.** New Arabic terms get `ar_status: "unverified"`;
  computed divisions get `division_review` only when he signs them off.
- **Arabic terms follow the reviewed ontology names**, for example الناتئ الوحشي,
  الساق القصيرة/الطويلة للسندان, السقالة الطبلية/الدهليزية, النافذة المستديرة,
  القنوات نصف الهلالية, الغشاء الطبلي, صفيحة الركاب, and «وحشي» for lateral.
- **The reference chapter** (Janfaza et al., Surgical Anatomy of the Head and Neck, ch. 9,
  Temporal bone and ear) is copyrighted. Never commit it or quote it; topic texts are our own
  words with figures cited by book page. The PDF is not in the workspace; ask him to attach it
  if a page check is needed (book page = PDF page + 414 in his excerpt).
- **Never type credentials.** He created the Hugging Face token and the GitHub secret `HF_TOKEN`
  himself.
- **Educational software only**, not a medical device; measurements show method and voxel size.
- Commits end with the attribution lines the session's system reminder gives.

## Where everything is

| What | Where |
| --- | --- |
| Repository | https://github.com/aliremuhammad-spec/otoatlas-3d (branch `main`) |
| Live app (GitHub Pages) | https://aliremuhammad-spec.github.io/otoatlas-3d/ |
| Scan mirror | Hugging Face dataset `zero019/otoatlas-3d-content` |
| Plan document (Claude Docs) | https://claude.ai/artifact/RsTg6tjXm5VMnLHo8tc7E7 (project id `c966f472-e4f5-4609-8ed7-8d8b516cd358`; main tab body node `5e841e35-749d`; tab "Phase 2B plan" `6140029f-3e1c`, body node `0c0d51db-ba49`) |
| Coverage of the chapter | `docs/CONTENT_COVERAGE.md` |
| Dataset facts | `DATA_PIPELINE/DATASET_NOTES.md` |
| Data | OpenEar, Zenodo 1473724, CC BY 4.0; Human Bony Labyrinth (Bern), Zenodo 3355272, CC BY 4.0 |

## Working economically (the user asked for this)

Long sessions cost most in re-read context, not in work. Keep quality, cut the re-reading:

- **One work package per session.** When a session passes about 120 to 150 requests, update this
  file and tell the user to continue in a new session.
- Read file ranges, not whole files; find code with `git grep -n`; pipe long command output
  through `tail` or `grep`; never print big JSON, logs or manifests whole.
- Run only the tests you touched while working, then the full suites once before committing.
- Look at pictures only when a decision depends on them; use `scale` 0.5 for browser screenshots.
- Do not re-read the chapter or the plan document whole; search them.
- Don't repeat finished research; facts gathered are recorded below and in the docs.

## Repository map

- `app/`: Vite + React + TypeScript PWA, Three.js viewer (WebGL2), Vitest, Playwright, ESLint.
  - `src/viewer/`: `ViewerCore.ts` (scene, camera from the anatomical frame, picking with an
    opacity threshold, touch handling, `setColor`, context-loss recovery), `manifest.ts` (strict
    parser; `MEASUREMENT_IDS`; `plain_color`), `loadPackage.ts` (meshes; scans from the site, then
    the HF mirror, with stall timeout and retry), `labels.ts` (3D labels placed without overlap),
    `slice.ts`.
  - `src/screens/`: `SpecimenView.tsx` (structure list with groups, isolate, opacity, the
    own-colour switch stored in `localStorage` key `otoatlas.plainColours`, topic overlay, focus
    from topics), `StructureCard.tsx` (facts, division status, measurements, related topics),
    `SlicePane.tsx`, `TopicsScreen.tsx`, `TopicReader.tsx`, `Home`, `About`, `Settings`, `Splash`.
  - `src/topics/topics.ts`: loads `ontology/topics/*.json` at build time (`import.meta.glob`).
  - `src/i18n/en.ts`, `ar.ts`: every key in both; Arabic strings must contain Arabic script except
    bare symbols; no empty strings (tests enforce this).
  - `e2e/`: `smoke`, `specimen` (fixture content in `e2e/fixtures/content/TEST-SYNTHETIC-01`) and
    `mobile` (four touch devices).
- `DATA_PIPELINE/`: Python package `otopipe` and `build_content.py`.
  - `openear.py` (reads only the wanted segments; bounded inflate), `fetch.py` (Zenodo with
    retries and backoff), `mesh.py` (marching cubes, Taubin with a per-vertex clamp, measured
    error, LODs), `package.py` (manifest, `group_of`, `plain_color`), `frames.py`, `scan.py`.
  - Computed anatomy: `split.py` (scala vestibuli vs vestibule and canals), `tm.py` (membrane
    quadrants), `ossicles.py` (anatomical frame; malleus, incus, stapes parts), `cochlea.py`
    (A and B values), `pneumatization.py` (tympanic air space, air cells, antrum),
    `membranous.py` (schematic membranous labyrinth), `softtissue.py` (schematic ligaments,
    muscles, malleal folds, tympanic plexus), `facialnerve.py` (nerve divided at the second genu).
  - `devtools/devdata.py`: load small real extracts, quick frame, three-view plots, straightened
    CT along a centreline.
- `ontology/structures.json` (every structure: names en/ar/Latin, sources, colour, provenance,
  review status), `descriptions.json` (card texts), `topics/` (70 chapter topics in eight files
  plus `_sources.json`).
- `.github/specimens.json`: the eight published specimens, in picker order: OPENEAR ZETA, DELTA,
  BETA, ALPHA, ETA; BERN F01, F03, T07.
- `.github/workflows/`: `ci.yml`, `deploy.yml` (plan → content matrix, max 4 parallel, cached by
  `hashFiles(DATA_PIPELINE/**, ontology/**, !ontology/topics/**)` → site with index, HF mirror,
  Pages deploy with retry), `dev-extract*.yml` (small extracts to the `dev-data*` branches),
  `data-report.yml`.

## Build, test, deploy

```
cd app && npm ci && npm test && npx eslint src e2e && npx tsc --noEmit
npm run build && npx playwright test            # e2e against the build
cd DATA_PIPELINE && pip install -e ".[dev]" && python -m pytest -q
```

- Pushing to `main` deploys. Changes under `DATA_PIPELINE/` or `ontology/` (not
  `ontology/topics/`) rebuild all eight specimens, about 12 minutes; app-only and topic changes
  take a few minutes. Check with `gh run list --limit 3` and read job logs per specimen with
  `gh run view <run> --job <id> --log | grep ...`.
- The shell cannot reach github.io. Check the live site with Claude in Chrome; the app shows an
  update banner («حدّث الآن») that must be clicked to load the new build. Restore any setting
  you change in his browser.
- At last count: 94 pipeline tests, 100 unit tests, and the e2e suites all pass.

## Dev data for checking a rule on real specimens

```
git clone -b dev-data-mastoid --depth 1 https://github.com/aliremuhammad-spec/otoatlas-3d /tmp/devm
# ZETA, ETA, ALPHA: all labels + registered CBCT (u8)
git clone -b dev-data --depth 1 https://github.com/aliremuhammad-spec/otoatlas-3d /tmp/devdata
# eight OpenEar specimens, middle-ear labels only
```

Use `DATA_PIPELINE/devtools/devdata.py` (docstring shows how). New extracts: copy
`.github/workflows/dev-extract-mastoid.yml` and `.github/scripts/extract_mastoid_dev.py`.

## State at the end of Phase 2 (all deployed)

- Eight specimens; anatomical frame per specimen; meshes with measured error.
- Computed: membrane quadrants; ossicle parts (reviewed 24 Nov); scala vestibuli vs vestibule
  and canals (reviewed 17 Nov); tympanic air space, mastoid antrum, other air cells (volumes in
  mL); cochlear A and B values with an estimated duct length (Bern); vestibule width;
  facial nerve divided at the second genu, mastoid segment 14 to 18 mm, shown light green with a
  switch back to the nerve's yellow.
- Schematic (badged, not measurable): membranous labyrinth; ossicular ligaments and annular
  ligament; tensor tympani and stapedius; anterior and posterior malleal folds; tympanic plexus.
- 70 topic texts covering every topic of the chapter, in both languages, with figures and pages;
  Topics screen with search, reader over the 3D view, "Show in 3D".
- Mobile: stacked layout, toolbar with slices and enlarge, touch tests on four screens.
- Correction made on 26 Nov: the OpenEar facial nerve label already includes the mastoid segment
  (verified against the CBCT); the 17 Nov note was wrong and was corrected in the ontology,
  coverage and dataset notes.
- Deferred on purpose: tracts of pneumatization (no reliable rule), small middle-ear arteries,
  Arnold's nerve geometry, the auricle (not in any specimen block).

## Waiting on the reviewer

1. Approve the 70 topic texts and their Arabic (start with middle ear and facial nerve).
2. Arabic terms for: air spaces (3), membranous labyrinth (4), muscles and ligaments (12), folds
   and plexus (3), facial nerve parts (2).
3. Computed sides: DELTA, BETA, ALPHA right; ETA left.
4. Whether the mobile fix works on his phone.
5. Facial nerve division: is the middle of the bend acceptable, or the level of the pyramidal
   eminence? Is light green right for the mastoid segment?
6. Phase 2B decisions (checklist in the plan's "Phase 2B plan" tab): approaches, head and
   surgeon position, microscope working distance and magnifications, landmarks per station,
   VES 3.5 installed on a Windows PC for the comparison, raters, stereo hardware.

## Next step: Phase 2B, WP2 part 2 (label-aware renderer; start in a NEW session)

WP2 part 1 is merged (PRs #2 and the polish PR) and live. Verified live on 28 Nov in his Chrome (Windows PC, DPR 1.25): the surgical
screen opens ZETA at 0.15 mm, canvas 1440x408, no errors, the HUD reads 60 frames per second at render scale 1 (vsync cap); the
controls changed the picture. Not yet seen: a phone, an iPad, the other five specimens (the manifests are the same shape).
Trap in tests: a synthetic `PointerEvent` has no valid pointer id, so `setPointerCapture` throws (now guarded); use wheel events to
drive the view in a page script.

**Rule from the user (28 Nov): the surgical view is a separate option from the anatomical models.** Home has two sections
(`home-anatomy`: viewer and topics; `home-surgical`: its own button), `ScreenId` has `'surgical'`, the screen is
`app/src/screens/SurgicalScreen.tsx` and shares nothing with `ViewerScreen`/`SpecimenView` except package loading. No viewer
control may appear on the surgical screen and no surgical control in the viewer (tests in `App.test.tsx` and `e2e/surgical.spec.ts`
check both). Keep it that way in every later work package; topics "Show in 3D" still opens the anatomical viewer.

Done in part 1 (`app/src/surgical/`): `bricks.ts` (index parser and decoder; golden test against the Python writer,
`fixtures/bricks_golden.json`, node environment because jsdom's Blob has no `stream()`), `tier.ts` (Gate 0 rule: phone =
small touch screen = 0.2 mm at render scale 0.5, others 0.15 mm; 0.1 mm never chosen; adaptive scale: below 30 fps minus 0.1 down to
0.35, above 52 fps plus 0.05 up to the start scale), `VolumeRenderer.ts` (WebGL2 ray-marcher ported from `public/dev/raymarch.html`,
orbit around the specimen using the anatomical frame, opaque or translucent, cut into the block, context-loss recovery,
`maxTextureSize` check), `loadColour.ts` (lists specimens whose manifest has `colour`, loads bricks from the site then the pinned
Hugging Face url), `SurgicalView.tsx` (canvas, loading overlay with three steps, error and no-WebGL2 states, pointer and wheel
controls, draws only when something changed, adapts scale while moving), and the e2e fixture package
`app/e2e/fixtures/content-colour/TEST-COLOUR-01` (generated with `colour.bricks_encode`; a pink ball with a dark core).
Unit tests 100, e2e 34 (all pass).

Not done (WP2 part 2, in this order):
1. **Label volume.** Design note: the label ids must include the *computed* parts (scala vestibuli, membrane quadrants, ossicle parts,
   facial nerve segments, air spaces), and those masks exist only inside `build_content.py` while the specimen package is built, not in
   `build_colour.py`. So write one label volume per specimen in the content job (uint8 ids on the segmentation grid, 0.125 mm, cropped
   to the ear, plus the id table), upload it with the package, and let the colour job resample it nearest-neighbour onto each tier
   grid (the colour grid is shifted from the label frame by the stored `shift_mm`; origins already include it). Structure ids in the
   table must be the manifest structure ids so the surgical list can reuse the names and colours. The renderer cannot hide, show, tint or isolate a structure yet because the browser has no label volume. The renderer cannot hide, show, tint or isolate a structure yet because the browser has no label volume.
   Pipeline job: resample the segmentation labels onto each colour tier grid (nearest neighbour, uint8 id per voxel with an
   id table in the manifest), brick it like the colour (single channel, or pack into the alpha of a second texture), build in
   `build_colour.py`, publish like the normals. Mind the size budget (site is 514 MB of 1 GB).
2. Shader: per-label visibility and tint (a 256-entry lookup texture), isolate, then picking (ray cast to the first opaque
   labelled voxel; must agree with the meshes within 0.2 mm), then ambient occlusion and progressive refinement, and the fallback
   to meshes when WebGL2 or the texture size is not available (today the screen shows a message).
3. Structure list and card inside the surgical screen, built for that screen (not shared with the viewer's list).
4. Check live on real specimens (ZETA 0.15 mm first), on his PC and phone, and read the fps the HUD shows.

## WP1 result (done 27/28 Nov, one build session after the WP0 session; the user approved the specimen list, the size budget and the montages)

- Six colour specimens: ZETA, ALPHA, DELTA, ETA, EPSILON, THETA (`.github/colour-specimens.json` for dev builds; `colour: true` in
  `.github/specimens.json`, which now also lists EPSILON and THETA, so they get meshes too; BETA stays mesh-only: no CBCT, sparse
  olive colour block). GAMMA dropped (rotated grid).
- Code: `DATA_PIPELINE/otopipe/colour.py` (+ `tests/test_colour.py`, 20 tests), `.github/scripts/build_colour.py` (stage A:
  alignment on the full 0.2 tier; stage B: CBCT alpha; tiers, bricks, read-back check, normals, montages, meta),
  `.github/scripts/attach_colour.py` (+ `tests/test_attach_colour.py`; copies products to `<pkg>/colour/`, writes the manifest
  `colour` block; `finish` removes the 0.1 bricks from the site), `publish_scans_hf.py` (uploads colour bricks, pinned urls),
  `deploy.yml` (job `colour` after `content`, max 3 parallel, cache key `colour-v1-<id>-hashFiles(colour.py, fetch.py, openear.py,
  scan.py, build_content.py, build_colour.py)`; `site` needs content and colour), `colour-build.yml` (dev run, outputs to
  `dev-data-colour-wp1-<SPEC>` branches), `app/src/viewer/manifest.ts` (optional `colour` block parser, 5 tests).
- Where the files go: tiers 0.2 and 0.15 mm and normals on the site (`<pkg>/colour/`); the 0.1 mm tier only on the HF mirror
  (manifest tier has `on_site: false` and a pinned HF url). Sizes MB (0.2 / 0.15 / 0.1 / normals): ZETA 9.1/20.6/64.2/3.3, ALPHA
  11.0/25.2/80.9/4.4, DELTA 8.5/19.2/60.5/3.9, ETA 9.6/21.9/68.7/3.8, EPSILON 11.2/25.4/79.4/3.8, THETA 6.8/15.5/48.5/3.2.
- Alpha rule: saturation ramp, plus (where there is a CBCT) pale voxels split by an isodata threshold on CBCT density. Two traps
  fixed in session 2: (1) **cupping** (ETA): a radial baseline from confident-epoxy voxels (bright, saturation < 0.12, 1 mm radial
  bins, 2 sigma clipping) is subtracted first, which made ETA usable; (2) **real air** among the pale voxels dragged the threshold
  below the epoxy level, so values below median - 3 sigma are dropped before the split. The rule switches itself off when
  epoxy and bone are not separable: ZETA and EPSILON (complete anyway) say so in `warnings`. Final: ALPHA, DELTA, ETA, THETA use it
  (thresholds 23.5, 25.4, 19.8, 21.5).
- Seam check: the rectangle with a round hole seen in ZETA coronal slices is a feature of the source images (probably a marker
  or fiducial), not a pipeline seam, and there are faint horizontal streaks in the epoxy. Left unmasked on purpose; epoxy is
  transparent so they do not show in the rendered volume.
- Alignment shifts (mm, subtracted from `origin_mm`) are listed above under session 1; all below the noise floor.
- Tests at the end: 94 pipeline tests; app unit tests include the colour manifest parser; CI green.
- Verified after merge (deploy run 46072719838, all green, about 30 min with the colour jobs): colour jobs for the six specimens
  passed; the site holds `<pkg>/colour/` with tiers 0.2 and 0.15, normals and the 0.1 index but no 0.1 bricks; the HF mirror
  (commit a368d3fb) holds all four brick files per specimen (ZETA: 67.4 / 21.6 / 9.5 / 3.5 MB); the Pages artifact is 514 MB
  (limit 1 GB, watch it when adding specimens); the live manifests carry the `colour` block with pinned HF urls; the live app
  (after the update banner) lists EPSILON and THETA and opens ETA and EPSILON with no errors. The app does not use the colour
  data yet (that is WP2).
- Trap: `deploy.yml` has `cancel-in-progress: true`, so a push to main while a deploy runs cancels it; wait for the deploy first.

## WP0 (feasibility on ZETA), finished 28 Nov, kept for reference

Goal: prove or reject true-colour volume rendering before anything else is built (Gate 0:
colour aligned within 0.25 mm of the labels at five landmarks, and at least 30 frames per second
at phone tier on his iPad, 60 on a PC). The full plan, risks and the VES comparison protocol are
in the plan document's "Phase 2B plan" tab.

1. Dev workflow to extract ZETA's `04_Reconstruction_Microslicing/Microslicing_Zeta.nrrd`
   (3 channels, 792 x 792 x 346 at 0.05 x 0.05 x 0.15 mm, 305 MB compressed) through the
   existing remote-zip reader, resampled onto the segmentation grid (segmentation is RAS at
   0.125 mm; CBCT is LPS; check the micro-slicing space from its NRRD header first), cropped to
   the bone label, epoxy masked, saved at 0.1, 0.15 and 0.2 mm to a `dev-data-colour` branch.
2. Measure alignment: label boundaries vs colour edges at umbo, footplate, second genu, round
   window, lateral canal; report millimetres.
3. A minimal WebGL2 ray-march page behind a dev route (3D texture, front-to-back, early stop,
   headlight shading from CBCT gradient), timing logged on screen; the user measures his iPad.
4. Report in Arabic with pictures, then update the plan and this file.

Fallbacks if Gate 0 fails: re-register colour to CBCT; colour only the bone and keep meshes for
soft tissue; or bake colour onto mesh textures.

**WP0 status, 27 Nov (alignment measured, speed test page live, waiting for the iPad numbers):**
- Space: the micro-slicing NRRD header says LPS with `space origin (0,0,0)`, which looked
  unregistered, but a mutual-information search against the embedded CBCT (24 flips x z offsets x
  rotations, then rigid refinement; scripts in `.github/scripts/wp0/`) found no flip, no rotation
  and a shift under 0.1 mm. The colour volume is already in the specimen frame (RAS mm, voxel
  centre i at i x step; a block average of f voxels is centred (f-1)/2 steps later). An earlier note
  in this file, that it was not registered, was wrong.
- Alignment at the native crop (0.05 x 0.05 x 0.15 mm), median |label boundary - colour edge| along
  the normal after one global shift colour = label + (-0.075, -0.05, +0.125) mm: umbo 0.125,
  footplate 0.175, second genu 0.15, lateral canal 0.275 (computed proxy), round window 0.10 (proxy:
  ZETA has no RW label); 75th percentiles 0.28 to 0.45 mm. Gate 0 (0.25 mm) is met by the median at
  4 of 5, on the noise floor (label voxel 0.125, section step 0.15): borderline, not decisive. The
  per-patch best translation is unreliable (aperture problem); use the normal offsets.
- Colour data: branch `dev-data-colour-products` (native ear crop, RGBA at 0.1/0.15/0.2 mm; alpha is
  a saturation ramp, epoxy transparent, so epoxy-filled air cells read as air; the bbox crop there
  is not tight) and `dev-data-colour-web` (browser volumes cropped to 32 x 35 x 53 mm, CBCT-gradient
  normals on a 0.2 mm grid, 0.1 mm colour in two parts that join by concatenation). Rebuild with the
  workflows `dev-extract-colour-products.yml`, then `dev-colour-web.yml`.
- Speed test: `https://aliremuhammad-spec.github.io/otoatlas-3d/dev/raymarch.html` (source
  `app/public/dev/raymarch.html`; plain WebGL2, Arabic UI, linked only from Settings → تجريبي). Loading screen
  with percentage and steps; three tabs: التعليمات (what it is, how to navigate, what is shown),
  العرض (resolution, opaque/translucent, render scale, step, cut into block, auto-orbit, live fps)
  and قياس السرعة (Benchmark: GPU time with a 1-pixel readback, 0.2/0.15 and optionally 0.1 mm x cut
  0 and 0.4 x two modes x scale 0.5 and 1, a verdict for 30 and 60 fps, Copy results). Downloads go
  through Cache Storage (`otoatlas-ray-<build>`), so the second visit opens at once. Normals are now
  on a 0.4 mm grid (3.4 MB instead of 27 MB); first load of 0.2 mm is about 20 MB.
  Measured on his Windows PC (AMD Radeon integrated, Chrome), full screen 1920x799, worst case
  (cut 0): 0.2 mm 190 to 217 fps, 0.15 mm 102 to 116 fps, 0.1 mm 47 to 53 fps; typical (cut 0.4):
  0.2 and 0.15 mm 280 to 300 fps, 0.1 mm 67 to 81 fps. The PC half of Gate 0 (60 fps) is met at 0.2
  and 0.15 mm. Still to measure: the iPad and a phone. Empty-space skipping added (8^3-voxel occupancy blocks, `?noskip` or `__ray.setSkip(0)` to compare): on his PC at the default view 4.3 to 5.2 ms with and without it, so no gain there; swiftshader slightly slower. Kept (harmless); the cost is dominated by opaque surface rays.
- Phone result, 28 Nov (his Android phone, Mali-G57 MC2, Chrome 158, DPR 2.75, 393x736 CSS px; low tier):
  at half render scale (393x736) opaque worst case 0.2 mm 37 fps, 0.15 mm 31 fps; translucent worst 39 and 26;
  typical (cut 0.4) 76 to 101 fps. At full device resolution (786x1472) 15 to 21 fps worst, 26 to 48 typical,
  so full resolution fails 30 fps. iPad still unmeasured (faster GPU expected). Decision proposed: phone default
  0.2 mm at half render scale, PC/tablet 0.15 mm; adaptive render scale. The page verdict now also reports half scale.
- App access: Settings → «تجريبي» (Experimental) has a link to `dev/raymarch.html` (`data-testid="raymarch-link"`). It is only the speed test, not the surgical view (WP1 onward not built).
- PWA trap: the app's service worker (registerType 'prompt') used to precache `/dev/raymarch.html`
  and answer any other `/dev/` URL with the app's index.html (a white page). `vite.config.ts` now
  has `globIgnores: ['dev/**']` and `navigateFallbackDenylist: [/\/dev\//]`. A browser that already
  has the old worker keeps the stale page until it updates (banner «حدّث الآن») or the worker is
  unregistered; when doing that, delete only the `workbox-precache*` cache, never `specimen-content`.
- Shell facts: the shell cannot reach Zenodo, so extraction runs as dev workflows, dispatched with
  `gh api -X POST repos/aliremuhammad-spec/otoatlas-3d/actions/workflows/<file>/dispatches -f ref=main`
  (`gh workflow run` fails: GraphQL is blocked); git push and clone of the repo work.
- CI note: `src/measure/surfaceDistance.test.ts` "sphere centred in a ring" took 5.5 s against its
  5 s limit on the runner and failed the app job on 27 Nov (twice); timeout raised to 30 s (fixed).
- Next: read the iPad and phone results; if 0.15 mm holds 30 fps go on to WP1, otherwise use 0.2 mm or half
  render scale, or bake colour onto mesh textures. Also open: tighten the specimen mask, and the
  five landmarks need his review (lateral canal and round window are proxies).

## Later phases

2B surgical view (16 to 18 sessions, nine work packages) → 3 drilling core and cochlear
implantation → 4 stapes, cholesteatoma, endoscopes → 5 sandbox, studio, assessment → 6 packaging
(Android, Windows, iPad), with an Arabic UI review gate before release.

## Things learned the hard way

- Zenodo answers 403 under load: the deploy plan reads `.github/specimens.json`, not Zenodo;
  fetch retries with long backoff; at most four content jobs at once.
- DELTA needs bounded inflate and reading only wanted segments, or the runner runs out of memory.
- In e2e, a page reload hands content requests to the service worker past the fixture routes;
  test persistence by leaving and reopening the viewer instead.
- jsdom has no `scrollIntoView`; guard it.
- `react-hooks/exhaustive-deps`: use the ref pattern (`selectRef`, `showRef`).
- Arabic numerals: Western digits by default; `localizeDigits` handles the setting.
