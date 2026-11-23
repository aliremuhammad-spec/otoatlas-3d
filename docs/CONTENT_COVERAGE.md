# Content coverage against the reference chapter

Reference: Janfaza P, Nadol JB Jr, Galla RJ, Fabian RL, Montgomery WW. *Surgical Anatomy of
the Head and Neck*, chapter on the temporal bone and ear (about book pages 423–492), supplied by the
reviewer on 20 November 2026. The chapter itself is not in this repository; this file lists its
topics in our own words and says how the app covers each one.

Target set by the reviewer: the app's level of detail must match or exceed the chapter's.

## How a topic can be covered

| Tier | Meaning | Measurable |
|---|---|---|
| **S** specimen-derived | Geometry from a dataset label, or a new segmentation of the specimen's own scan, with a method note | Yes |
| **A** expert-annotated | Point, line, region or volume placed on specimen geometry; first pass computed where possible, corrected by the reviewer | Yes, marked "annotation-based" |
| **D** schematic | Model not from the specimen, fitted to its landmarks, badged in every view | No; cited values shown instead |
| **T** text | Card text in our own words, reviewed: description, surgical relevance, variants, numbers with source | — |

Resolution decides the tier. OpenEar CBCT is 0.125 mm (BETA 0.05, DELTA 0.063); Bern micro-CT
is 0.061 mm. Anything thinner than about two voxels cannot be specimen-derived.

## Coverage map

Status: ✔ in the app now · ◐ partly · ○ planned.

### External ear

| Topic | Plan | Status |
|---|---|---|
| Auricle: surface landmarks, cartilage, ligaments, intrinsic and extrinsic muscles, vessels, nerves, lymph nodes | D (no dataset includes the auricle) + T | ○ |
| External canal: cartilaginous and bony parts, S-shaped course, two isthmuses, inferior tympanic recess, foramen of Huschke, relations (parotid, condyle, mastoid cells, epitympanum), skin, blood, nerves, lymph | S (canal label) + A (parts, isthmuses, recess) + measured lengths and diameters + T | ◐ label only |
| Tympanic membrane: diameters, angle to the canal, umbo, pars tensa and flaccida, malleal folds, notch of Rivinus, fibrous annulus, layers, blood and nerve supply, quadrants and what lies behind each | S (label) + computed quadrants and umbo from the malleus handle + label extents + T; pars flaccida, folds and annulus D | ◐ quadrants, umbo, extents and quadrant texts live |

### Middle ear

| Topic | Plan | Status |
|---|---|---|
| Malleus: head, neck, anterior process, lateral process, manubrium | S (whole bone) + computed parts (otopipe/ossicles.py) | ◐ head, neck, lateral process and handle computed on all 8 OpenEar specimens; length measured; anterior process not resolved in the labels |
| Incus: body, short, long and lenticular processes | S + computed parts | ◐ all four parts computed on all 8 OpenEar specimens |
| Stapes: head, neck, crura, footplate (about 3.0 × 1.4 mm), obturator foramen | S + computed parts + measured footplate | ◐ head and neck, both crura and footplate computed; a bone whose result fails the checks ships whole; footplate 2.5 to 3.5 × 1.0 to 1.9 mm |
| Suspensory ligaments (anterior, lateral, superior malleal; posterior and superior incudal; incudomallear), annular ligament | D + T | ○ |
| Joints: incudomallear, incudostapedial, stapediovestibular | A (contact zones) + T | ○ |
| Stapedius (canal, pyramidal eminence, tendon) and tensor tympani (semicanal, cochleariform process, tendon) | S where the canals show on CBCT + D for muscle and tendon + T | ○ |
| Middle ear cavity and its divisions: epi-, meso-, hypo-, pro- and posterior tympanum; dimensions | A (reviewer segments the cavity on the scan slices with a painting tool) + A (division planes) + measured. Computing it was tried and failed (see note below) | ○ |
| Walls: tegmen, jugular floor, carotid wall with tube opening, mastoid wall, lateral wall with scutum, labyrinthine wall | A on bone surface + T | ○ |
| Eminences, ridges and recesses: promontory, ponticulus, subiculum, pyramidal, chordal and styloid eminences and ridges, sinus tympani, facial recess, oval and round window niches, cochleariform process, anterior epitympanic recess, cog, Prussak's space, pouches of von Tröltsch | A (points, regions, volumes) + S where the air space defines them + T | ○ |
| Mucosal folds and their embryological sacs | D + T | ○ |
| Eustachian tube: bony and cartilaginous parts, isthmus, orifice, palatal muscles, supply | S for the bony part inside the scan + D beyond it + T | ○ |
| Pneumatization: regions, areas, tracts; antrum, aditus, Körner's septum; tegmental, sinodural, sinal, facial, tip and perilabyrinthine cells | S (air cells computed from CBCT) + A (region labels) + T | ○ |
| Blood supply and anomalies: tympanic arteries, persistent stapedial artery, aberrant internal carotid, high jugular bulb | D variants + T | ○ |
| Nerves: tympanic (Jacobson's), auricular branch of vagus (Arnold's), tympanic plexus, lesser petrosal | D + T | ○ |

### Inner ear and internal auditory canal

| Topic | Plan | Status |
|---|---|---|
| Bony labyrinth as a whole; otic capsule layers | S (Bern, OpenEar split) + T | ✔ + T ○ |
| Vestibule: elliptical and spherical recesses, vestibular crest, cochlear recess | A on Bern micro-CT | ○ |
| Cochlea: about 32 mm, two and a half turns, height, modiolus, osseous spiral lamina, helicotrema, scalae | S (scalae in OpenEar) + A and B values on every Bern specimen (live) + duct length once the reviewer picks a method + D for lamina | ◐ |
| Semicircular canals: planes, arc, ampullae, common crus, lengths and diameters | S (split label, Bern) + measured on each specimen | ◐ shape only |
| Aqueducts (vestibular, cochlear), paravestibular canaliculi, fissula ante fenestram, fossula post fenestram, Hyrtl's fissure | A on micro-CT where visible + D otherwise + T | ○ |
| Membranous labyrinth: cochlear duct, utricle, saccule, semicircular ducts, endolymphatic duct and sac | D fitted inside the bony labyrinth + T | ○ |
| Internal auditory canal: porus, fundus, falciform and vertical crests, nerve quadrants, dimensions | S (canal from bone) + A (crests) + D (nerves) + measured | ○ |
| Inner ear blood supply: labyrinthine artery and branches, AICA loop variants, veins | D + T | ○ |

### Facial nerve

| Topic | Plan | Status |
|---|---|---|
| Course: meatal, labyrinthine, geniculate, tympanic, second genu, mastoid segments; stylomastoid foramen | S (OpenEar label covers labyrinthine and tympanic) + new segmentation of the mastoid segment's canal from CBCT + A (segment boundaries) | ◐ |
| Branches: greater superficial petrosal, nerve to stapedius, chorda tympani | S (chorda label) + D + T | ◐ |
| Dehiscence, hiatus, anomalies | A where seen + T | ○ |
| Components, nuclei, central connections | T only (outside the temporal bone) | ○ |

## Working basis from 20 November 2026

The reviewer has no time to draw segmentations. Everything that would need drawing
(tympanic cavity and recesses, facial canal mastoid segment, air cells, ossicle parts
below what geometry can separate) is therefore covered by computed geometry where a
rule is reliable, and otherwise by badged schematic models and card text. The reviewer
checks by looking, not by drawing.

## Order of work proposed

1. Middle ear air space and its recesses (sinus tympani, facial recess, niches), with measurements.
2. Full facial canal course, including the mastoid segment.
3. Ossicle parts on the finest specimens, with the annotation tool the reviewer will use.
4. Tympanic membrane parts and quadrants.
5. Mastoid air cell system and pneumatization tracts.
6. Inner ear measurements and the membranous labyrinth (schematic).
7. Schematic layer for ligaments, folds, muscles, vessels and nerves; auricle.
8. Card text covering every topic above, reviewed.

## Notes on what was tried

**Ossicle parts by rule (23 November 2026).** Each bone is divided along its own shape:
cross-section area along the malleus axis (handle, lateral-process swelling, neck,
head), distance inside the incus from the tips of its two processes, and sections of the
stapes parallel to the plane where it meets the vestibule (crura are the sections that
fall into two pieces). Checks keep a bone whole when a result is implausible. Malleus lengths came out 7.9 to 9.1 mm. The same labels also give the side of each ear from the
handedness of lateral, anterior and superior: ALPHA, BETA, DELTA, THETA and ZETA right;
GAMMA, EPSILON and ETA left (ZETA matches the reviewer's call). The computed sides are not yet shown in the app.

**Tympanic cavity by rule (20 November 2026).** Three rule-based attempts to derive the
air space from the labels did not converge: each filled a ball around the ossicles
(1.5 to 3.2 mL against well under 1 mL expected). The OpenEar bone label leaves gaps in
less dense bone. In the registered CBCT the cavity is filled with epoxy, at values
overlapping thin bone. The unembedded CBCT does not line up with the labels. The colour
micro-slicing volume (0.05 × 0.05 × 0.15 mm) sits in its own frame, starting at the
origin, and its colours in the cavity overlap bone. The code stays in
`otopipe/airspace.py`, switched off. The cavity, the facial canal's mastoid segment and
the air cells need segmentation drawn on the slices, by the reviewer or under his
direction.
