import { angleAt, angleBetweenPlanes, distance, pathLength, type Vec3 } from './geometry';

describe('point measurements', () => {
  it('measures a 3-4-5 triangle exactly', () => {
    expect(distance([0, 0, 0], [3, 4, 0])).toBe(5);
  });

  it('keeps sub-micrometre differences that single precision would lose', () => {
    // 50 mm offset plus 1e-7 mm step: float32 cannot represent the step, float64 can.
    const d = distance([50, 0, 0], [50.0000001, 0, 0]);
    expect(d).toBeGreaterThan(0.9e-7);
    expect(d).toBeLessThan(1.1e-7);
  });

  it('sums a multi-segment path', () => {
    const path: Vec3[] = [
      [0, 0, 0],
      [1, 0, 0],
      [1, 2, 0],
      [1, 2, 2],
    ];
    expect(pathLength(path)).toBe(5);
    expect(pathLength([[1, 1, 1]])).toBe(0);
  });

  it('approximates the length of a helix sampled finely', () => {
    // Helix of radius r and pitch p over n turns has length n * sqrt((2*pi*r)^2 + p^2).
    const r = 4;
    const pitch = 1.5;
    const turns = 2.5;
    const samples = 20000;
    const points: Vec3[] = [];
    for (let i = 0; i <= samples; i += 1) {
      const t = (i / samples) * turns * 2 * Math.PI;
      points.push([r * Math.cos(t), r * Math.sin(t), (pitch * t) / (2 * Math.PI)]);
    }
    const exact = turns * Math.hypot(2 * Math.PI * r, pitch);
    expect(Math.abs(pathLength(points) - exact)).toBeLessThan(1e-5);
  });

  it('measures three-point angles', () => {
    expect(angleAt([0, 0, 0], [1, 0, 0], [0, 1, 0])).toBeCloseTo(90, 12);
    expect(angleAt([0, 0, 0], [1, 0, 0], [-2, 0, 0])).toBeCloseTo(180, 12);
    expect(angleAt([0, 0, 0], [1, 0, 0], [1, Math.sqrt(3), 0])).toBeCloseTo(60, 10);
    expect(angleAt([0, 0, 0], [0, 0, 0], [1, 0, 0])).toBeNaN();
  });

  it('measures plane-to-plane angles regardless of normal direction', () => {
    expect(angleBetweenPlanes([0, 0, 1], [0, 0, -3])).toBeCloseTo(0, 12);
    expect(angleBetweenPlanes([0, 0, 1], [0, 1, 0])).toBeCloseTo(90, 12);
    expect(angleBetweenPlanes([0, 0, 1], [0, 1, 1])).toBeCloseTo(45, 12);
  });
});
