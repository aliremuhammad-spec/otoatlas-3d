import { ar } from './ar';
import { en, type MessageKey } from './en';
import { localizeDigits } from './numerals';
import { detectLocale, directionOf, translate } from './translate';

const keys = Object.keys(en) as MessageKey[];
const placeholders = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(',');

describe('message catalogs', () => {
  it('have exactly the same keys in Arabic and English', () => {
    expect(Object.keys(ar).sort()).toEqual([...keys].sort());
  });

  it('have no empty strings', () => {
    for (const k of keys) {
      expect(en[k].trim(), `en ${k}`).not.toBe('');
      expect(ar[k].trim(), `ar ${k}`).not.toBe('');
    }
  });

  it('use the same placeholders in both languages', () => {
    for (const k of keys) expect(placeholders(ar[k]), k).toBe(placeholders(en[k]));
  });

  it('translate every Arabic string except the product name and bare symbols', () => {
    for (const k of keys) {
      // The product name stays in Latin script; a symbol such as ° needs no translation.
      if (k === 'app.name' || !/[A-Za-z]/.test(en[k])) continue;
      expect(/[؀-ۿ]/.test(ar[k]), `ar ${k} contains no Arabic`).toBe(true);
    }
  });
});

describe('supervision credit wording', () => {
  // Release blocker: the wording is fixed by the product owner and must never drift.
  it('is exact in English', () => {
    expect(en['credit.supervision']).toBe('Designed under the supervision of Dr. Ali R. Muhammad');
  });

  it('is exact in Arabic', () => {
    expect(ar['credit.supervision']).toBe('تم تصميم التطبيق بإشراف د. علي ر. محمد');
  });
});

describe('translate', () => {
  it('fills placeholders and leaves unknown ones visible', () => {
    expect(translate('en', 'about.version', { version: '1.2.3' })).toBe('Version 1.2.3');
    expect(translate('en', 'about.version', {})).toBe('Version {version}');
  });

  it('maps locales to text direction', () => {
    expect(directionOf('ar')).toBe('rtl');
    expect(directionOf('en')).toBe('ltr');
  });

  it('picks the first supported device language and falls back to English', () => {
    expect(detectLocale(['ar-SY', 'en-US'])).toBe('ar');
    expect(detectLocale(['ru-RU', 'ar'])).toBe('ar');
    expect(detectLocale(['ru-RU', 'en-GB'])).toBe('en');
    expect(detectLocale(['ru-RU'])).toBe('en');
    expect(detectLocale([])).toBe('en');
  });
});

describe('numerals', () => {
  it('leaves Western digits unchanged', () => {
    expect(localizeDigits('2.93 mm', 'western')).toBe('2.93 mm');
  });

  it('converts digits and only decimal points between digits', () => {
    expect(localizeDigits('v0.1.0', 'eastern')).toBe('v٠٫١٫٠');
    expect(localizeDigits('3 mm.', 'eastern')).toBe('٣ mm.');
  });
});
