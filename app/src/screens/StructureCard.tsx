import { useI18n } from '../i18n/I18nProvider';
import { localizeDigits } from '../i18n/numerals';
import { estimateCdlOrganOfCorti } from '../measure/cdl';
import { formatMillilitres, formatMillimetres, formatVoxelSize } from '../measure/format';
import type { SceneContent, SceneStructure } from '../viewer/content';
import { MEASUREMENT_IDS, type MeasurementId } from '../viewer/manifest';
import { pick, topicsForStructure } from '../topics/topics';
import { displayName, latinLine } from '../viewer/names';

interface Props {
  structure: SceneStructure;
  content: SceneContent;
  onClose: () => void;
  /** Opens one of the chapter topics about this structure. */
  onOpenTopic?: (id: string) => void;
}

function MeasurementRow({ id, value, unit }: { id: string; value: number; unit: 'mm' | 'mL' }) {
  const { t, numerals } = useI18n();
  if (!(MEASUREMENT_IDS as readonly string[]).includes(id)) return null;
  return (
    <>
      <dt>{t(`viewer.measurement.${id as MeasurementId}`)}</dt>
      <dd>
        {unit === 'mm' ? formatMillimetres(value, numerals) : formatMillilitres(value, numerals)}{' '}
        {t(unit === 'mm' ? 'units.mm' : 'units.ml')}
      </dd>
    </>
  );
}

/** Cochlear duct length worked out from A with the default formula; shown as an estimate with its source. */
function CdlEstimateRow({ aMm }: { aMm: number }) {
  const { t, numerals } = useI18n();
  return (
    <>
      <dt>{t('viewer.measurement.cdl_estimate')}</dt>
      <dd data-testid="cdl-estimate">
        ≈ {formatMillimetres(estimateCdlOrganOfCorti(aMm), numerals)} {t('units.mm')}
        <span className="card__method">{t('viewer.measurement.cdl_method')}</span>
      </dd>
    </>
  );
}

/** Names of reviewers as written in each language; others are shown as recorded. */
const REVIEWER_NAMES: Readonly<Record<string, { ar: string }>> = {
  'Dr. Ali R. Muhammad': { ar: 'د. علي ر. محمد' },
};

function reviewerName(name: string, locale: string): string {
  return locale === 'ar' ? (REVIEWER_NAMES[name]?.ar ?? name) : name;
}

/** Facts about one structure: its names, where its geometry comes from, and how accurate the mesh is. */
export function StructureCard({ structure, content, onClose, onOpenTopic }: Props) {
  const { t, numerals, locale } = useI18n();
  const name = displayName(structure.names, locale);
  const latin = latinLine(structure.names, locale);
  const other = locale === 'ar' ? structure.names.en : structure.names.ar;
  const info = structure.info;
  // A part also reads its whole structure's topics (the mastoid segment, the facial nerve's).
  const topics = onOpenTopic
    ? [...topicsForStructure(structure.id), ...(structure.group ? topicsForStructure(structure.group.id) : [])].filter(
        (topic, i, all) => all.findIndex((x) => x.id === topic.id) === i,
      )
    : [];
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
      {topics.length > 0 && onOpenTopic && (
        <nav className="card__topics" aria-label={t('topics.related')}>
          <h3>{t('topics.related')}</h3>
          <ul>
            {topics.map((topic) => (
              <li key={topic.id}>
                <button type="button" className="link" onClick={() => onOpenTopic(topic.id)}>
                  {pick(topic.title, locale)}
                </button>
              </li>
            ))}
          </ul>
        </nav>
      )}
      {info ? (
        <dl className="card__facts">
          <dt>{t('viewer.card.origin')}</dt>
          <dd>{t(`viewer.card.tier.${info.provenanceTier}`)}</dd>
          <dt>{t('viewer.card.status')}</dt>
          <dd>{t(`viewer.card.status.${info.contentStatus}`)}</dd>
          {/* A schematic shape has no source voxels and no accuracy to report. */}
          {info.provenanceTier !== 'schematic' && (
            <>
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
            </>
          )}
          {info.computedPart && info.provenanceTier !== 'schematic' && (
            <>
              <dt>{t('viewer.card.division')}</dt>
              <dd>
                {info.divisionReview
                  ? t('viewer.card.division.reviewed', {
                      by: reviewerName(info.divisionReview.by, locale),
                      on: localizeDigits(info.divisionReview.on, numerals),
                    })
                  : t('viewer.card.division.computed')}
              </dd>
            </>
          )}
          {(content.measurements ?? [])
            .filter((m) => m.structures.includes(structure.id))
            .map((m) => (
              <MeasurementRow key={m.id} id={m.id} value={m.value} unit={m.unit} />
            ))}
          {(content.measurements ?? [])
            .filter((m) => m.id === 'cochlear_a_value' && m.structures.includes(structure.id))
            .map((m) => (
              <CdlEstimateRow key="cdl" aMm={m.value} />
            ))}
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
