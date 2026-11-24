import type { BufferGeometry, Mesh, Object3D } from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { SceneContent, SceneStructure } from './content';
import { parseManifest, parseSpecimenIndex, type Manifest, type SpecimenIndexEntry } from './manifest';

/** Folder that holds specimen packages, relative to the app. */
export const CONTENT_BASE = './content';

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url, { cache: 'no-cache' });
  if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
  return (await response.json()) as unknown;
}

/** Installed specimens, or an empty list when no content is installed. */
export async function listSpecimens(base = CONTENT_BASE): Promise<SpecimenIndexEntry[]> {
  try {
    return parseSpecimenIndex(await fetchJson(`${base}/index.json`));
  } catch {
    return [];
  }
}

function firstGeometry(root: Object3D): BufferGeometry | null {
  let found: BufferGeometry | null = null;
  root.traverse((node) => {
    const mesh = node as Mesh;
    if (!found && mesh.isMesh) found = mesh.geometry;
  });
  return found;
}

export function sceneFromManifest(
  manifest: Manifest,
  geometries: ReadonlyMap<string, BufferGeometry>,
  root = '',
): SceneContent {
  const structures: SceneStructure[] = manifest.structures.map((s) => {
    const geometry = geometries.get(s.id);
    if (!geometry) throw new Error(`No geometry loaded for ${s.id}`);
    const shown = s.lods.find((l) => l.level === s.displayLevel);
    const measurable = shown?.withinLimit ?? false;
    return {
      id: s.id,
      names: s.names,
      color: s.color,
      geometry,
      position: [0, 0, 0],
      defaultOpacity: s.defaultOpacity,
      defaultVisible: s.defaultVisible,
      measurable,
      ...(shown && measurable ? { meshErrorMm: shown.hausdorffMm } : {}),
      info: {
        provenanceTier: s.provenanceTier,
        contentStatus: s.contentStatus,
        sourceVoxelMm: s.sourceVoxelMm,
        meshErrorLimitMm: s.meshErrorLimitMm,
        shownErrorMm: shown?.hausdorffMm ?? Number.NaN,
        description: s.description,
        computedPart: s.sourcePart !== null,
        divisionReview: s.divisionReview,
      },
      ...(s.group ? { group: s.group } : {}),
    };
  });
  return {
    specimenId: manifest.specimenId,
    dataset: manifest.synthetic ? null : manifest.dataset,
    side: manifest.side,
    synthetic: manifest.synthetic,
    draft: manifest.structures.some((s) => s.contentStatus === 'draft' || s.arStatus === 'unverified'),
    sourceVoxelMm: Math.max(...manifest.structures.flatMap((s) => [...s.sourceVoxelMm])),
    attribution: { dataDoi: manifest.attribution.dataDoi, license: manifest.attribution.license },
    structures,
    measurements: manifest.measurements,
    anatomicalFrame: manifest.anatomicalFrame,
    scan: manifest.scan
      ? {
          // This site's copy first; the pinned Hugging Face copy only if that fails. Some
          // networks cannot reach Hugging Face, and the scans then never arrived.
          urls: [`${root}/${manifest.scan.file}`, ...(manifest.scan.url ? [manifest.scan.url] : [])],
          shape: manifest.scan.shape,
          spacingMm: manifest.scan.spacingMm,
          originMm: manifest.scan.originMm,
          modality: manifest.scan.modality,
        }
      : null,
  };
}

/** A download that stops receiving data for this long is given up and the next source tried. */
const STALL_MS = 20_000;

export interface ScanProgress {
  received: number;
  total: number | null;
  source: number;
}

/** Fetches one URL, giving up when no data arrives for STALL_MS. */
async function fetchBytes(
  url: string,
  onBytes: (received: number, total: number | null) => void,
): Promise<Uint8Array<ArrayBuffer>> {
  const abort = new AbortController();
  let timer = setTimeout(() => abort.abort(), STALL_MS);
  const restart = () => {
    clearTimeout(timer);
    timer = setTimeout(() => abort.abort(), STALL_MS);
  };
  try {
    const response = await fetch(url, { signal: abort.signal });
    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
    const length = Number(response.headers.get('content-length'));
    const total = Number.isFinite(length) && length > 0 ? length : null;
    const reader = response.body.getReader();
    const chunks: Uint8Array[] = [];
    let received = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      restart();
      chunks.push(value);
      received += value.length;
      onBytes(received, total);
    }
    const out = new Uint8Array(received);
    let at = 0;
    for (const c of chunks) {
      out.set(c, at);
      at += c.length;
    }
    return out;
  } finally {
    clearTimeout(timer);
  }
}

async function gunzip(compressed: Uint8Array<ArrayBuffer>): Promise<Uint8Array> {
  if (typeof DecompressionStream === 'function') {
    const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }
  // iPadOS and iOS before 16.4 have no DecompressionStream.
  const { gunzipSync } = await import('three/examples/jsm/libs/fflate.module.js');
  return gunzipSync(compressed);
}

/**
 * Downloads and unpacks a scan (gzip, 8-bit), trying each source in turn. Throws an error
 * naming every source that failed and why.
 */
export async function loadScan(
  urls: readonly string[],
  shape: readonly [number, number, number],
  onProgress?: (p: ScanProgress) => void,
): Promise<Uint8Array> {
  const failures: string[] = [];
  for (const [source, url] of urls.entries()) {
    try {
      const compressed = await fetchBytes(url, (received, total) => onProgress?.({ received, total, source }));
      const bytes = await gunzip(compressed);
      if (bytes.length !== shape[0] * shape[1] * shape[2]) throw new Error('size does not match its shape');
      return bytes;
    } catch (e) {
      const why = e instanceof DOMException && e.name === 'AbortError' ? 'no data for 20 s' : String(e);
      failures.push(`${new URL(url, window.location.href).host}: ${why}`);
    }
  }
  throw new Error(failures.join('; '));
}

/**
 * Loads one specimen package: its manifest and, for every structure, the level the
 * manifest says to show (full resolution unless the mesh is too large for a tablet).
 */
export async function loadPackage(path: string, base = CONTENT_BASE): Promise<SceneContent> {
  const root = `${base}/${path}`;
  const manifest = parseManifest(await fetchJson(`${root}/manifest.json`));
  const loader = new GLTFLoader();
  const geometries = new Map<string, BufferGeometry>();
  await Promise.all(
    manifest.structures.map(async (s) => {
      const shown = s.lods.find((l) => l.level === s.displayLevel);
      if (!shown) throw new Error(`${s.id} has no level ${s.displayLevel}`);
      const gltf = await loader.loadAsync(`${root}/${shown.file}`);
      const geometry = firstGeometry(gltf.scene);
      if (!geometry) throw new Error(`${shown.file} contains no mesh`);
      // Smooth shading; the pipeline stores positions only.
      geometry.computeVertexNormals();
      geometries.set(s.id, geometry);
    }),
  );
  return sceneFromManifest(manifest, geometries, root);
}
