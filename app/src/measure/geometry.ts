/**
 * Point-based measurements. All inputs and outputs are in millimetres and
 * all arithmetic is IEEE-754 double precision.
 */
export type Vec3 = readonly [x: number, y: number, z: number];

function sub(a: Vec3, b: Vec3): Vec3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function dot(a: Vec3, b: Vec3): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function norm(a: Vec3): number {
  return Math.hypot(a[0], a[1], a[2]);
}

/** Straight-line distance between two points. */
export function distance(a: Vec3, b: Vec3): number {
  return norm(sub(a, b));
}

/** Length of the polyline through `points`, in order. */
export function pathLength(points: readonly Vec3[]): number {
  let total = 0;
  for (let i = 1; i < points.length; i += 1) {
    const prev = points[i - 1];
    const cur = points[i];
    if (prev && cur) total += distance(prev, cur);
  }
  return total;
}

/**
 * Angle at `vertex` between the rays to `a` and to `b`, in degrees (0 to 180).
 * Returns NaN when either ray has zero length, because the angle is undefined.
 */
export function angleAt(vertex: Vec3, a: Vec3, b: Vec3): number {
  const u = sub(a, vertex);
  const v = sub(b, vertex);
  const lu = norm(u);
  const lv = norm(v);
  if (lu === 0 || lv === 0) return Number.NaN;
  const cos = Math.min(1, Math.max(-1, dot(u, v) / (lu * lv)));
  return (Math.acos(cos) * 180) / Math.PI;
}

/**
 * Dihedral angle between two planes given by their normals, in degrees (0 to 90).
 * Normals need not be unit length; their sign is ignored.
 */
export function angleBetweenPlanes(normalA: Vec3, normalB: Vec3): number {
  const la = norm(normalA);
  const lb = norm(normalB);
  if (la === 0 || lb === 0) return Number.NaN;
  const cos = Math.min(1, Math.abs(dot(normalA, normalB)) / (la * lb));
  return (Math.acos(cos) * 180) / Math.PI;
}
