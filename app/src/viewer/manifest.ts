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
  sourceVoxelMm: readonly [number, number, number];
  lods: readonly ManifestLod[];
}

export interface Manifest {
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
    defaultVisible: o.default_visible === undefined || o.default_visible === null ? true : bool(o.default_visible, `${what}.default_visible`),
    sourceVoxelMm: [
      num(voxel[0], `${what}.source_voxel_mm[0]`),
      num(voxel[1], `${what}.source_voxel_mm[1]`),
      num(voxel[2], `${what}.source_voxel_mm[2]`),
    ],
    lods,
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
  };
}

export interface SpecimenIndexEntry {
  id: string;
  path: string;
}

/** Parses `content/index.json`: the list of specimen packages installed beside the app. */
export function parseSpecimenIndex(value: unknown): SpecimenIndexEntry[] {
  const o = obj(value, 'index');
  if (!Array.isArray(o.specimens)) fail('index.specimens is not a list');
  return o.specimens.map((entry, i) => {
    const e = obj(entry, `specimens[${i}]`);
    const path = str(e.path, `specimens[${i}].path`);
    if (!/^[A-Za-z0-9._-]+$/.test(path)) fail(`specimens[${i}].path is not a plain folder name`);
    return { id: str(e.id, `specimens[${i}].id`), path };
  });
}
