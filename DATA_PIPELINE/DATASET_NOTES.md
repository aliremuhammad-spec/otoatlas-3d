# Dataset notes

Facts read from the files themselves by `probe/report_*.py`, run on GitHub Actions on 2026-11-16.

## Human Bony Labyrinth (Zenodo 3355272, CC BY 4.0)

Checked on specimens F01 and T01.

- Archive layout: `<ID>/<ID>_DESC.json`, `<ID>/uCT/<ID>_uCT_{LABELS,RAW}.nii`, `<ID>/uCT/<ID>_uCT_SURF.ply`,
  and the same three under `<ID>/CT/`.
- Micro-CT: 0.0607 mm isotropic. F01 is 250 x 336 x 348 voxels. Labels are `uint8` with values 0 and 1.
- Clinical CT: 0.1562 x 0.1562 x 0.2 mm. F01 is 95 x 115 x 97 voxels.
- Descriptor: `ID`, `SIDE`, five `LANDMARKS` (RW, C, A, OW, V) and `COORD` (origin and three axes, two decimals).
- Volumes are axis-aligned; the NIfTI affine carries spacing and origin only.
- Irregularities in T01: the micro-CT surface is named `T1_uCT_SURF.ply`, and `T01_CT_SURF.ply` has the
  same byte size and vertex count as the micro-CT surface, so it is probably a duplicate. The pipeline
  rebuilds all surfaces from the label volumes and does not use the shipped PLY files.

## OpenEar (Zenodo 1473724, CC BY 4.0)

Checked on specimen ZETA (3.87 GB archive, read remotely without downloading it whole).

- Files the pipeline needs, with compressed sizes: `06_Segmentation/Segmentation.seg.nrrd` (3.6 MB),
  `05_Registred_Slicer_Volumes/CBCT_Embedded.nrrd` (116 MB),
  `04_Reconstruction_Microslicing/Microslicing_Zeta.nrrd` (305 MB). The other 2868 raw image files
  (10.2 GB unpacked) are not needed.
- Segmentation: 13 binary layers, 641 x 579 x 475 voxels at 0.125 mm, right-anterior-superior space.
- Segment names: Scala Tympani, Scala Vestibuli, Malleus, Incus, Stapes, Cochleovestibular nerve,
  Facial Nerve, Chorda Tympani, Bone, Tympanic Membrane, External Auditory Canal, Sinus Dura, Carotis Interna.
- CBCT: 668 x 587 x 625 voxels at 0.125 mm, left-posterior-superior space.
- Micro-slicing colour volume: 3 channels, 792 x 792 x 346 at 0.05 x 0.05 x 0.15 mm.
- Bounding boxes in ZETA: scala tympani about 5.2 x 6.9 x 8.5 mm; "Scala Vestibuli" about 12 x 14.6 x 15 mm,
  so that label probably includes the vestibule and semicircular canals; facial nerve about
  8.9 x 18.7 x 15.2 mm.

## Not usable yet

- Gerber et al. 2017 (SICAS repository): the site could not be reached and no data licence is stated in the paper.
- Visible Ear: no licence text permitting redistribution was found.
