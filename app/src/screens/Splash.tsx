import { useEffect } from 'react';
import { SupervisionCredit } from '../components/SupervisionCredit';
import { useI18n } from '../i18n/I18nProvider';

/** The splash stays up at least this long so the supervision credit can be read. */
export const SPLASH_MIN_MS = 2500;

interface Props {
  onDone: () => void;
}

export function Splash({ onDone }: Props) {
  const { t } = useI18n();
  useEffect(() => {
    const timer = window.setTimeout(onDone, SPLASH_MIN_MS);
    return () => window.clearTimeout(timer);
  }, [onDone]);

  return (
    <main className="splash" data-testid="splash-screen">
      <h1 className="splash__name">{t('app.name')}</h1>
      <SupervisionCredit variant="prominent" />
      <p className="splash__tagline">{t('app.tagline')}</p>
    </main>
  );
}
