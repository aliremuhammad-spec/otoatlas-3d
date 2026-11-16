import { Matrix4, Vector3, type BufferGeometry } from 'three';
import { MeshBVH, type HitPointInfo } from 'three-mesh-bvh';
import type { Vec3 } from './geometry';

export interface SurfaceDistanceResult {
  /** Minimum distance between the two surfaces, in millimetres. Zero if they touch or cross. */
  distance: number;
  /** Closest point on surface A, in A's coordinates. */
  pointOnA: Vec3;
  /** Closest point on surface B, in A's coordinates. */
  pointOnB: Vec3;
}

const boundsTrees = new WeakMap<BufferGeometry, MeshBVH>();

function boundsTreeOf(geometry: BufferGeometry): MeshBVH {
  let tree = boundsTrees.get(geometry);
  if (!tree) {
    tree = new MeshBVH(geometry);
    boundsTrees.set(geometry, tree);
    geometry.boundsTree = tree;
  }
  return tree;
}

/**
 * Minimum distance between two triangulated surfaces (triangle to triangle, not
 * vertex to vertex).
 *
 * Vertex positions are stored as 32-bit floats, which resolves about 4e-6 mm at a
 * coordinate of 50 mm; the distance arithmetic itself is double precision. The
 * result can never be more accurate than the meshes are to the anatomy.
 *
 * @param bToA Transform taking B's coordinates into A's. Identity when both
 *             meshes share one specimen frame, which is the normal case.
 */
export function minSurfaceDistance(
  geometryA: BufferGeometry,
  geometryB: BufferGeometry,
  bToA: Matrix4 = new Matrix4(),
): SurfaceDistanceResult | null {
  const tree = boundsTreeOf(geometryA);
  boundsTreeOf(geometryB);
  const onA: HitPointInfo = { point: new Vector3(), distance: 0, faceIndex: 0 };
  const onB: HitPointInfo = { point: new Vector3(), distance: 0, faceIndex: 0 };
  const hit = tree.closestPointToGeometry(geometryB, bToA, onA, onB);
  if (!hit) return null;
  const a = onA.point;
  const b = onB.point.clone().applyMatrix4(bToA);
  return {
    distance: onA.distance,
    pointOnA: [a.x, a.y, a.z],
    pointOnB: [b.x, b.y, b.z],
  };
}
