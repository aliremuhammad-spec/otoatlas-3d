import { describe, expect, it } from 'vitest';
import { placeLabels, type Box } from './labels';

function overlap(a: Box, b: Box): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

describe('placeLabels', () => {
  const centre = { x: 400, y: 300 };

  it('puts a label outward from its anchor, growing away from the centre', () => {
    const right = placeLabels([{ id: 'r', x: 500, y: 300, w: 80, h: 20 }], centre).get('r');
    const left = placeLabels([{ id: 'l', x: 300, y: 300, w: 80, h: 20 }], centre).get('l');
    expect(right?.x).toBeGreaterThan(500);
    expect(left && left.x + left.w).toBeLessThan(300);
  });

  it('pushes overlapping labels apart', () => {
    const anchors = [
      { id: 'a', x: 500, y: 300, w: 120, h: 20 },
      { id: 'b', x: 502, y: 302, w: 120, h: 20 },
      { id: 'c', x: 504, y: 298, w: 120, h: 20 },
    ];
    const boxes = [...placeLabels(anchors, centre).values()];
    for (let i = 0; i < boxes.length; i += 1)
      for (let j = i + 1; j < boxes.length; j += 1) expect(overlap(boxes[i] as Box, boxes[j] as Box)).toBe(false);
  });

  it('handles an anchor exactly at the centre', () => {
    const box = placeLabels([{ id: 'c', x: 400, y: 300, w: 50, h: 20 }], centre).get('c');
    expect(box?.x).toBeGreaterThan(400);
  });
});
