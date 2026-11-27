# OtoAtlas 3D

Educational 3D anatomy and procedure trainer for the middle and inner ear, in Arabic and English.

**Designed under the supervision of Dr. Ali R. Muhammad**
**تم تصميم التطبيق بإشراف د. علي ر. محمد**

Educational software only. Not a medical device. Not for diagnosis or for planning surgery on an individual patient.

## Status

End of Phase 2 (27 November 2026): eight specimens with computed and schematic anatomy, 70
chapter topics in Arabic and English, measurements, CT slices, and a phone layout. Next is
Phase 2B, the surgical view. `CLAUDE.md` holds the full state, the rules and the next step.

- Live build: https://aliremuhammad-spec.github.io/otoatlas-3d/ (published by the `deploy` workflow).
  All specimen content is **draft** until the named reviewer signs it off.

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

Specimen data is never committed. The `deploy` workflow downloads what it needs from Zenodo,
builds measured meshes (`DATA_PIPELINE/build_content.py`) and publishes them beside the app:

- OpenEar, doi:10.5281/zenodo.1473724, CC BY 4.0 (Sieber et al., Scientific Data 2019).
- Human Bony Labyrinth, doi:10.5281/zenodo.3355272, CC BY 4.0 (Wimmer et al., Data in Brief 2019).
