import { localizeDigits, type NumeralSystem } from '../i18n/numerals';

/**
 * Display rule from the product brief: two decimals below 5 mm, one decimal otherwise.
 * The rule is applied to the unrounded value, so 4.996 shows as "5.00".
 */
export function formatMillimetres(value: number, numerals: NumeralSystem = 'western'): string {
  if (!Number.isFinite(value)) return '—';
  const decimals = Math.abs(value) < 5 ? 2 : 1;
  return localizeDigits(value.toFixed(decimals), numerals);
}

/** Volumes in millilitres, to two decimals (the air spaces are worked on a 0.25 mm grid). */
export function formatMillilitres(value: number, numerals: NumeralSystem = 'western'): string {
  if (!Number.isFinite(value)) return '\u2014';
  return localizeDigits(value.toFixed(2), numerals);
}

/**
 * Voxel sizes are shown exactly as the dataset states them (for example 0.125 or 0.0607),
 * never rounded to the two decimals used for measurements.
 */
export function formatVoxelSize(value: number, numerals: NumeralSystem = 'western'): string {
  if (!Number.isFinite(value)) return '\u2014';
  return localizeDigits(String(Number(value.toFixed(4))), numerals);
}
