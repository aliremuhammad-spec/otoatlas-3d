/**
 * Content package manifest, as written by the data pipeline (`otopipe.package`).
 * Parsing is strict: a package the app cannot fully trust is rejected, never half-loaded.
 */
export interface ManifestLod {
  level: number;
  file: string;
  triangles: number;
  withinLimit: boolean;
  hausdorffMm: number;
  /** False when the file was measured but not shipped with the app. */
  published: boolean;
}

export interface StructureDescription {
  en: string;
  ar: string;
  status: 'draft' | 'reviewed';
}

export interface ManifestStructure {
  id: string;
  names: { en: string; ar: string | null; latin: string | null };
  arStatus: 'unverified' | 'verified';
  contentStatus: 'draft' | 'expert-reviewed';
  provenanceTier: 'specimen-derived' | 'expert-annotated' | 'schematic';
  color: number;
  meshErrorLimitMm: number;
  /** Opacity the structure starts at, 0 to 1. Large enclosing structures start faded. */
  defaultOpacity: number;
  /** Level the app shows. Above level 0 the structure is display-only unless that level is within its limit. */
  displayLevel: number;
  /** False for structures that start hidden. */
  defaultVisible: boolean;
  description: StructureDescription | null;
  sourceVoxelMm: readonly [number, number, number];
  lods: readonly ManifestLod[];
  /** For a part of a larger structure (a quadrant, a part of a bone): that structure. */
  group: { id: string; names: { en: string; ar: string | null; latin: string | null } } | null;
  /** Set when the structure is one part of a label divided by a computed rule. */
  sourcePart: string | null;
  /** Who checked the computed division, and when. */
  divisionReview: { by: string; on: string } | null;
}

export interface ManifestScan {
  file: string;
  /** Where the scan is published when it is not beside the manifest: a Hugging Face dataset file. */
  url: string | null;
  shape: readonly [number, number, number];
  spacingMm: readonly [number, number, number];
  originMm: readonly [number, number, number];
  modality: string;
}

/** Measurements the pipeline makes on a specimen; ids the app does not know are skipped. */
export const MEASUREMENT_IDS = [
  'cochlear_a_value',
  'cochlear_b_value',
  'tm_vertical_diameter',
  'tm_horizontal_diameter',
  'malleus_length',
  'stapes_footplate_length',
  'stapes_footplate_width',
  'tympanic_cavity_volume',
  'air_cells_volume',
] as const;
export type MeasurementId = (typeof MEASUREMENT_IDS)[number];

export interface SpecimenMeasurement {
  id: MeasurementId;
  /** In millimetres for lengths, millilitres for volumes (`unit`). */
  value: number;
  unit: 'mm' | 'mL';
  structures: readonly string[];
}

/** Unit directions of the ear in the specimen frame, computed from its labels. */
export interface AnatomicalFrame {
  lateral: readonly [number, number, number];
  anterior: readonly [number, number, number];
  superior: readonly [number, number, number];
}

export interface Manifest {
  measurements: readonly SpecimenMeasurement[];
  anatomicalFrame: AnatomicalFrame | null;
  /** The specimen's own scan for the slice view, when the package has one. */
  scan: ManifestScan | null;
  specimenId: string;
  dataset: string;
  side: 'left' | 'right' | null;
  synthetic: boolean;
  attribution: { dataDoi: string; paperDoi: string; license: string };
  structures: readonly ManifestStructure[];
}

export const SUPPORTED_SCHEMA = 1;

class ManifestError extends Error {}

function fail(message: string): never {
  throw new ManifestError(`Invalid content manifest: ${message}`);
}

function obj(value: unknown, what: string): Record<string, unknown> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) fail(`${what} is not an object`);
  return value as Record<string, unknown>;
}

function str(value: unknown, what: string): string {
  if (typeof value !== 'string' || value === '') fail(`${what} is not a non-empty string`);
  return value;
}

function strOrNull(value: unknown, what: string): string | null {
  return value === null || value === undefined ? null : str(value, what);
}

function num(value: unknown, what: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) fail(`${what} is not a finite number`);
  return value;
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[], what: string): T {
  if (typeof value !== 'string' || !allowed.includes(value as T)) fail(`${what} has an unknown value`);
  return value as T;
}

function parseColor(value: unknown, what: string): number {
  const text = str(value, what);
  if (!/^#[0-9a-fA-F]{6}$/.test(text)) fail(`${what} is not a #rrggbb colour`);
  return Number.parseInt(text.slice(1), 16);
}

function parseLod(value: unknown, what: string): ManifestLod {
  const o = obj(value, what);
  const file = str(o.file, `${what}.file`);
  // Files must sit beside the manifest; a path that climbs out of the package is refused.
  if (!/^[A-Za-z0-9._-]+\.glb$/.test(file)) fail(`${what}.file is not a plain .glb file name`);
  if (typeof o.within_limit !== 'boolean') fail(`${what}.within_limit is not a boolean`);
  return {
    level: num(o.level, `${what}.level`),
    file,
    triangles: num(o.triangles, `${what}.triangles`),
    withinLimit: o.within_limit,
    hausdorffMm: num(o.hausdorff_mm, `${what}.hausdorff_mm`),
    published: o.published === undefined ? true : bool(o.published, `${what}.published`),
  };
}

function bool(value: unknown, what: string): boolean {
  if (typeof value !== 'boolean') fail(`${what} is not a boolean`);
  return value;
}

function parseDescription(value: unknown, what: string): StructureDescription | null {
  if (value === undefined || value === null) return null;
  const o = obj(value, what);
  return {
    en: str(o.en, `${what}.en`),
    ar: str(o.ar, `${what}.ar`),
    status: oneOf(o.status, ['draft', 'reviewed'] as const, `${what}.status`),
  };
}

function parseOpacity(value: unknown, what: string): number {
  if (value === undefined || value === null) return 1;
  const n = num(value, what);
  if (n < 0 || n > 1) fail(`${what} is outside 0 to 1`);
  return n;
}

function parseStructure(value: unknown, index: number): ManifestStructure {
  const what = `structures[${index}]`;
  const o = obj(value, what);
  const names = obj(o.names, `${what}.names`);
  const voxel = o.source_voxel_mm;
  if (!Array.isArray(voxel) || voxel.length !== 3) fail(`${what}.source_voxel_mm is not three numbers`);
  if (!Array.isArray(o.lods) || o.lods.length === 0) fail(`${what}.lods is empty`);
  const lods = o.lods.map((l, i) => parseLod(l, `${what}.lods[${i}]`));
  const lod0 = lods.find((l) => l.level === 0);
  if (!lod0) fail(`${what} has no full-resolution level`);
  if (!lod0.withinLimit) fail(`${what} full-resolution mesh exceeds its error limit`);
  const displayLevel = o.display_level === undefined || o.display_level === null ? 0 : num(o.display_level, `${what}.display_level`);
  const shownLod = lods.find((l) => l.level === displayLevel);
  if (!shownLod) fail(`${what}.display_level names no level`);
  if (!shownLod.published) fail(`${what}.display_level names a level that was not published`);
  return {
    id: str(o.id, `${what}.id`),
    names: {
      en: str(names.en, `${what}.names.en`),
      ar: strOrNull(names.ar, `${what}.names.ar`),
      latin: strOrNull(names.latin, `${what}.names.latin`),
    },
    arStatus: oneOf(o.ar_status, ['unverified', 'verified'] as const, `${what}.ar_status`),
    contentStatus: oneOf(o.content_status, ['draft', 'expert-reviewed'] as const, `${what}.content_status`),
    provenanceTier: oneOf(
      o.provenance_tier,
      ['specimen-derived', 'expert-annotated', 'schematic'] as const,
      `${what}.provenance_tier`,
    ),
    color: parseColor(o.color, `${what}.color`),
    meshErrorLimitMm: num(o.mesh_error_limit_mm, `${what}.mesh_error_limit_mm`),
    defaultOpacity: parseOpacity(o.default_opacity, `${what}.default_opacity`),
    displayLevel,
    description: parseDescription(o.description, `${what}.description`),
    defaultVisible: o.default_visible === undefined || o.default_visible === null ? true : bool(o.default_visible, `${what}.default_visible`),
    sourceVoxelMm: [
      num(voxel[0], `${what}.source_voxel_mm[0]`),
      num(voxel[1], `${what}.source_voxel_mm[1]`),
      num(voxel[2], `${what}.source_voxel_mm[2]`),
    ],
    lods,
    group: parseGroup(o.group, `${what}.group`),
    sourcePart: o.source_part === undefined || o.source_part === null ? null : str(o.source_part, `${what}.source_part`),
    divisionReview: parseReview(o.division_review, `${what}.division_review`),
  };
}

function parseReview(value: unknown, what: string): { by: string; on: string } | null {
  if (value === undefined || value === null) return null;
  const o = obj(value, what);
  const on = str(o.on, `${what}.on`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(on)) fail(`${what}.on is not a date`);
  return { by: str(o.by, `${what}.by`), on };
}

function parseGroup(value: unknown, what: string): ManifestStructure['group'] {
  if (value === undefined || value === null) return null;
  const o = obj(value, what);
  const names = obj(o.names, `${what}.names`);
  return {
    id: str(o.id, `${what}.id`),
    names: {
      en: str(names.en, `${what}.names.en`),
      ar: strOrNull(names.ar, `${what}.names.ar`),
      latin: strOrNull(names.latin, `${what}.names.latin`),
    },
  };
}

export function parseManifest(value: unknown): Manifest {
  const o = obj(value, 'manifest');
  if (o.schema !== SUPPORTED_SCHEMA) fail(`schema ${String(o.schema)} is not supported`);
  if (o.units !== 'mm') fail('units must be millimetres');
  const attribution = obj(o.attribution, 'attribution');
  if (!Array.isArray(o.structures) || o.structures.length === 0) fail('structures is empty');
  if (typeof o.synthetic !== 'boolean') fail('synthetic is not a boolean');
  const side = o.side === null || o.side === undefined ? null : oneOf(o.side, ['left', 'right'] as const, 'side');
  return {
    specimenId: str(o.specimen_id, 'specimen_id'),
    dataset: str(o.dataset, 'dataset'),
    side,
    synthetic: o.synthetic,
    attribution: {
      dataDoi: str(attribution.data_doi, 'attribution.data_doi'),
      paperDoi: str(attribution.paper_doi, 'attribution.paper_doi'),
      license: str(attribution.license, 'attribution.license'),
    },
    structures: o.structures.map(parseStructure),
    scan: parseScan(o.scan),
    measurements: parseMeasurements(o.measurements),
    anatomicalFrame: parseFrame(o.anatomical_frame),
  };
}

function parseMeasurements(value: unknown): SpecimenMeasurement[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) fail('measurements is not a list');
  return value.flatMap((item, i) => {
    const o = obj(item, `measurements[${i}]`);
    const id = str(o.id, `measurements[${i}].id`);
    if (!(MEASUREMENT_IDS as readonly string[]).includes(id)) return [];
    if (!Array.isArray(o.structures)) fail(`measurements[${i}].structures is not a list`);
    return [
      {
        id: id as MeasurementId,
        ...(o.value_ml !== undefined
          ? { value: num(o.value_ml, `measurements[${i}].value_ml`), unit: 'mL' as const }
          : { value: num(o.value_mm, `measurements[${i}].value_mm`), unit: 'mm' as const }),
        structures: o.structures.map((s, j) => str(s, `measurements[${i}].structures[${j}]`)),
      },
    ];
  });
}

function parseFrame(value: unknown): AnatomicalFrame | null {
  if (value === undefined || value === null) return null;
  const o = obj(value, 'anatomical_frame');
  const unit = (v: unknown, what: string) => {
    const t = triple(v, `anatomical_frame.${what}`, false);
    if (Math.abs(Math.hypot(...t) - 1) > 0.01) fail(`anatomical_frame.${what} is not a unit vector`);
    return t;
  };
  return { lateral: unit(o.lateral, 'lateral'), anterior: unit(o.anterior, 'anterior'), superior: unit(o.superior, 'superior') };
}

function triple(value: unknown, what: string, positive: boolean): readonly [number, number, number] {
  if (!Array.isArray(value) || value.length !== 3) fail(`${what} is not three numbers`);
  const [a, b, c] = value.map((v, i) => num(v, `${what}[${i}]`)) as [number, number, number];
  if (positive && !(a > 0 && b > 0 && c > 0)) fail(`${what} must be positive`);
  return [a, b, c];
}

function parseScan(value: unknown): ManifestScan | null {
  if (value === undefined || value === null) return null;
  const o = obj(value, 'scan');
  const file = str(o.file, 'scan.file');
  if (!/^[A-Za-z0-9._-]+\.gz$/.test(file)) fail('scan.file is not a plain .gz file name');
  if (o.format !== 'uint8, gzip, x fastest') fail('scan.format is not supported');
  const shape = triple(o.shape, 'scan.shape', true);
  if (!shape.every(Number.isInteger)) fail('scan.shape must be whole numbers');
  let url: string | null = null;
  if (o.url !== undefined && o.url !== null) {
    url = str(o.url, 'scan.url');
    // Only the project's own kind of host: a public Hugging Face dataset file.
    if (!/^https:\/\/huggingface\.co\/datasets\/[\w.-]+\/[\w.-]+\/resolve\/[0-9a-f]{40}\/[\w./-]+\.gz$/.test(url))
      fail('scan.url is not a pinned Hugging Face dataset file');
  }
  return {
    file,
    url,
    shape,
    spacingMm: triple(o.spacing_mm, 'scan.spacing_mm', true),
    originMm: triple(o.origin_mm, 'scan.origin_mm', false),
    modality: str(o.modality, 'scan.modality'),
  };
}

export interface SpecimenIndexEntry {
  id: string;
  path: string;
  /** Dataset and side, when the index lists them, so the picker can group and label specimens. */
  dataset: string | null;
  side: 'left' | 'right' | null;
}

/** Parses `content/index.json`: the list of specimen packages installed beside the app. */
export function parseSpecimenIndex(value: unknown): SpecimenIndexEntry[] {
  const o = obj(value, 'index');
  if (!Array.isArray(o.specimens)) fail('index.specimens is not a list');
  return o.specimens.map((entry, i) => {
    const e = obj(entry, `specimens[${i}]`);
    const path = str(e.path, `specimens[${i}].path`);
    if (!/^[A-Za-z0-9._-]+$/.test(path)) fail(`specimens[${i}].path is not a plain folder name`);
    const dataset = e.dataset === undefined || e.dataset === null ? null : str(e.dataset, `specimens[${i}].dataset`);
    const side =
      e.side === undefined || e.side === null ? null : oneOf(e.side, ['left', 'right'] as const, `specimens[${i}].side`);
    return { id: str(e.id, `specimens[${i}].id`), path, dataset, side };
  });
}
