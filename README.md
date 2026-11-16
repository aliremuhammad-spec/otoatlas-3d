# OtoAtlas 3D

Educational 3D anatomy and procedure trainer for the middle and inner ear, in Arabic and English.

**Designed under the supervision of Dr. Ali R. Muhammad**
**تم تصميم التطبيق بإشراف د. علي ر. محمد**

Educational software only. Not a medical device. Not for diagnosis or for planning surgery on an individual patient.

## Status

Phase 1, in progress. What exists and is tested:

- `app/`: installable web app (PWA). Arabic and English with right-to-left layout, the supervision
  credit on the splash, home and About screens, a 3D viewer, and point-to-point and
  surface-to-surface distance tools. The viewer shows a **synthetic phantom** until specimen
  content is built; nothing anatomical is bundled yet.
- `DATA_PIPELINE/`: label volume to surface mesh with the geometric error measured against the
  label surface, plus scripts that describe the open datasets on Zenodo.
- `ontology/`: the structure list, with English, Terminologia Anatomica and Arabic names and a
  review status per Arabic term.

## Run it

```
cd app
npm ci
npm run dev        # development server
npm test           # unit tests
npm run build:pwa  # production build in app/dist
npm run e2e        # browser smoke tests against the build (needs Chrome)
```

```
cd DATA_PIPELINE
pip install -e ".[dev]"
python -m pytest -q
```

## Data

Specimen data is never committed. The pipeline downloads it from Zenodo:

- OpenEar, doi:10.5281/zenodo.1473724, CC BY 4.0 (Sieber et al., Scientific Data 2019).
- Human Bony Labyrinth, doi:10.5281/zenodo.3355272, CC BY 4.0 (Wimmer et al., Data in Brief 2019).
