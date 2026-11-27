import { useCallback, useEffect, useRef, useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { loadColourVolume, type ColourSpecimen } from './loadColour';
import { chooseTier, adaptScale, type DeviceProfile, type Quality } from './tier';
import { NoWebGL2Error, VolumeRenderer } from './VolumeRenderer';

function deviceProfile(): DeviceProfile {
  const coarse = typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches;
  return { shortSide: Math.min(window.screen?.width || 1024, window.screen?.height || 1024), coarsePointer: coarse };
}

type Phase =
  | { kind: 'starting' }
  | { kind: 'loading'; step: number; fraction: number }
  | { kind: 'ready' }
  | { kind: 'error' }
  | { kind: 'nowebgl' };

const STEPS = 3;
const STEP_KEYS = ['surgical.step.lighting', 'surgical.step.colour', 'surgical.step.prepare'] as const;

interface Props {
  specimen: ColourSpecimen;
  quality: Quality;
  translucent: boolean;
  cut: number;
}

/** The picture of one specimen: owns the canvas, the renderer, loading and the pointer controls. */
export function SurgicalView({ specimen, quality, translucent, cut }: Props) {
  const { t } = useI18n();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rendererRef = useRef<VolumeRenderer | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: 'starting' });
  const [attempt, setAttempt] = useState(0);
  const [stats, setStats] = useState<{ fps: number; mm: number; scale: number } | null>(null);
  const [reduced, setReduced] = useState(false);
  const normalsFor = useRef<string | null>(null);
  const dirty = useRef(true);
  const scaleRef = useRef(1);
  const ceilingRef = useRef(1);
  const optsRef = useRef({ translucent, cut });
  const tier = chooseTier(specimen.colour, deviceProfile(), quality);
  const tierMm = tier?.volume.spacingMm ?? null;

  useEffect(() => {
    optsRef.current = { translucent, cut };
    dirty.current = true;
  }, [translucent, cut]);

  // One renderer for the lifetime of this view.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    let renderer: VolumeRenderer;
    try {
      renderer = new VolumeRenderer(canvas);
    } catch (e) {
      setPhase({ kind: e instanceof NoWebGL2Error ? 'nowebgl' : 'error' });
      return undefined;
    }
    rendererRef.current = renderer;
    renderer.onContextChange = (lost) => {
      if (!lost) dirty.current = true;
    };
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(() => (dirty.current = true)) : null;
    observer?.observe(canvas);

    let raf = 0;
    let last = 0;
    let frames = 0;
    let acc = 0;
    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      if (!dirty.current || !renderer.ready) {
        last = 0;
        frames = 0;
        acc = 0;
        return;
      }
      dirty.current = false;
      renderer.render({ ...optsRef.current, renderScale: scaleRef.current });
      if (last > 0 && now - last < 100) {
        frames += 1;
        acc += now - last;
        if (frames >= 30) {
          const fps = (frames * 1000) / acc;
          const next = adaptScale(scaleRef.current, fps, ceilingRef.current);
          const changed = next !== scaleRef.current;
          if (next < scaleRef.current) setReduced(true);
          scaleRef.current = next;
          setStats({ fps: Math.round(fps), mm: renderer.voxelMm ?? 0, scale: next });
          frames = 0;
          acc = 0;
          // A new scale takes effect on the next frame, and the view keeps drawing while it adapts.
          if (changed) dirty.current = true;
        }
      }
      last = now;
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      observer?.disconnect();
      renderer.dispose();
      rendererRef.current = null;
      normalsFor.current = null;
    };
  }, []);

  // Load lighting data once per specimen, then the colour tier.
  useEffect(() => {
    const renderer = rendererRef.current;
    if (!renderer || !tier) return undefined;
    let cancelled = false;
    const run = async () => {
      if (normalsFor.current !== specimen.path) {
        const normals = specimen.colour.normals;
        if (!normals) throw new Error('no lighting data');
        setPhase({ kind: 'loading', step: 1, fraction: 0 });
        const data = await loadColourVolume(specimen.path, normals, (p) =>
          !cancelled && setPhase({ kind: 'loading', step: 1, fraction: p.fraction }),
        );
        if (cancelled) return;
        renderer.setNormals(data);
        normalsFor.current = specimen.path;
      }
      setPhase({ kind: 'loading', step: 2, fraction: 0 });
      const colour = await loadColourVolume(specimen.path, tier.volume, (p) =>
        !cancelled && setPhase({ kind: 'loading', step: 2, fraction: p.fraction }),
      );
      if (cancelled) return;
      setPhase({ kind: 'loading', step: 3, fraction: 1 });
      // Let the "preparing" message paint before the upload blocks the thread for a moment.
      await new Promise((resolve) => setTimeout(resolve, 30));
      if (cancelled) return;
      if (Math.max(...colour.dims) > renderer.maxTextureSize) throw new Error('volume larger than the texture limit');
      renderer.setColour(colour);
      if (specimen.frame) renderer.setFrame(specimen.frame.lateral, specimen.frame.superior);
      ceilingRef.current = tier.renderScale;
      scaleRef.current = tier.renderScale;
      setReduced(false);
      setStats(null);
      setPhase({ kind: 'ready' });
      dirty.current = true;
    };
    run().catch(() => {
      if (!cancelled) setPhase({ kind: 'error' });
    });
    return () => {
      cancelled = true;
    };
    // `tier` is derived from the specimen and quality; its spacing identifies it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [specimen, tierMm, attempt]);

  // Pointer controls: one pointer turns, two pinch.
  const pointers = useRef(new Map<number, [number, number]>());
  const pinch = useRef(0);
  const spread = () => {
    const [a, b] = [...pointers.current.values()];
    return a && b ? Math.hypot(a[0] - b[0], a[1] - b[1]) : 0;
  };
  const onPointerDown = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    pointers.current.set(e.pointerId, [e.clientX, e.clientY]);
    if (pointers.current.size === 2) pinch.current = spread();
  }, []);
  const onPointerMove = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    const prev = pointers.current.get(e.pointerId);
    const r = rendererRef.current;
    if (!prev || !r) return;
    if (pointers.current.size === 1) r.rotate(e.clientX - prev[0], e.clientY - prev[1]);
    pointers.current.set(e.pointerId, [e.clientX, e.clientY]);
    if (pointers.current.size === 2) {
      const d = spread();
      if (d > 0 && pinch.current > 0) r.zoom(pinch.current / d);
      pinch.current = d;
    }
    dirty.current = true;
  }, []);
  const onPointerEnd = useCallback((e: React.PointerEvent<HTMLCanvasElement>) => {
    pointers.current.delete(e.pointerId);
  }, []);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      rendererRef.current?.zoom(Math.exp(e.deltaY * 0.001));
      dirty.current = true;
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, []);

  return (
    <div className="surgical__stage" data-testid="surgical-stage" data-phase={phase.kind}>
      <canvas
        ref={canvasRef}
        className="surgical__canvas"
        role="img"
        aria-label={t('surgical.canvasLabel')}
        data-testid="surgical-canvas"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
      />
      {phase.kind === 'loading' && (
        <div className="surgical__overlay" role="status" data-testid="surgical-loading">
          <p>{t('surgical.loading', { mb: Math.round((tier?.volume.bytes ?? 0) / 2 ** 20) })}</p>
          <p>
            {t('surgical.loadingStep', {
              step: phase.step,
              steps: STEPS,
              what: t(STEP_KEYS[phase.step - 1] ?? STEP_KEYS[0]),
            })}
          </p>
          <progress max={1} value={phase.fraction} aria-label={t('surgical.loading', { mb: 0 })} />
        </div>
      )}
      {phase.kind === 'error' && (
        <div className="surgical__overlay" role="alert" data-testid="surgical-error">
          <p>{t('surgical.loadError')}</p>
          <button type="button" className="primary" onClick={() => setAttempt((n) => n + 1)}>
            {t('surgical.retry')}
          </button>
        </div>
      )}
      {phase.kind === 'nowebgl' && (
        <div className="surgical__overlay" role="alert" data-testid="surgical-nowebgl">
          <p>{t('surgical.noWebgl2')}</p>
        </div>
      )}
      {phase.kind === 'ready' && (
        <div className="surgical__hud" aria-live="off" data-testid="surgical-hud">
          <p>{t('surgical.help')}</p>
          {stats && (
            <p>
              {t('surgical.fps', { fps: stats.fps })} · {t('surgical.resolution', { mm: stats.mm, scale: stats.scale })}
            </p>
          )}
          {reduced && <p>{t('surgical.reducedScale')}</p>}
        </div>
      )}
    </div>
  );
}
