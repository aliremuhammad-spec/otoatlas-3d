import { describe, expect, it } from 'vitest';
import { estimateCdlOrganOfCorti } from './cdl';

describe('estimateCdlOrganOfCorti', () => {
  it('applies 4.16 × A − 4 (Alexiades 2015)', () => {
    expect(estimateCdlOrganOfCorti(9)).toBeCloseTo(33.44, 2);
    expect(estimateCdlOrganOfCorti(8.5)).toBeCloseTo(31.36, 2);
  });
});
