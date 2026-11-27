/**
 * The per-structure style table the shader reads: 256 columns (one per label value) and two rows.
 * Row 0: red = 255 when the structure is shown, 0 when hidden; green = how strongly it is tinted (0 to 255).
 * Row 1: the tint colour. Value 0 (no structure) is always shown, natural.
 */
export const LUT_WIDTH = 256;
export const LUT_ROWS = 2;
export const TINT_STRENGTH = 0.5;

export interface StyleInput {
  /** Label value in the volume, 1 to 255. */
  value: number;
  visible: boolean;
  /** 0xRRGGBB, or null for the natural colour. */
  tint: number | null;
}

export function buildLut(styles: Iterable<StyleInput>, strength = TINT_STRENGTH): Uint8Array {
  const lut = new Uint8Array(LUT_WIDTH * LUT_ROWS * 4);
  // Every value starts shown and natural, including the ones no structure uses.
  for (let v = 0; v < LUT_WIDTH; v++) lut[v * 4] = 255;
  for (const s of styles) {
    if (!Number.isInteger(s.value) || s.value < 1 || s.value >= LUT_WIDTH) continue;
    lut[s.value * 4] = s.visible ? 255 : 0;
    if (s.tint !== null) {
      lut[s.value * 4 + 1] = Math.round(Math.max(0, Math.min(1, strength)) * 255);
      const row1 = (LUT_WIDTH + s.value) * 4;
      lut[row1] = (s.tint >> 16) & 255;
      lut[row1 + 1] = (s.tint >> 8) & 255;
      lut[row1 + 2] = s.tint & 255;
      lut[row1 + 3] = 255;
    }
  }
  return lut;
}

/** What the structure panel keeps: which structures are hidden, and whether they are tinted with their colours. */
export interface StructureState {
  hidden: ReadonlySet<string>;
  tinted: boolean;
}

export function isolate(all: readonly string[], keep: string): Set<string> {
  return new Set(all.filter((id) => id !== keep));
}
