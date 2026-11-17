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
      measurable,
      ...(shown && measurable ? { meshErrorMm: shown.hausdorffMm } : {}),
    };
  });
  return {
    specimenId: manifest.specimenId,
    synthetic: manifest.synthetic,
    draft: manifest.structures.some((s) => s.contentStatus === 'draft' || s.arStatus === 'unverified'),
    sourceVoxelMm: Math.max(...manifest.structures.flatMap((s) => [...s.sourceVoxelMm])),
    attribution: { dataDoi: manifest.attribution.dataDoi, license: manifest.attribution.license },
    structures,
  };
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
  return sceneFromManifest(manifest, geometries);
}
