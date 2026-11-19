import { describe, expect, it } from 'vitest';
import { meshSection, sliceImage, slicePosition, type ScanGrid } from './slice';

const grid: ScanGrid = { shape: [3, 2, 2], spacingMm: [0.5, 0.5, 1], originMm: [10, 20, 30] };
// Value = x + 10 y + 100 z, x fastest.
const data = new Uint8Array(12).map((_, i) => (i % 3) + 10 * (Math.floor(i / 3) % 2) + 100 * Math.floor(i / 6));

describe('sliceImage', () => {
  it('shows the XY plane with x to the right and y upwards', () => {
    const img = sliceImage(data, grid, 'z', 1);
    expect([img.width, img.height]).toEqual([3, 2]);
    // Top row is the largest y.
    expect([...img.pixels]).toEqual([110, 111, 112, 100, 101, 102]);
  });

  it('shows the YZ plane with y to the right and z upwards', () => {
    const img = sliceImage(data, grid, 'x', 2);
    expect([...img.pixels]).toEqual([102, 112, 2, 12]);
  });

  it('places slices in millimetres', () => {
    expect(slicePosition(grid, 'z', 1)).toBe(31);
    expect(slicePosition(grid, 'x', 2)).toBe(11);
  });
});

describe('meshSection', () => {
  // One triangle standing across the plane z = 0.5.
  const tri = [0, 0, 0, 2, 0, 0, 0, 0, 2];

  it('cuts a triangle crossing the plane into one segment', () => {
    const seg = meshSection(tri, null, 'z', 0.5);
    expect(seg.length).toBe(4);
    const xs = [seg[0], seg[2]].sort();
    expect(xs[0]).toBeCloseTo(0);
    expect(xs[1]).toBeCloseTo(1.5);
  });

  it('ignores triangles on one side, and applies the offset and an index', () => {
    expect(meshSection(tri, null, 'z', 3).length).toBe(0);
    const seg = meshSection(tri, [0, 1, 2], 'z', 1.5, [0, 0, 1]);
    expect(seg.length).toBe(4);
  });
});

describe('section helpers', () => {
  // A unit square outline from (0,0) to (1,1), as an unordered list of segments.
  const square = [0, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1];

  it('tells inside from outside', async () => {
    const { insideSection } = await import('./slice');
    expect(insideSection(square, 0.5, 0.5)).toBe(true);
    expect(insideSection(square, 1.5, 0.5)).toBe(false);
    expect(insideSection(square, 0.5, -0.2)).toBe(false);
  });

  it('measures the box area and pins the label on the outline', async () => {
    const { sectionBoxArea, sectionAnchor } = await import('./slice');
    expect(sectionBoxArea(square)).toBeCloseTo(1);
    const a = sectionAnchor(square);
    expect(a).not.toBeNull();
    const [u, v] = a as [number, number];
    expect(u === 0 || u === 1 || v === 0 || v === 1).toBe(true);
  });

  it('labels the edges by scanner axes', async () => {
    const { edgeLetters } = await import('./slice');
    expect(edgeLetters('z')).toEqual(['L', 'R', 'P', 'A']);
    expect(edgeLetters('x')).toEqual(['P', 'A', 'I', 'S']);
  });
});
