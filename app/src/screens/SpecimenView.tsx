import { useEffect, useRef, useState } from 'react';
import { Vector3 } from 'three';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/en';
import { formatMillimetres, formatVoxelSize } from '../measure/format';
import { distance, type Vec3 } from '../measure/geometry';
import { minSurfaceDistance } from '../measure/surfaceDistance';
import type { SceneContent } from '../viewer/content';
import { LabelLayer } from '../viewer/labels';
import { displayName, latinLine } from '../viewer/names';
import { ViewerCore } from '../viewer/ViewerCore';
import { SlicePane } from './SlicePane';
import { StructureCard } from './StructureCard';

type Mode = 'explore' | 'p2p' | 's2s';

interface Measurement {
  value: number;
  methodKey: MessageKey;
}

interface Props {
  content: SceneContent;
}

/** The 3D stage and its side panel for one specimen. Remount it (by key) to switch specimen. */
export function SpecimenView({ content }: Props) {
  const { t, numerals, locale } = useI18n();
  const hostRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const coreRef = useRef<ViewerCore | null>(null);
  const labelsRef = useRef<LabelLayer | null>(null);
  const [failed, setFailed] = useState(false);
  const [lost, setLost] = useState(false);
  const [mode, setMode] = useState<Mode>('explore');
  const modeRef = useRef<Mode>('explore');
  const [selected, setSelected] = useState<string | null>(null);
  const [labelsOn, setLabelsOn] = useState(true);
  const viewRef = useRef<HTMLDivElement>(null);
  const [core, setCore] = useState<ViewerCore | null>(null);
  const [slicesOpen, setSlicesOpen] = useState(false);
  const [points, setPoints] = useState<readonly Vec3[]>([]);
  const measurable = content.structures.filter((s) => s.measurable !== false);
  const [pair, setPair] = useState<readonly [string, string]>(() => [
    measurable[0]?.id ?? '',
    measurable[1]?.id ?? measurable[0]?.id ?? '',
  ]);
  const [surfaceResult, setSurfaceResult] = useState<Measurement | null>(null);
  const [hidden, setHidden] = useState<ReadonlySet<string>>(
    () => new Set(content.structures.filter((s) => s.defaultVisible === false).map((s) => s.id)),
  );
  const [opacity, setOpacity] = useState<Readonly<Record<string, number>>>({});

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    let core: ViewerCore;
    try {
      core = new ViewerCore(host, content);
    } catch {
      setFailed(true);
      return undefined;
    }
    coreRef.current = core;
    setCore(core);
    core.onContextLost(() => setLost(true));
    core.onPick((pick) => {
      if (modeRef.current === 'explore') select(pick.structureId);
      else if (modeRef.current === 'p2p') setPoints((prev) => (prev.length >= 2 ? [pick.point] : [...prev, pick.point]));
    });
    const view = viewRef.current;
    const layer = view ? new LabelLayer(view, core) : null;
    labelsRef.current = layer;
    const unsubscribe = layer ? core.onRender(() => layer.update()) : () => undefined;
    return () => {
      unsubscribe();
      layer?.dispose();
      labelsRef.current = null;
      core.dispose();
      coreRef.current = null;
      setCore(null);
    };
  }, [content]);

  // Label text follows the interface language; anchors are computed once per specimen.
  useEffect(() => {
    const core = coreRef.current;
    const layer = labelsRef.current;
    if (!core || !layer) return;
    layer.setLabels(
      content.structures.flatMap((s) => {
        const anchor = core.anchorOf(s.id);
        return anchor ? [{ id: s.id, text: displayName(s.names, locale), anchor }] : [];
      }),
    );
  }, [content, locale]);

  useEffect(() => {
    labelsRef.current?.setEnabled(labelsOn);
  }, [labelsOn]);

  function select(id: string | null): void {
    setSelected(id);
    coreRef.current?.setHighlight(id);
  }

  useEffect(() => {
    if (mode === 'p2p') coreRef.current?.showMeasurement(points);
  }, [mode, points]);

  const pointResult: Measurement | null =
    points[0] && points[1]
      ? { value: distance(points[0], points[1]), methodKey: 'viewer.measure.method.p2p' }
      : null;
  const result = mode === 'p2p' ? pointResult : mode === 's2s' ? surfaceResult : null;
  const selectedStructure = content.structures.find((s) => s.id === selected) ?? null;

  function measureSurfaces(a: string, b: string): void {
    const core = coreRef.current;
    const ga = core?.getGeometry(a);
    const gb = core?.getGeometry(b);
    if (!core || !ga || !gb || a === b) {
      setSurfaceResult(null);
      core?.showMeasurement([]);
      return;
    }
    const bToA = ga.toSpecimen.clone().invert().multiply(gb.toSpecimen);
    const r = minSurfaceDistance(ga.geometry, gb.geometry, bToA);
    if (!r) {
      setSurfaceResult(null);
      return;
    }
    const toSpecimen = (p: Vec3): Vec3 => {
      const v = new Vector3(...p).applyMatrix4(ga.toSpecimen);
      return [v.x, v.y, v.z];
    };
    core.showMeasurement([toSpecimen(r.pointOnA), toSpecimen(r.pointOnB)]);
    setSurfaceResult({ value: r.distance, methodKey: 'viewer.measure.method.s2s' });
  }

  function changeMode(next: Mode): void {
    setMode(next);
    modeRef.current = next;
    setPoints([]);
    setSurfaceResult(null);
    coreRef.current?.showMeasurement([]);
    if (next === 's2s') measureSurfaces(pair[0], pair[1]);
  }

  function changePair(index: 0 | 1, id: string): void {
    const next: readonly [string, string] = index === 0 ? [id, pair[1]] : [pair[0], id];
    setPair(next);
    measureSurfaces(next[0], next[1]);
  }

  function clear(): void {
    setPoints([]);
    setSurfaceResult(null);
    coreRef.current?.showMeasurement([]);
  }

  function toggleVisible(id: string): void {
    const next = new Set(hidden);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setHidden(next);
    coreRef.current?.setVisible(id, !next.has(id));
  }

  function isolate(id: string | null): void {
    const next = new Set(id ? content.structures.filter((s) => s.id !== id).map((s) => s.id) : []);
    setHidden(next);
    for (const s of content.structures) coreRef.current?.setVisible(s.id, !next.has(s.id));
    coreRef.current?.frameOn(id ? [id] : null);
  }

  function changeOpacity(id: string, value: number): void {
    setOpacity({ ...opacity, [id]: value });
    coreRef.current?.setOpacity(id, value);
  }

  return (
    <>
      <div className={`viewer__stage${slicesOpen ? ' viewer__stage--split' : ''}`} ref={stageRef}>
        <div ref={viewRef} className="viewer__view">
          <div ref={hostRef} className="viewer__canvas" />
        </div>
        {slicesOpen && (
          <SlicePane
            content={content}
            core={core}
            hidden={hidden}
            selected={selected}
            labelsOn={labelsOn}
            onSelect={select}
            onClose={() => setSlicesOpen(false)}
          />
        )}
        <div className="badges">
          {content.synthetic && <div className="badge badge--synthetic">{t('viewer.phantomBadge')}</div>}
          {content.draft && <div className="badge badge--draft">{t('viewer.draftBadge')}</div>}
        </div>
        {failed && <div className="viewer__error">{t('viewer.webglError')}</div>}
        {lost && (
          <div className="viewer__error" role="alert">
            <p>{t('viewer.contextLost')}</p>
            <button type="button" onClick={() => window.location.reload()}>
              {t('viewer.reload')}
            </button>
          </div>
        )}
        {selectedStructure && (
          <StructureCard structure={selectedStructure} content={content} onClose={() => select(null)} />
        )}
      </div>
      <aside className="viewer__panel">
        <section>
          <h2>{t('viewer.structures')}</h2>
          <ul className="structures">
            {content.structures.map((s) => {
              const name = displayName(s.names, locale);
              const latin = latinLine(s.names, locale);
              return (
                <li key={s.id} data-structure={s.id}>
                  <div className="choice">
                    <input
                      type="checkbox"
                      checked={!hidden.has(s.id)}
                      onChange={() => toggleVisible(s.id)}
                      aria-label={`${t('viewer.show')}: ${name}`}
                    />
                    <span
                      className="swatch"
                      style={{ background: `#${s.color.toString(16).padStart(6, '0')}` }}
                    />
                    <button
                      type="button"
                      className="structure-name"
                      aria-pressed={selected === s.id}
                      onClick={() => select(selected === s.id ? null : s.id)}
                    >
                      <span>{name}</span>
                      {latin && (
                        <span className="structure-name__latin" lang="la" dir="ltr">
                          {latin}
                        </span>
                      )}
                      {s.measurable === false && (
                        <span className="structure-name__note">{t('viewer.displayOnly')}</span>
                      )}
                    </button>
                  </div>
                  <div className="structures__row">
                    <input
                      type="range"
                      min={0.1}
                      max={1}
                      step={0.05}
                      value={opacity[s.id] ?? s.defaultOpacity ?? 1}
                      onChange={(e) => changeOpacity(s.id, Number(e.target.value))}
                      aria-label={`${t('viewer.opacity')}: ${name}`}
                    />
                    <button type="button" onClick={() => isolate(s.id)}>
                      {t('viewer.isolate')}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="structures__actions">
            <button type="button" onClick={() => isolate(null)}>
              {t('viewer.showAll')}
            </button>
            <label className="choice">
              <input type="checkbox" checked={labelsOn} onChange={() => setLabelsOn(!labelsOn)} />
              <span>{t('viewer.labels')}</span>
            </label>
          </div>
          {!selectedStructure && <p className="note">{t('viewer.card.hint')}</p>}
        </section>
        <section>
          <h2>{t('viewer.slices.title')}</h2>
          {content.scan ? (
            <button type="button" aria-pressed={slicesOpen} onClick={() => setSlicesOpen(!slicesOpen)}>
              {t('viewer.slices.open')}
            </button>
          ) : (
            <p className="note">{t('viewer.slices.none')}</p>
          )}
        </section>
        <section className="panel__tools">
          <h2>{t('viewer.tools')}</h2>
          <div className="segmented" role="group" aria-label={t('viewer.tools')}>
            <button type="button" aria-pressed={mode === 'explore'} onClick={() => changeMode('explore')}>
              {t('viewer.mode.explore')}
            </button>
            <button type="button" aria-pressed={mode === 'p2p'} onClick={() => changeMode('p2p')}>
              {t('viewer.measure.pointToPoint')}
            </button>
            <button type="button" aria-pressed={mode === 's2s'} onClick={() => changeMode('s2s')}>
              {t('viewer.measure.surfaceToSurface')}
            </button>
          </div>
          {result ? (
            <dl className="result" data-testid="measurement-result">
              <dt>{t('viewer.measure.distance')}</dt>
              <dd className="result__value">
                {formatMillimetres(result.value, numerals)} {t('units.mm')}
              </dd>
              <dt>{t('viewer.measure.method')}</dt>
              <dd>{t(result.methodKey)}</dd>
              <dd>{t('viewer.specimen', { id: content.specimenId })}</dd>
              {content.sourceVoxelMm !== null && (
                <dd>
                  {t('viewer.measure.sourceVoxel', {
                    size: formatVoxelSize(content.sourceVoxelMm, numerals),
                  })}
                </dd>
              )}
            </dl>
          ) : mode === 'explore' ? null : (
            <p className="note">{t('viewer.measure.none')}</p>
          )}
          {mode === 'explore' ? null : mode === 'p2p' ? (
            <p className="note">{t('viewer.measure.hintPoints')}</p>
          ) : (
            <div className="pair">
              <p className="note">{t('viewer.measure.hintSurfaces')}</p>
              {([0, 1] as const).map((i) => (
                <select
                  key={i}
                  value={pair[i]}
                  onChange={(e) => changePair(i, e.target.value)}
                  aria-label={t('viewer.structures')}
                >
                  {measurable.map((s) => (
                    <option key={s.id} value={s.id}>
                      {displayName(s.names, locale)}
                    </option>
                  ))}
                </select>
              ))}
            </div>
          )}
          <button type="button" onClick={clear}>
            {t('viewer.measure.clear')}
          </button>
        </section>
        {content.attribution && (
          <p className="note" dir="auto" data-testid="specimen-attribution">
            {t('viewer.dataSource', {
              doi: content.attribution.dataDoi,
              license: content.attribution.license,
            })}
          </p>
        )}
      </aside>
    </>
  );
}
