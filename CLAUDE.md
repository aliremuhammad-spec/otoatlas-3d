# OtoAtlas 3D: handoff for the next session

Last updated 27 November 2026, at the end of Phase 2 and before Phase 2B. Read this file first;
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
- At last count: 69 pipeline tests, 80 unit tests, and the e2e suites all pass.

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

## Next step: Phase 2B, WP0 (feasibility on ZETA), one session

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
  `app/public/dev/raymarch.html`; plain WebGL2, Arabic UI, not linked from the app). Loading screen
  with percentage and steps; three tabs: التعليمات (what it is, how to navigate, what is shown),
  العرض (resolution, opaque/translucent, render scale, step, cut into block, auto-orbit, live fps)
  and قياس السرعة (Benchmark: GPU time with a 1-pixel readback, 0.2/0.15 and optionally 0.1 mm x cut
  0 and 0.4 x two modes x scale 0.5 and 1, a verdict for 30 and 60 fps, Copy results). Downloads go
  through Cache Storage (`otoatlas-ray-<build>`), so the second visit opens at once. Normals are now
  on a 0.4 mm grid (3.4 MB instead of 27 MB); first load of 0.2 mm is about 20 MB.
  Measured on his Windows PC (AMD Radeon integrated, Chrome), full screen 1920x799, worst case
  (cut 0): 0.2 mm 190 to 217 fps, 0.15 mm 102 to 116 fps, 0.1 mm 47 to 53 fps; typical (cut 0.4):
  0.2 and 0.15 mm 280 to 300 fps, 0.1 mm 67 to 81 fps. The PC half of Gate 0 (60 fps) is met at 0.2
  and 0.15 mm. Still to measure: the iPad and a phone. Naive marching, no empty-space skipping yet.
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
  5 s limit on the runner and failed the app job on 27 Nov (twice); code untouched by WP0. Raise its
  timeout or speed it up.
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
