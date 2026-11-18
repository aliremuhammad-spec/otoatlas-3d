import { useEffect, useMemo, useRef, useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { formatMillimetres, formatVoxelSize } from '../measure/format';
import type { SceneContent } from '../viewer/content';
import { loadScan } from '../viewer/loadPackage';
import {
  meshSection,
  planeAxes,
  sliceCount,
  sliceImage,
  slicePosition,
  type Axis,
  type ScanGrid,
} from '../viewer/slice';
import type { ViewerCore } from '../viewer/ViewerCore';

interface Props {
  content: SceneContent;
  core: ViewerCore | null;
  hidden: ReadonlySet<string>;
  onClose: () => void;
}

const AXES: readonly Axis[] = ['z', 'y', 'x'];

/** The specimen's own scan, one slice at a time, with each visible structure's outline drawn on it. */
export function SlicePane({ content, core, hidden, onClose }: Props) {
  const { t, numerals } = useI18n();
  const scan = content.scan;
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [data, setData] = useState<Uint8Array | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [axis, setAxis] = useState<Axis>('z');
  const grid: ScanGrid | null = useMemo(
    () => (scan ? { shape: scan.shape, spacingMm: scan.spacingMm, originMm: scan.originMm } : null),
    [scan],
  );
  const [index, setIndex] = useState(() => (grid ? Math.floor(sliceCount(grid, 'z') / 2) : 0));

  useEffect(() => {
    if (!scan) return undefined;
    let cancelled = false;
    setStatus('loading');
    loadScan(scan.url, scan.shape).then(
      (bytes) => {
        if (cancelled) return;
        setData(bytes);
        setStatus('ready');
      },
      () => {
        if (!cancelled) setStatus('error');
      },
    );
    return () => {
      cancelled = true;
    };
  }, [scan]);

  const position = grid ? slicePosition(grid, axis, index) : 0;

  // Show the cutting plane in the 3D view while the pane is open.
  useEffect(() => {
    if (!core || !grid) return undefined;
    const half = grid.spacingMm.map((s) => s / 2);
    const min = [0, 1, 2].map((i) => (grid.originMm[i] ?? 0) - (half[i] ?? 0)) as [number, number, number];
    const max = [0, 1, 2].map(
      (i) => (grid.originMm[i] ?? 0) + ((grid.shape[i] ?? 1) - 1) * (grid.spacingMm[i] ?? 0) + (half[i] ?? 0),
    ) as [number, number, number];
    core.setSlicePlane({ axis, position, min, max });
    return () => core.setSlicePlane(null);
  }, [core, grid, axis, position]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !grid || !data) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const img = sliceImage(data, grid, axis, index);
    const [h, v] = planeAxes(axis);
    const sh = grid.spacingMm[h] ?? 1;
    const sv = grid.spacingMm[v] ?? 1;
    // Fit the slice to the canvas at its true aspect ratio (voxels may not be square).
    const box = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(box.width * dpr);
    canvas.height = Math.round(box.height * dpr);
    const widthMm = img.width * sh;
    const heightMm = img.height * sv;
    const scale = Math.min(canvas.width / widthMm, canvas.height / heightMm);
    const drawW = widthMm * scale;
    const drawH = heightMm * scale;
    const left = (canvas.width - drawW) / 2;
    const top = (canvas.height - drawH) / 2;

    const off = document.createElement('canvas');
    off.width = img.width;
    off.height = img.height;
    const offCtx = off.getContext('2d');
    if (!offCtx) return;
    const rgba = offCtx.createImageData(img.width, img.height);
    for (let i = 0; i < img.pixels.length; i += 1) {
      const g = img.pixels[i] ?? 0;
      rgba.data[4 * i] = g;
      rgba.data[4 * i + 1] = g;
      rgba.data[4 * i + 2] = g;
      rgba.data[4 * i + 3] = 255;
    }
    offCtx.putImageData(rgba, 0, 0);
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(off, left, top, drawW, drawH);

    // Outlines: where each visible structure's mesh crosses this plane.
    const u0 = (grid.originMm[h] ?? 0) - sh / 2;
    const v0 = (grid.originMm[v] ?? 0) - sv / 2;
    const toX = (u: number) => left + (u - u0) * scale;
    const toY = (w: number) => top + drawH - (w - v0) * scale;
    ctx.lineWidth = Math.max(1, 1.5 * dpr);
    for (const s of content.structures) {
      if (hidden.has(s.id)) continue;
      const pos = s.geometry.getAttribute('position');
      if (!pos) continue;
      const idx = s.geometry.getIndex();
      const segs = meshSection(pos.array, idx ? idx.array : null, axis, position, s.position);
      if (segs.length === 0) continue;
      ctx.strokeStyle = `#${s.color.toString(16).padStart(6, '0')}`;
      ctx.beginPath();
      for (let i = 0; i < segs.length; i += 4) {
        ctx.moveTo(toX(segs[i] ?? 0), toY(segs[i + 1] ?? 0));
        ctx.lineTo(toX(segs[i + 2] ?? 0), toY(segs[i + 3] ?? 0));
      }
      ctx.stroke();
    }
  }, [data, grid, axis, index, position, hidden, content.structures]);

  if (!scan || !grid) return null;
  const count = sliceCount(grid, axis);
  const voxel = [...new Set(scan.spacingMm.map((s) => formatVoxelSize(s, numerals)))].join(' × ');

  function changeAxis(next: Axis): void {
    if (!grid) return;
    setAxis(next);
    setIndex(Math.floor(sliceCount(grid, next) / 2));
  }

  return (
    <section className="slices" data-testid="slice-pane" aria-label={t('viewer.slices.title')}>
      <header className="slices__header">
        <div className="segmented" role="group" aria-label={t('viewer.slices.plane')}>
          {AXES.map((a) => (
            <button key={a} type="button" aria-pressed={axis === a} onClick={() => changeAxis(a)}>
              {t(`viewer.slices.plane.${a}`)}
            </button>
          ))}
        </div>
        <button type="button" onClick={onClose} aria-label={t('viewer.card.close')}>
          ×
        </button>
      </header>
      <div className="slices__view">
        <canvas ref={canvasRef} className="slices__canvas" />
        {status !== 'ready' && (
          <div className="slices__message" role="status">
            {t(status === 'loading' ? 'viewer.slices.loading' : 'viewer.slices.error')}
          </div>
        )}
      </div>
      <input
        type="range"
        min={0}
        max={count - 1}
        step={1}
        value={Math.min(index, count - 1)}
        onChange={(e) => setIndex(Number(e.target.value))}
        aria-label={t('viewer.slices.position')}
      />
      <p className="note" dir="auto">
        {t('viewer.slices.where', {
          axis: axis,
          value: formatMillimetres(position, numerals),
          modality: scan.modality,
          voxel,
        })}
      </p>
      <p className="note">{t('viewer.slices.axesNote')}</p>
    </section>
  );
}
