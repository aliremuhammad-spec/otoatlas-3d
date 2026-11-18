import type { BufferGeometry } from 'three';

/** Display names of a structure. Latin is the Terminologia Anatomica term, when one exists. */
export interface StructureNames {
  en: string;
  ar: string | null;
  latin: string | null;
}

/** What the info card says about a structure from a specimen package. */
export interface StructureInfo {
  provenanceTier: 'specimen-derived' | 'expert-annotated' | 'schematic';
  contentStatus: 'draft' | 'expert-reviewed';
  /** Voxel edges of the label the mesh was built from, in millimetres. */
  sourceVoxelMm: readonly [number, number, number];
  meshErrorLimitMm: number;
  /** Measured distance of the shown mesh from its label surface. */
  shownErrorMm: number;
  description: { en: string; ar: string; status: 'draft' | 'reviewed' } | null;
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
  /**
   * False when the shown mesh is a simplified display level outside the error limit:
   * the structure is then for orientation only and takes no measurement. Absent means true.
   */
  measurable?: boolean;
  /** False when the structure starts hidden. Absent means shown. */
  defaultVisible?: boolean;
  /** Opacity the structure starts at; 1 when not given. */
  defaultOpacity?: number;
  /** Absent for synthetic phantoms. */
  info?: StructureInfo;
}

export interface SceneContent {
  specimenId: string;
  /** Dataset the specimen comes from, such as "openear" or "bern". Null for synthetic content. */
  dataset: string | null;
  side: 'left' | 'right' | null;
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
