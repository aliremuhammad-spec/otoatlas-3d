import { ar } from './ar';
import { en, type MessageKey } from './en';

export type Locale = 'en' | 'ar';
export type Direction = 'ltr' | 'rtl';
export type Params = Readonly<Record<string, string | number>>;
export type Translate = (key: MessageKey, params?: Params) => string;

export const LOCALES: readonly Locale[] = ['en', 'ar'];
/** Each language is named in its own script so a user can always find it. */
export const LOCALE_NAMES: Readonly<Record<Locale, string>> = { en: 'English', ar: 'العربية' };

const CATALOGS: Readonly<Record<Locale, Readonly<Record<MessageKey, string>>>> = { en, ar };

export function directionOf(locale: Locale): Direction {
  return locale === 'ar' ? 'rtl' : 'ltr';
}

export function translate(locale: Locale, key: MessageKey, params?: Params): string {
  const template = CATALOGS[locale][key];
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

/** Picks the start-up language from the device's preferred languages. */
export function detectLocale(preferred: readonly string[]): Locale {
  for (const tag of preferred) {
    const base = tag.toLowerCase().split('-')[0];
    if (base === 'ar') return 'ar';
    if (base === 'en') return 'en';
  }
  return 'en';
}
