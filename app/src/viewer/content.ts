import type { BufferGeometry } from 'three';

/** Display names of a structure. Latin is the Terminologia Anatomica term, when one exists. */
export interface StructureNames {
  en: string;
  ar: string | null;
  latin: string | null;
}

/** One selectable object in the scene. */
export interface SceneStructure {
  id: string;
  names: StructureNames;
  color: number;
  geometry: BufferGeometry;
  /** Position of the geometry in the specimen frame, in millimetres. */
  position: readonly [number, number, number];
  /** Measured distance between this mesh and its label surface, when it comes from a package. */
  meshErrorMm?: number;
}

export interface SceneContent {
  specimenId: string;
  /** True when the geometry is not derived from a specimen. Drives the on-screen badge. */
  synthetic: boolean;
  /** True when any structure is still awaiting expert review. */
  draft: boolean;
  /** Largest voxel edge of the source segmentation, in millimetres. Null for synthetic content. */
  sourceVoxelMm: number | null;
  /** Dataset credit shown with the specimen. Null for synthetic content. */
  attribution: { dataDoi: string; license: string } | null;
  structures: readonly SceneStructure[];
}
