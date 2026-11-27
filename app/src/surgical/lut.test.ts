import { LUT_WIDTH, buildLut, isolate } from './lut';

describe('style table', () => {
  it('shows everything natural by default, including value 0', () => {
    const lut = buildLut([]);
    for (let v = 0; v < LUT_WIDTH; v++) {
      expect(lut[v * 4]).toBe(255);
      expect(lut[v * 4 + 1]).toBe(0);
    }
  });

  it('hides and tints by label value', () => {
    const lut = buildLut([
      { value: 3, visible: false, tint: null },
      { value: 7, visible: true, tint: 0xe69f00 },
    ]);
    expect(lut[3 * 4]).toBe(0);
    expect(lut[3 * 4 + 1]).toBe(0);
    expect(lut[7 * 4]).toBe(255);
    expect(lut[7 * 4 + 1]).toBe(128);
    const row1 = (LUT_WIDTH + 7) * 4;
    expect([lut[row1], lut[row1 + 1], lut[row1 + 2]]).toEqual([0xe6, 0x9f, 0x00]);
    expect(lut[4]).toBe(255); // a neighbour is untouched
  });

  it('ignores values it cannot hold', () => {
    const lut = buildLut([{ value: 0, visible: false, tint: null }, { value: 256, visible: false, tint: null }]);
    expect(lut[0]).toBe(255);
  });

  it('isolates one structure by hiding all the others', () => {
    expect([...isolate(['a', 'b', 'c'], 'b')].sort()).toEqual(['a', 'c']);
  });
});
