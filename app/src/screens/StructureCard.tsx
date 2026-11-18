import { useI18n } from '../i18n/I18nProvider';
import { formatMillimetres, formatVoxelSize } from '../measure/format';
import type { SceneContent, SceneStructure } from '../viewer/content';
import { displayName, latinLine } from '../viewer/names';

interface Props {
  structure: SceneStructure;
  content: SceneContent;
  onClose: () => void;
}

/** Facts about one structure: its names, where its geometry comes from, and how accurate the mesh is. */
export function StructureCard({ structure, content, onClose }: Props) {
  const { t, numerals, locale } = useI18n();
  const name = displayName(structure.names, locale);
  const latin = latinLine(structure.names, locale);
  const other = locale === 'ar' ? structure.names.en : structure.names.ar;
  const info = structure.info;
  const voxel = info
    ? [...new Set(info.sourceVoxelMm.map((v) => formatVoxelSize(v, numerals)))].join(' × ')
    : null;
  return (
    <section className="card" data-testid="structure-card" aria-label={name}>
      <header className="card__header">
        <div>
          <h2 className="card__title">{name}</h2>
          {latin && (
            <p className="card__latin" lang="la" dir="ltr">
              {latin}
            </p>
          )}
          {other && other !== name && other !== latin && (
            <p className="card__other" dir="auto">
              {other}
            </p>
          )}
        </div>
        <button type="button" onClick={onClose} aria-label={t('viewer.card.close')}>
          ×
        </button>
      </header>
      {info?.description && (
        <div className="card__description">
          <p>{locale === 'ar' ? info.description.ar : info.description.en}</p>
          {info.description.status === 'draft' && <p className="card__draft">{t('viewer.card.descriptionDraft')}</p>}
        </div>
      )}
      {info ? (
        <dl className="card__facts">
          <dt>{t('viewer.card.origin')}</dt>
          <dd>{t(`viewer.card.tier.${info.provenanceTier}`)}</dd>
          <dt>{t('viewer.card.status')}</dt>
          <dd>{t(`viewer.card.status.${info.contentStatus}`)}</dd>
          <dt>{t('viewer.card.voxel')}</dt>
          <dd>
            {voxel} {t('units.mm')}
          </dd>
          <dt>{t('viewer.card.meshError')}</dt>
          <dd>
            {structure.measurable === false
              ? t('viewer.card.meshErrorDisplay', { value: formatMillimetres(info.shownErrorMm, numerals) })
              : t('viewer.card.meshErrorValue', {
                  value: formatMillimetres(info.shownErrorMm, numerals),
                  limit: formatMillimetres(info.meshErrorLimitMm, numerals),
                })}
          </dd>
          <dt>{t('viewer.specimenSelect')}</dt>
          <dd>
            {content.specimenId}
            {' · '}
            {t(content.side ? `viewer.side.${content.side}` : 'viewer.side.unknown')}
          </dd>
        </dl>
      ) : (
        <p className="note">{t('viewer.card.synthetic')}</p>
      )}
    </section>
  );
}
