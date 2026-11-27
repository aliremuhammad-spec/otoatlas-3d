import { Disclaimer } from '../components/Disclaimer';
import { SupervisionCredit } from '../components/SupervisionCredit';
import { useI18n } from '../i18n/I18nProvider';
import type { ScreenId } from '../App';

interface Props {
  onNavigate: (screen: ScreenId) => void;
}

export function Home({ onNavigate }: Props) {
  const { t } = useI18n();
  return (
    <div className="page" data-testid="home-screen">
      <header className="page__header">
        <h1>{t('app.name')}</h1>
        <nav className="page__nav" aria-label={t('nav.home')}>
          <button type="button" onClick={() => onNavigate('about')}>
            {t('nav.about')}
          </button>
          <button type="button" onClick={() => onNavigate('settings')}>
            {t('nav.settings')}
          </button>
        </nav>
      </header>
      <main className="page__body">
        <p className="lead">{t('home.intro')}</p>
        <section className="home__mode" aria-labelledby="home-anatomy" data-testid="home-anatomy">
          <h2 id="home-anatomy">{t('home.anatomy.title')}</h2>
          <p>{t('home.anatomy.body')}</p>
          <button type="button" className="primary" onClick={() => onNavigate('viewer')}>
            {t('home.openViewer')}
          </button>
          <button type="button" className="secondary" onClick={() => onNavigate('topics')} data-testid="open-topics">
            {t('topics.open')}
          </button>
        </section>
        <section className="home__mode" aria-labelledby="home-surgical" data-testid="home-surgical">
          <h2 id="home-surgical">{t('home.surgical.title')}</h2>
          <p>{t('home.surgical.body')}</p>
          <button type="button" className="primary" onClick={() => onNavigate('surgical')} data-testid="open-surgical">
            {t('home.surgical.open')}
          </button>
        </section>
        <p className="note">{t('home.phaseNote')}</p>
        <Disclaimer />
      </main>
      <footer className="page__footer">
        <SupervisionCredit variant="footer" />
      </footer>
    </div>
  );
}
