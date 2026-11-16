import { useEffect, useRef, useState } from 'react';
import { Vector3 } from 'three';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/en';
import { formatMillimetres, formatVoxelSize } from '../measure/format';
import { distance, type Vec3 } from '../measure/geometry';
import { minSurfaceDistance } from '../measure/surfaceDistance';
import type { SceneContent } from '../viewer/content';
import { displayName, latinLine } from '../viewer/names';
import { ViewerCore } from '../viewer/ViewerCore';

type Mode = 'p2p' | 's2s';

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
  const coreRef = useRef<ViewerCore | null>(null);
  const [failed, setFailed] = useState(false);
  const [mode, setMode] = useState<Mode>('p2p');
  const [points, setPoints] = useState<readonly Vec3[]>([]);
  const [pair, setPair] = useState<readonly [string, string]>(() => [
    content.structures[0]?.id ?? '',
    content.structures[1]?.id ?? content.structures[0]?.id ?? '',
  ]);
  const [surfaceResult, setSurfaceResult] = useState<Measurement | null>(null);
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
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
    core.onPick((pick) => setPoints((prev) => (prev.length >= 2 ? [pick.point] : [...prev, pick.point])));
    return () => {
      core.dispose();
      coreRef.current = null;
    };
  }, [content]);

  useEffect(() => {
    if (mode === 'p2p') coreRef.current?.showMeasurement(points);
  }, [mode, points]);

  const pointResult: Measurement | null =
    points[0] && points[1]
      ? { value: distance(points[0], points[1]), methodKey: 'viewer.measure.method.p2p' }
      : null;
  const result = mode === 'p2p' ? pointResult : surfaceResult;

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
  }

  function changeOpacity(id: string, value: number): void {
    setOpacity({ ...opacity, [id]: value });
    coreRef.current?.setOpacity(id, value);
  }

  return (
    <>
      <div className="viewer__stage">
        <div ref={hostRef} className="viewer__canvas" />
        <div className="badges">
          {content.synthetic && <div className="badge badge--synthetic">{t('viewer.phantomBadge')}</div>}
          {content.draft && <div className="badge badge--draft">{t('viewer.draftBadge')}</div>}
        </div>
        {failed && <div className="viewer__error">{t('viewer.webglError')}</div>}
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
                  <label className="choice">
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
                    <span className="structure-name">
                      <span>{name}</span>
                      {latin && (
                        <span className="structure-name__latin" lang="la" dir="ltr">
                          {latin}
                        </span>
                      )}
                    </span>
                  </label>
                  <div className="structures__row">
                    <input
                      type="range"
                      min={0.1}
                      max={1}
                      step={0.05}
                      value={opacity[s.id] ?? 1}
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
          <button type="button" onClick={() => isolate(null)}>
            {t('viewer.showAll')}
          </button>
        </section>
        <section>
          <h2>{t('viewer.measure.title')}</h2>
          <div className="segmented" role="group" aria-label={t('viewer.measure.title')}>
            <button type="button" aria-pressed={mode === 'p2p'} onClick={() => changeMode('p2p')}>
              {t('viewer.measure.pointToPoint')}
            </button>
            <button type="button" aria-pressed={mode === 's2s'} onClick={() => changeMode('s2s')}>
              {t('viewer.measure.surfaceToSurface')}
            </button>
          </div>
          {mode === 'p2p' ? (
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
                  {content.structures.map((s) => (
                    <option key={s.id} value={s.id}>
                      {displayName(s.names, locale)}
                    </option>
                  ))}
                </select>
              ))}
            </div>
          )}
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
          ) : (
            <p className="note">{t('viewer.measure.none')}</p>
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
