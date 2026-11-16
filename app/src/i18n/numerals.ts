export type NumeralSystem = 'western' | 'eastern';

const EASTERN_DIGITS = ['٠', '١', '٢', '٣', '٤', '٥', '٦', '٧', '٨', '٩'] as const;
const ARABIC_DECIMAL_SEPARATOR = '٫';

/** Converts Western digits (and the decimal point) in `text` to the chosen numeral system. */
export function localizeDigits(text: string, system: NumeralSystem): string {
  if (system === 'western') return text;
  return text.replace(/\d|(?<=\d)\.(?=\d)/g, (ch) =>
    ch === '.' ? ARABIC_DECIMAL_SEPARATOR : (EASTERN_DIGITS[Number(ch)] ?? ch),
  );
}
