import { Disclaimer } from '../components/Disclaimer';
import { SupervisionCredit } from '../components/SupervisionCredit';
import { DATASET_CREDITS } from '../content/datasets';
import { useI18n } from '../i18n/I18nProvider';
import { localizeDigits } from '../i18n/numerals';

interface Props {
  onBack: () => void;
}

export function About({ onBack }: Props) {
  const { t, numerals } = useI18n();
  return (
    <div className="page" data-testid="about-screen">
      <header className="page__header">
        <button type="button" onClick={onBack}>
          {t('nav.back')}
        </button>
        <h1>{t('about.title')}</h1>
      </header>
      <main className="page__body">
        {/* Order is a requirement: credit first, then version, then data credits. */}
        <SupervisionCredit variant="prominent" />
        <p data-testid="app-version">
          {t('about.version', { version: localizeDigits(__APP_VERSION__, numerals) })}
        </p>
        <Disclaimer />
        <section aria-labelledby="data-title" data-testid="data-credits">
          <h2 id="data-title">{t('about.dataTitle')}</h2>
          <p>{t('about.dataNone')}</p>
          <p>{t('about.dataPlanned')}</p>
          <ul className="citations">
            {DATASET_CREDITS.map((d) => (
              <li key={d.id} dir="ltr" lang="en">
                {d.citation} doi:{d.paperDoi}. Data: doi:{d.dataDoi}. {d.license}.
              </li>
            ))}
          </ul>
        </section>
      </main>
    </div>
  );
}
