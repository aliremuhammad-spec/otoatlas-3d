/**
 * Slices through a specimen scan, and the outlines that structure meshes cut on a slice.
 * Pure functions, so the geometry can be tested without a browser.
 *
 * Planes are the scan's own axes: 'z' is the XY plane, 'y' the XZ plane, 'x' the YZ plane.
 * They are the scanner's axes, not anatomical planes.
 */
export type Axis = 'x' | 'y' | 'z';

export interface ScanGrid {
  /** Voxel counts along x, y, z; the data has x varying fastest. */
  shape: readonly [number, number, number];
  spacingMm: readonly [number, number, number];
  /** Centre of voxel (0, 0, 0), millimetres. */
  originMm: readonly [number, number, number];
}

const AXIS_INDEX: Record<Axis, 0 | 1 | 2> = { x: 0, y: 1, z: 2 };

function pick(t: readonly [number, number, number], i: number): number {
  return i === 0 ? t[0] : i === 1 ? t[1] : t[2];
}

/** The two in-plane axes, horizontal first. Vertical runs upwards on screen. */
export function planeAxes(axis: Axis): readonly [number, number] {
  if (axis === 'z') return [0, 1];
  if (axis === 'y') return [0, 2];
  return [1, 2];
}

export function sliceCount(grid: ScanGrid, axis: Axis): number {
  return pick(grid.shape, AXIS_INDEX[axis]);
}

/** Millimetre position of slice `index` along `axis`. */
export function slicePosition(grid: ScanGrid, axis: Axis, index: number): number {
  const a = AXIS_INDEX[axis];
  return pick(grid.originMm, a) + index * pick(grid.spacingMm, a);
}

export interface SliceImage {
  width: number;
  height: number;
  /** Grey values, row 0 at the top of the image. */
  pixels: Uint8Array;
}

/** The grey image of one slice, oriented so the vertical axis points up. */
export function sliceImage(data: Uint8Array, grid: ScanGrid, axis: Axis, index: number): SliceImage {
  const [nx, ny] = grid.shape;
  const [h, v] = planeAxes(axis);
  const width = pick(grid.shape, h);
  const height = pick(grid.shape, v);
  const pixels = new Uint8Array(width * height);
  const k = Math.min(Math.max(Math.round(index), 0), sliceCount(grid, axis) - 1);
  for (let row = 0; row < height; row += 1) {
    const j = height - 1 - row;
    for (let i = 0; i < width; i += 1) {
      let x: number;
      let y: number;
      let z: number;
      if (axis === 'z') [x, y, z] = [i, j, k];
      else if (axis === 'y') [x, y, z] = [i, k, j];
      else [x, y, z] = [k, i, j];
      pixels[row * width + i] = data[x + nx * (y + ny * z)] ?? 0;
    }
  }
  return { width, height, pixels };
}

/**
 * Line segments where a triangle mesh crosses the plane `axis = position`, in in-plane
 * millimetres [h1, v1, h2, v2, ...]. `offset` moves the mesh into the specimen frame.
 */
export function meshSection(
  positions: ArrayLike<number>,
  index: ArrayLike<number> | null,
  axis: Axis,
  position: number,
  offset: readonly [number, number, number] = [0, 0, 0],
): Float32Array {
  const a = AXIS_INDEX[axis];
  const [h, v] = planeAxes(axis);
  const out: number[] = [];
  const triangles = index ? index.length / 3 : positions.length / 9;
  const p = [0, 0, 0, 0, 0, 0, 0, 0, 0];
  const d = [0, 0, 0];
  for (let t = 0; t < triangles; t += 1) {
    for (let c = 0; c < 3; c += 1) {
      const vi = index ? (index[3 * t + c] as number) : 3 * t + c;
      for (let q = 0; q < 3; q += 1) p[3 * c + q] = (positions[3 * vi + q] as number) + (offset[q] as number);
      d[c] = (p[3 * c + a] as number) - position;
    }
    const [d0, d1, d2] = d as [number, number, number];
    if ((d0 > 0 && d1 > 0 && d2 > 0) || (d0 < 0 && d1 < 0 && d2 < 0)) continue;
    const hits: number[] = [];
    for (const [e0, e1] of [
      [0, 1],
      [1, 2],
      [2, 0],
    ] as const) {
      const da = d[e0] as number;
      const db = d[e1] as number;
      if ((da > 0 && db > 0) || (da < 0 && db < 0) || da === db) continue;
      const s = da / (da - db);
      hits.push(
        (p[3 * e0 + h] as number) + s * ((p[3 * e1 + h] as number) - (p[3 * e0 + h] as number)),
        (p[3 * e0 + v] as number) + s * ((p[3 * e1 + v] as number) - (p[3 * e0 + v] as number)),
      );
      if (hits.length === 4) break;
    }
    if (hits.length === 4) out.push(...hits);
  }
  return new Float32Array(out);
}

/**
 * Whether the in-plane point (u, v) lies inside the closed outline a section forms,
 * by counting crossings of a ray towards +u. Works on the unordered segment soup that
 * meshSection returns, because a closed outline crosses the ray an odd number of times
 * exactly when the point is inside.
 */
export function insideSection(segs: ArrayLike<number>, u: number, v: number): boolean {
  let inside = false;
  for (let i = 0; i + 3 < segs.length; i += 4) {
    const u1 = segs[i] as number;
    const v1 = segs[i + 1] as number;
    const u2 = segs[i + 2] as number;
    const v2 = segs[i + 3] as number;
    if (v1 > v !== v2 > v) {
      const uc = u1 + ((v - v1) / (v2 - v1)) * (u2 - u1);
      if (uc > u) inside = !inside;
    }
  }
  return inside;
}

/** Area of the box around a section, in mm²: used to prefer the smallest of nested outlines. */
export function sectionBoxArea(segs: ArrayLike<number>): number {
  let u0 = Infinity;
  let v0 = Infinity;
  let u1 = -Infinity;
  let v1 = -Infinity;
  for (let i = 0; i + 1 < segs.length; i += 2) {
    const u = segs[i] as number;
    const v = segs[i + 1] as number;
    u0 = Math.min(u0, u);
    u1 = Math.max(u1, u);
    v0 = Math.min(v0, v);
    v1 = Math.max(v1, v);
  }
  return u1 > u0 && v1 > v0 ? (u1 - u0) * (v1 - v0) : 0;
}

/** A point on the outline to pin its name to: the outline point nearest the outline's centre. */
export function sectionAnchor(segs: ArrayLike<number>): readonly [number, number] | null {
  const n = Math.floor(segs.length / 2);
  if (n === 0) return null;
  let cu = 0;
  let cv = 0;
  for (let i = 0; i < n; i += 1) {
    cu += segs[2 * i] as number;
    cv += segs[2 * i + 1] as number;
  }
  cu /= n;
  cv /= n;
  let best = 0;
  let bestD = Infinity;
  for (let i = 0; i < n; i += 1) {
    const d = ((segs[2 * i] as number) - cu) ** 2 + ((segs[2 * i + 1] as number) - cv) ** 2;
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  }
  return [segs[2 * best] as number, segs[2 * best + 1] as number];
}

/**
 * Scanner-axis letters for the four edges of a slice: [left, right, bottom, top].
 * Axes follow the right-anterior-superior convention of the scan's own frame.
 */
export function edgeLetters(axis: Axis): readonly [string, string, string, string] {
  if (axis === 'z') return ['L', 'R', 'P', 'A'];
  if (axis === 'y') return ['L', 'R', 'I', 'S'];
  return ['P', 'A', 'I', 'S'];
}
