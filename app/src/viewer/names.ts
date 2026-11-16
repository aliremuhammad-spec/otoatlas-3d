import type { Locale } from '../i18n/translate';
import type { StructureNames } from './content';

/** Name to show for a structure in the current language, falling back to English. */
export function displayName(names: StructureNames, locale: Locale): string {
  return locale === 'ar' ? (names.ar ?? names.en) : names.en;
}

/** The Latin (Terminologia Anatomica) term, when it adds information to the displayed name. */
export function latinLine(names: StructureNames, locale: Locale): string | null {
  if (!names.latin) return null;
  return names.latin === displayName(names, locale) ? null : names.latin;
}
