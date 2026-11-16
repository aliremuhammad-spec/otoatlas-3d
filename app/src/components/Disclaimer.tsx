import { useI18n } from '../i18n/I18nProvider';

export function Disclaimer() {
  const { t } = useI18n();
  return (
    <section className="disclaimer" aria-labelledby="disclaimer-title">
      <h2 id="disclaimer-title">{t('disclaimer.title')}</h2>
      <p>{t('disclaimer.body')}</p>
    </section>
  );
}
