import { useI18n } from '../i18n/I18nProvider';

interface Props {
  /** `prominent` on the splash and About screens, `footer` on the home screen. */
  variant: 'prominent' | 'footer';
}

/** The supervision credit. Its wording comes only from the `credit.supervision` catalog entry. */
export function SupervisionCredit({ variant }: Props) {
  const { t } = useI18n();
  return (
    <p className={`credit credit--${variant}`} data-testid="supervision-credit">
      {t('credit.supervision')}
    </p>
  );
}
