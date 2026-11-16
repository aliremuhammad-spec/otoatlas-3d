import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { type NumeralSystem } from './numerals';
import {
  detectLocale,
  directionOf,
  translate,
  type Direction,
  type Locale,
  type Translate,
} from './translate';

const STORAGE_KEY = 'otoatlas.settings.v1';

interface StoredSettings {
  locale?: Locale;
  numerals?: NumeralSystem;
}

interface I18nValue {
  locale: Locale;
  dir: Direction;
  numerals: NumeralSystem;
  t: Translate;
  setLocale: (locale: Locale) => void;
  setNumerals: (numerals: NumeralSystem) => void;
}

const I18nContext = createContext<I18nValue | null>(null);

function readStored(): StoredSettings {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredSettings) : {};
  } catch {
    return {};
  }
}

function writeStored(settings: StoredSettings): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch {
    // Storage can be unavailable (private mode); the choice then lasts for this session only.
  }
}

interface ProviderProps {
  children: ReactNode;
  /** Overrides detection and storage. Used by tests. */
  initialLocale?: Locale;
}

export function I18nProvider({ children, initialLocale }: ProviderProps) {
  const stored = useMemo(readStored, []);
  const [locale, setLocaleState] = useState<Locale>(
    () => initialLocale ?? stored.locale ?? detectLocale(navigator.languages ?? [navigator.language]),
  );
  const [numerals, setNumeralsState] = useState<NumeralSystem>(() => stored.numerals ?? 'western');

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = directionOf(locale);
  }, [locale]);

  const setLocale = useCallback(
    (next: Locale) => {
      setLocaleState(next);
      writeStored({ locale: next, numerals });
    },
    [numerals],
  );
  const setNumerals = useCallback(
    (next: NumeralSystem) => {
      setNumeralsState(next);
      writeStored({ locale, numerals: next });
    },
    [locale],
  );

  const value = useMemo<I18nValue>(
    () => ({
      locale,
      dir: directionOf(locale),
      numerals,
      t: (key, params) => translate(locale, key, params),
      setLocale,
      setNumerals,
    }),
    [locale, numerals, setLocale, setNumerals],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error('useI18n must be used inside I18nProvider');
  return value;
}
