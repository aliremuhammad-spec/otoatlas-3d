import type { ManifestColour, ManifestColourVolume } from '../viewer/manifest';
import { MIN_RENDER_SCALE, adaptScale, chooseTier, isPhone } from './tier';

function volume(spacingMm: number, onSite: boolean): ManifestColourVolume {
  return {
    spacingMm,
    dims: [10, 10, 10],
    originMm: [0, 0, 0],
    index: `colour/x_${spacingMm}.json`,
    bricks: `colour/x_${spacingMm}.bricks`,
    bytes: 1000,
    onSite,
    url: onSite ? null : 'https://huggingface.co/datasets/u/r/resolve/' + 'a'.repeat(40) + '/x.bricks',
  };
}

const colour: ManifestColour = {
  alphaSource: 'colour',
  levelled: true,
  shiftMm: [0, 0, 0],
  brick: 64,
  tiers: [volume(0.1, false), volume(0.15, true), volume(0.2, true)],
  normals: null,
};

const phone = { shortSide: 393, coarsePointer: true };
const tablet = { shortSide: 820, coarsePointer: true };
const computer = { shortSide: 900, coarsePointer: false };

describe('tier choice', () => {
  it('recognises a phone only by a small touch screen', () => {
    expect(isPhone(phone)).toBe(true);
    expect(isPhone(tablet)).toBe(false);
    expect(isPhone({ shortSide: 400, coarsePointer: false })).toBe(false);
  });

  it('gives a phone 0.2 mm at half render scale', () => {
    const c = chooseTier(colour, phone);
    expect(c?.volume.spacingMm).toBe(0.2);
    expect(c?.renderScale).toBe(0.5);
  });

  it('gives tablets and computers 0.15 mm at full render scale', () => {
    for (const d of [tablet, computer]) {
      const c = chooseTier(colour, d);
      expect(c?.volume.spacingMm).toBe(0.15);
      expect(c?.renderScale).toBe(1);
    }
  });

  it('never picks the 0.1 mm tier, which is not on the site', () => {
    expect(chooseTier(colour, computer, 'fine')?.volume.spacingMm).toBe(0.15);
    expect(chooseTier({ ...colour, tiers: [volume(0.1, false)] }, computer)).toBeNull();
  });

  it('lets the user force a tier and falls back to the nearest one the specimen has', () => {
    expect(chooseTier(colour, phone, 'fine')?.volume.spacingMm).toBe(0.15);
    expect(chooseTier(colour, computer, 'standard')?.volume.spacingMm).toBe(0.2);
    expect(chooseTier({ ...colour, tiers: [volume(0.2, true)] }, computer)?.volume.spacingMm).toBe(0.2);
  });
});

describe('adaptive render scale', () => {
  it('lowers the scale under 30 frames per second, down to a floor', () => {
    expect(adaptScale(1, 24, 1)).toBeCloseTo(0.9);
    expect(adaptScale(MIN_RENDER_SCALE, 10, 1)).toBe(MIN_RENDER_SCALE);
  });

  it('grows back slowly when the view is fast, never above the starting scale', () => {
    expect(adaptScale(0.5, 60, 1)).toBeCloseTo(0.55);
    expect(adaptScale(0.5, 60, 0.5)).toBe(0.5);
  });

  it('leaves the scale alone in between', () => {
    expect(adaptScale(0.7, 40, 1)).toBe(0.7);
  });
});
