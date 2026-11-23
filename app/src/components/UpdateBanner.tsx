import { useRegisterSW } from 'virtual:pwa-register/react';
import { useI18n } from '../i18n/I18nProvider';

/** How often an open app asks the server whether a newer build is out. */
const CHECK_EVERY_MS = 30 * 60 * 1000;

/**
 * Tells the user when a newer build has been downloaded and lets them switch to it.
 * Without this, an installed app (or a phone tab that is never closed) keeps running
 * the old build indefinitely.
 */
export function UpdateBanner() {
  const { t } = useI18n();
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      if (!registration) return;
      void registration.update();
      setInterval(() => void registration.update(), CHECK_EVERY_MS);
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') void registration.update();
      });
    },
  });
  if (!needRefresh) return null;
  return (
    <div className="update-banner" role="status">
      <span>{t('update.ready')}</span>
      <button type="button" className="primary" onClick={() => void updateServiceWorker(true)}>
        {t('update.apply')}
      </button>
      <button type="button" onClick={() => setNeedRefresh(false)} aria-label={t('viewer.card.close')}>
        ×
      </button>
    </div>
  );
}
