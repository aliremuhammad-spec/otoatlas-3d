import { useI18n } from '../i18n/I18nProvider';
import { LOCALE_NAMES, LOCALES } from '../i18n/translate';

interface Props {
  onBack: () => void;
}

export function Settings({ onBack }: Props) {
  const { t, locale, numerals, setLocale, setNumerals } = useI18n();
  return (
    <div className="page" data-testid="settings-screen">
      <header className="page__header">
        <button type="button" onClick={onBack}>
          {t('nav.back')}
        </button>
        <h1>{t('settings.title')}</h1>
      </header>
      <main className="page__body">
        <fieldset>
          <legend>{t('settings.language')}</legend>
          {LOCALES.map((l) => (
            <label key={l} className="choice">
              <input type="radio" name="locale" checked={locale === l} onChange={() => setLocale(l)} />
              <span lang={l}>{LOCALE_NAMES[l]}</span>
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>{t('settings.numerals')}</legend>
          <label className="choice">
            <input
              type="radio"
              name="numerals"
              checked={numerals === 'western'}
              onChange={() => setNumerals('western')}
            />
            <span>{t('settings.numerals.western')}</span>
          </label>
          <label className="choice">
            <input
              type="radio"
              name="numerals"
              checked={numerals === 'eastern'}
              onChange={() => setNumerals('eastern')}
            />
            <span>{t('settings.numerals.eastern')}</span>
          </label>
        </fieldset>
        <fieldset>
          <legend>{t('settings.experimental')}</legend>
          <p>{t('settings.experimental.note')}</p>
          <a href={`${import.meta.env.BASE_URL}dev/raymarch.html`} data-testid="raymarch-link">
            {t('settings.experimental.raymarch')}
          </a>
        </fieldset>
      </main>
    </div>
  );
}
