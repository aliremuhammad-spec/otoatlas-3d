import { gunzip } from '../viewer/loadPackage';

/**
 * Reads the bricked colour volumes written by DATA_PIPELINE/otopipe/colour.py `bricks_encode`.
 * Each stored brick is gzipped on its own as [z][y][x][channel] bytes; bricks that are all zero
 * are not stored. The result is one array in the order a WebGL2 3D texture upload wants.
 */

export interface BrickIndex {
  channels: number;
  dims: readonly [number, number, number];
  brick: number;
  /** Each stored brick: [bx, by, bz, byte offset in the blob, byte length]. */
  bricks: readonly (readonly [number, number, number, number, number])[];
}

function isInt(v: unknown): v is number {
  return typeof v === 'number' && Number.isInteger(v);
}

/** Checks the index file strictly: a malformed index must fail loudly, never draw garbage. */
export function parseBrickIndex(value: unknown): BrickIndex {
  if (typeof value !== 'object' || value === null) throw new Error('brick index is not an object');
  const o = value as Record<string, unknown>;
  const dims = o.dims;
  if (!Array.isArray(dims) || dims.length !== 3 || !dims.every((d) => isInt(d) && d > 0)) {
    throw new Error('brick index dims are not three positive whole numbers');
  }
  if (!isInt(o.channels) || o.channels < 1 || o.channels > 4) throw new Error('brick index channels must be 1 to 4');
  if (!isInt(o.brick) || o.brick < 8) throw new Error('brick index brick size must be at least 8');
  if (!Array.isArray(o.bricks)) throw new Error('brick index has no brick list');
  const brick = o.brick;
  const bricks = o.bricks.map((b, i) => {
    if (!Array.isArray(b) || b.length !== 5 || !b.every(isInt) || b.some((n: number) => n < 0)) {
      throw new Error(`brick index entry ${i} is malformed`);
    }
    const e = b as [number, number, number, number, number];
    const d = dims as [number, number, number];
    if (e[0] * brick >= d[0] || e[1] * brick >= d[1] || e[2] * brick >= d[2]) {
      throw new Error(`brick index entry ${i} lies outside the volume`);
    }
    return e;
  });
  return { channels: o.channels, dims: dims as [number, number, number], brick, bricks };
}

/**
 * Unpacks all bricks into one array [z][y][x][channel]. `onProgress` gets the fraction done.
 * Bricks are decoded a few at a time so the page stays responsive on a phone.
 */
export async function decodeBricks(
  blob: Uint8Array<ArrayBuffer>,
  index: BrickIndex,
  onProgress?: (fraction: number) => void,
): Promise<Uint8Array> {
  const { channels: c, dims, brick: b } = index;
  const [nx, ny, nz] = dims;
  const out = new Uint8Array(nx * ny * nz * c);
  const total = index.bricks.length;
  let done = 0;
  const batch = 8;
  for (let start = 0; start < total; start += batch) {
    const slice = index.bricks.slice(start, start + batch);
    await Promise.all(
      slice.map(async ([bx, by, bz, offset, length]) => {
        if (offset + length > blob.length) throw new Error('brick lies beyond the end of the file');
        const x0 = bx * b;
        const y0 = by * b;
        const z0 = bz * b;
        const sx = Math.min(b, nx - x0);
        const sy = Math.min(b, ny - y0);
        const sz = Math.min(b, nz - z0);
        const raw = await gunzip(blob.subarray(offset, offset + length));
        if (raw.length !== sx * sy * sz * c) throw new Error('brick has the wrong size');
        for (let z = 0; z < sz; z++) {
          for (let y = 0; y < sy; y++) {
            const from = (z * sy + y) * sx * c;
            const to = (((z0 + z) * ny + (y0 + y)) * nx + x0) * c;
            out.set(raw.subarray(from, from + sx * c), to);
          }
        }
      }),
    );
    done += slice.length;
    onProgress?.(done / total);
  }
  return out;
}
