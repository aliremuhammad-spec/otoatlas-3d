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
    const lod0 = s.lods.find((l) => l.level === 0);
    return {
      id: s.id,
      names: s.names,
      color: s.color,
      geometry,
      position: [0, 0, 0],
      ...(lod0 ? { meshErrorMm: lod0.hausdorffMm } : {}),
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

/** Loads one specimen package: its manifest and the full-resolution mesh of every structure. */
export async function loadPackage(path: string, base = CONTENT_BASE): Promise<SceneContent> {
  const root = `${base}/${path}`;
  const manifest = parseManifest(await fetchJson(`${root}/manifest.json`));
  const loader = new GLTFLoader();
  const geometries = new Map<string, BufferGeometry>();
  await Promise.all(
    manifest.structures.map(async (s) => {
      const lod0 = s.lods.find((l) => l.level === 0);
      if (!lod0) throw new Error(`${s.id} has no full-resolution level`);
      const gltf = await loader.loadAsync(`${root}/${lod0.file}`);
      const geometry = firstGeometry(gltf.scene);
      if (!geometry) throw new Error(`${lod0.file} contains no mesh`);
      // Smooth shading; the pipeline stores positions only.
      geometry.computeVertexNormals();
      geometries.set(s.id, geometry);
    }),
  );
  return sceneFromManifest(manifest, geometries);
}
