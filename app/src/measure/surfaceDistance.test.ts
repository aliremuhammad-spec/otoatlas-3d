import { IcosahedronGeometry, Matrix4, PlaneGeometry, TorusGeometry } from 'three';
import { minSurfaceDistance } from './surfaceDistance';

/**
 * Ground-truth phantoms. A tessellated sphere has its vertices on the true sphere
 * and its faces slightly inside it, by at most the sagitta of the longest edge.
 * Each test derives its tolerance from that bound instead of using a loose constant.
 */
function sphere(radius: number, detail: number) {
  const g = new IcosahedronGeometry(radius, detail);
  const edge = (radius * 2 * Math.sin(Math.atan(2) / 2)) / (detail + 1);
  // Chord sagitta, doubled as a safe bound for face centres.
  const inset = 2 * (radius - Math.sqrt(radius * radius - (edge * edge) / 4));
  return { geometry: g, inset };
}

describe('minimum surface-to-surface distance', () => {
  it('matches the analytic gap between two spheres', () => {
    const a = sphere(3, 40);
    const b = sphere(2, 40);
    const centreDistance = 8;
    const exact = centreDistance - 3 - 2;
    const result = minSurfaceDistance(
      a.geometry,
      b.geometry,
      new Matrix4().makeTranslation(centreDistance, 0, 0),
    );
    expect(result).not.toBeNull();
    const d = result?.distance ?? Number.NaN;
    // Faces sit inside the true spheres, so the mesh gap can only be larger than the exact gap.
    expect(d).toBeGreaterThanOrEqual(exact - 1e-6);
    expect(d - exact).toBeLessThan(a.inset + b.inset);
    expect(d - exact).toBeLessThan(0.05);
  });

  it('is independent of the direction of separation', () => {
    const a = sphere(3, 30);
    const b = sphere(2, 30);
    // (0.36, -0.48, 0.8) is a unit vector; centres are 7 mm apart along it.
    const m = new Matrix4().makeTranslation(0.36 * 7, -0.48 * 7, 0.8 * 7);
    const d = minSurfaceDistance(a.geometry, b.geometry, m)?.distance ?? Number.NaN;
    expect(d).toBeGreaterThanOrEqual(2 - 1e-6);
    expect(d - 2).toBeLessThan(a.inset + b.inset);
  });

  it('matches the analytic gap between a sphere and a plane', () => {
    const a = sphere(1.5, 40);
    const plane = new PlaneGeometry(20, 20, 4, 4); // lies in z = 0
    const height = 1.5 + 0.3;
    const m = new Matrix4().makeTranslation(0, 0, -height);
    const d = minSurfaceDistance(a.geometry, plane, m)?.distance ?? Number.NaN;
    expect(d).toBeGreaterThanOrEqual(0.3 - 1e-6);
    expect(d - 0.3).toBeLessThan(a.inset);
  });

  it('measures a sphere centred in a ring to the inner rim', () => {
    // Ring of major radius 4 and tube radius 0.5 around a sphere of radius 3: gap 0.5 mm.
    const a = sphere(3, 40);
    const ring = new TorusGeometry(4, 0.5, 96, 512);
    const d = minSurfaceDistance(a.geometry, ring)?.distance ?? Number.NaN;
    expect(Math.abs(d - 0.5)).toBeLessThan(0.01);
  }, 30_000);

  it('reports the two closest points one distance apart', () => {
    const a = sphere(3, 30);
    const b = sphere(2, 30);
    const r = minSurfaceDistance(a.geometry, b.geometry, new Matrix4().makeTranslation(8, 0, 0));
    expect(r).not.toBeNull();
    if (!r) return;
    const span = Math.hypot(
      r.pointOnA[0] - r.pointOnB[0],
      r.pointOnA[1] - r.pointOnB[1],
      r.pointOnA[2] - r.pointOnB[2],
    );
    expect(span).toBeCloseTo(r.distance, 5);
  });

  it('returns zero for surfaces that cross', () => {
    const a = sphere(3, 20);
    const b = sphere(2, 20);
    const d = minSurfaceDistance(a.geometry, b.geometry, new Matrix4().makeTranslation(4, 0, 0));
    expect(d?.distance).toBeLessThan(1e-6);
  });
});
