import { useEffect, useState } from 'react';
import { Disclaimer } from '../components/Disclaimer';
import { SupervisionCredit } from '../components/SupervisionCredit';
import { useI18n } from '../i18n/I18nProvider';
import { listColourSpecimens, type ColourSpecimen } from '../surgical/loadColour';
import type { StructureState } from '../surgical/lut';
import { SurgicalStructures } from '../surgical/SurgicalStructures';
import { SurgicalView } from '../surgical/SurgicalView';
import type { Quality } from '../surgical/tier';

interface Props {
  onBack: () => void;
}

/**
 * The surgical view: its own screen with its own controls, reached from its own button on the home
 * screen. It shares nothing with the anatomical-model viewer except the packages it reads.
 */
export function SurgicalScreen({ onBack }: Props) {
  const { t } = useI18n();
  const [specimens, setSpecimens] = useState<readonly ColourSpecimen[] | null>(null);
  const [selected, setSelected] = useState<string>('');
  const [quality, setQuality] = useState<Quality>('auto');
  const [translucent, setTranslucent] = useState(false);
  const [cut, setCut] = useState(0);
  const [structureState, setStructureState] = useState<StructureState>({ hidden: new Set(), tinted: false });
  const [labelsReady, setLabelsReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void listColourSpecimens().then((found) => {
      if (cancelled) return;
      setSpecimens(found);
      setSelected(found[0]?.path ?? '');
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const specimen = specimens?.find((s) => s.path === selected) ?? null;
  const tiers = specimen ? [...specimen.colour.tiers].filter((x) => x.onSite) : [];
  const fine = tiers.find((x) => Math.abs(x.spacingMm - 0.15) < 0.01);
  const standard = tiers.find((x) => Math.abs(x.spacingMm - 0.2) < 0.01);

  return (
    <div className="viewer surgical" data-testid="surgical-screen">
      <header className="page__header">
        <button type="button" onClick={onBack}>
          {t('nav.back')}
        </button>
        <h1>{t('surgical.title')}</h1>
        {specimens && specimens.length > 0 && (
          <label className="specimen-select">
            <span>{t('surgical.specimenSelect')}</span>
            <select value={selected} onChange={(e) => {
                setSelected(e.target.value);
                setStructureState({ hidden: new Set(), tinted: false });
                setLabelsReady(false);
              }} data-testid="surgical-specimen-select">
              {specimens.map((s) => (
                <option key={s.path} value={s.path}>
                  {s.id} · {t(s.side ? `surgical.side.${s.side}` : 'surgical.side.unknown')}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>
      <p className="note surgical__badge" data-testid="surgical-badge">
        {t('surgical.badge')}
      </p>
      {specimens === null && (
        <div className="viewer__stage viewer__stage--message" role="status">
          {t('surgical.checking')}
        </div>
      )}
      {specimens !== null && specimens.length === 0 && (
        <div className="viewer__stage viewer__stage--message" role="status" data-testid="surgical-empty">
          {t('surgical.noSpecimens')}
        </div>
      )}
      {specimen && (
        <>
          <div className="surgical__controls" role="group" aria-label={t('surgical.controls')}>
            <label>
              <span>{t('surgical.mode')}</span>
              <select
                value={translucent ? 'translucent' : 'opaque'}
                onChange={(e) => setTranslucent(e.target.value === 'translucent')}
                data-testid="surgical-mode"
              >
                <option value="opaque">{t('surgical.mode.opaque')}</option>
                <option value="translucent">{t('surgical.mode.translucent')}</option>
              </select>
            </label>
            <label>
              <span>{t('surgical.quality')}</span>
              <select value={quality} onChange={(e) => setQuality(e.target.value as Quality)} data-testid="surgical-quality">
                <option value="auto">{t('surgical.quality.auto')}</option>
                {fine && <option value="fine">{t('surgical.quality.fine', { mm: fine.spacingMm })}</option>}
                {standard && <option value="standard">{t('surgical.quality.standard', { mm: standard.spacingMm })}</option>}
              </select>
            </label>
            <label>
              <span>{t('surgical.cut')}</span>
              <input
                type="range"
                min={0}
                max={0.6}
                step={0.02}
                value={cut}
                onChange={(e) => setCut(Number(e.target.value))}
                data-testid="surgical-cut"
              />
            </label>
          </div>
          <SurgicalView
            key={specimen.path}
            specimen={specimen}
            quality={quality}
            translucent={translucent}
            cut={cut}
            structures={structureState}
            onLabels={setLabelsReady}
          />
          {labelsReady && specimen.structures.length > 0 && (
            <SurgicalStructures structures={specimen.structures} state={structureState} onChange={setStructureState} />
          )}
          {specimen.draft && <p className="note">{t('surgical.draft')}</p>}
        </>
      )}
      <Disclaimer />
      <footer className="page__footer">
        <SupervisionCredit variant="footer" />
      </footer>
    </div>
  );
}
