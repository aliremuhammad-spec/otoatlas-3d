import type { ManifestColour, ManifestColourVolume } from '../viewer/manifest';

/** What the tier choice needs to know about the device. */
export interface DeviceProfile {
  /** Short side of the screen in CSS pixels. */
  shortSide: number;
  /** True for a touch screen without a mouse. */
  coarsePointer: boolean;
}

export type Quality = 'auto' | 'fine' | 'standard';

/** A phone: small touch screen. Tablets and computers get the finer tier. */
export function isPhone(d: DeviceProfile): boolean {
  return d.coarsePointer && d.shortSide < 600;
}

export interface TierChoice {
  volume: ManifestColourVolume;
  /** Render scale to start at: 0.5 means half the device pixels on each side. */
  renderScale: number;
}

/** The finest tier that is published on the site (the 0.1 mm tier lives on the mirror only). */
function onSiteTiers(colour: ManifestColour): readonly ManifestColourVolume[] {
  return colour.tiers.filter((t) => t.onSite);
}

/**
 * Tier rule agreed at Gate 0: phones use 0.2 mm at half render scale; tablets and computers use 0.15 mm.
 * The 0.1 mm tier is never chosen here. "fine" picks 0.15 mm and "standard" 0.2 mm whatever the device.
 * A specimen that lacks the wanted tier gets the nearest one it has.
 */
export function chooseTier(colour: ManifestColour, device: DeviceProfile, quality: Quality = 'auto'): TierChoice | null {
  const tiers = onSiteTiers(colour);
  if (tiers.length === 0) return null;
  const want = quality === 'fine' ? 0.15 : quality === 'standard' ? 0.2 : isPhone(device) ? 0.2 : 0.15;
  const best = tiers.reduce((a, t) => (Math.abs(t.spacingMm - want) < Math.abs(a.spacingMm - want) ? t : a));
  return { volume: best, renderScale: isPhone(device) ? 0.5 : 1 };
}

export const MIN_RENDER_SCALE = 0.35;
export const MAX_RENDER_SCALE = 1;
const SLOW_FPS = 30;
const FAST_FPS = 52;

/**
 * Adaptive render scale: below 30 frames per second the picture is made smaller, and when the view runs
 * comfortably fast it grows back toward the starting scale. `ceiling` is the scale the device starts at.
 * Returns the new scale (unchanged when the rate is fine).
 */
export function adaptScale(current: number, fps: number, ceiling: number): number {
  if (fps < SLOW_FPS && current > MIN_RENDER_SCALE) return Math.max(MIN_RENDER_SCALE, Math.round((current - 0.1) * 100) / 100);
  if (fps > FAST_FPS && current < ceiling) return Math.min(ceiling, Math.round((current + 0.05) * 100) / 100);
  return current;
}
