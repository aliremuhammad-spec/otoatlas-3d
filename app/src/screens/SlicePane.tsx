import { useEffect, useMemo, useRef, useState } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import { formatMillimetres, formatVoxelSize } from '../measure/format';
import type { SceneContent } from '../viewer/content';
import { placeLabels } from '../viewer/labels';
import { loadScan } from '../viewer/loadPackage';
import { displayName } from '../viewer/names';
import {
  edgeLetters,
  insideSection,
  meshSection,
  sectionAnchor,
  sectionBoxArea,
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
  selected: string | null;
  labelsOn: boolean;
  onSelect: (id: string | null) => void;
  onClose: () => void;
}

interface Placement {
  left: number;
  top: number;
  scale: number;
  drawH: number;
  u0: number;
  v0: number;
  dpr: number;
}

const AXES: readonly Axis[] = ['z', 'y', 'x'];

/** The specimen's own scan, one slice at a time, with each visible structure's outline drawn on it. */
export function SlicePane({ content, core, hidden, selected, labelsOn, onSelect, onClose }: Props) {
  const { t, numerals, locale } = useI18n();
  const placementRef = useRef<Placement | null>(null);
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

  // Where each shown structure crosses this slice, in in-plane millimetres.
  const sections = useMemo(() => {
    const out = new Map<string, Float32Array>();
    for (const s of content.structures) {
      if (hidden.has(s.id)) continue;
      const pos = s.geometry.getAttribute('position');
      if (!pos) continue;
      const idx = s.geometry.getIndex();
      const segs = meshSection(pos.array, idx ? idx.array : null, axis, position, s.position);
      if (segs.length > 0) out.set(s.id, segs);
    }
    return out;
  }, [content.structures, hidden, axis, position]);

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

    // Outlines: where each shown structure crosses this plane. With a structure selected,
    // its outline is drawn bold and the others faint.
    const u0 = (grid.originMm[h] ?? 0) - sh / 2;
    const v0 = (grid.originMm[v] ?? 0) - sv / 2;
    placementRef.current = { left, top, scale, drawH, u0, v0, dpr };
    const toX = (u: number) => left + (u - u0) * scale;
    const toY = (w: number) => top + drawH - (w - v0) * scale;
    const colourOf = new Map(content.structures.map((s) => [s.id, `#${s.color.toString(16).padStart(6, '0')}`]));
    const order = [...sections.keys()].sort((a, b) => (a === selected ? 1 : b === selected ? -1 : 0));
    for (const id of order) {
      const segs = sections.get(id);
      if (!segs) continue;
      const isSelected = id === selected;
      ctx.globalAlpha = selected && !isSelected ? 0.35 : 1;
      ctx.lineWidth = (isSelected ? 3 : 1.5) * dpr;
      ctx.strokeStyle = colourOf.get(id) ?? '#fff';
      ctx.beginPath();
      for (let i = 0; i < segs.length; i += 4) {
        ctx.moveTo(toX(segs[i] ?? 0), toY(segs[i + 1] ?? 0));
        ctx.lineTo(toX(segs[i + 2] ?? 0), toY(segs[i + 3] ?? 0));
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Names beside their outlines, joined by a leader line, pushed apart when they overlap.
    const fontPx = Math.round(12 * dpr);
    ctx.font = `${fontPx}px "IBM Plex Sans Arabic", system-ui, sans-serif`;
    ctx.direction = locale === 'ar' ? 'rtl' : 'ltr';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    if (labelsOn) {
      const pad = 4 * dpr;
      const anchors = [...sections.entries()].flatMap(([id, segs]) => {
        const s = content.structures.find((x) => x.id === id);
        const a = sectionAnchor(segs);
        if (!s || !a) return [];
        const text = displayName(s.names, locale);
        const w = ctx.measureText(text).width + 2 * pad;
        return [{ id, text, x: toX(a[0]), y: toY(a[1]), w, h: fontPx + 2 * pad }];
      });
      const boxes = placeLabels(anchors, { x: canvas.width / 2, y: canvas.height / 2 });
      for (const a of anchors) {
        const b = boxes.get(a.id);
        if (!b) continue;
        const dim = selected !== null && a.id !== selected;
        ctx.globalAlpha = dim ? 0.5 : 1;
        ctx.strokeStyle = 'rgba(238, 243, 245, 0.75)';
        ctx.lineWidth = dpr;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x + b.w / 2 < a.x ? b.x + b.w : b.x, b.y + b.h / 2);
        ctx.stroke();
        ctx.fillStyle = 'rgba(14, 20, 24, 0.82)';
        ctx.fillRect(b.x, b.y, b.w, b.h);
        ctx.fillStyle = colourOf.get(a.id) ?? '#fff';
        ctx.fillRect(b.x, b.y, 3 * dpr, b.h);
        ctx.fillStyle = '#eef3f5';
        // Arabic is drawn right to left from the box's right edge.
        if (locale === 'ar') {
          ctx.textAlign = 'right';
          ctx.fillText(a.text, b.x + b.w - pad, b.y + b.h / 2);
          ctx.textAlign = 'left';
        } else {
          ctx.fillText(a.text, b.x + pad + 2 * dpr, b.y + b.h / 2);
        }
      }
      ctx.globalAlpha = 1;
    }

    // Scanner-axis letters on the four edges of the image.
    const [l, r, bottom, topLetter] = edgeLetters(axis);
    ctx.direction = 'ltr';
    ctx.font = `600 ${Math.round(13 * dpr)}px system-ui, sans-serif`;
    ctx.fillStyle = '#5fd0c5';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText(l, left + 6 * dpr, top + drawH / 2);
    ctx.textAlign = 'right';
    ctx.fillText(r, left + drawW - 6 * dpr, top + drawH / 2);
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(topLetter, left + drawW / 2, top + 6 * dpr);
    ctx.textBaseline = 'bottom';
    ctx.fillText(bottom, left + drawW / 2, top + drawH - 6 * dpr);
  }, [data, grid, axis, index, sections, selected, labelsOn, locale, content.structures]);

  if (!scan || !grid) return null;
  const count = sliceCount(grid, axis);
  const voxel = [...new Set(scan.spacingMm.map((s) => formatVoxelSize(s, numerals)))].join(' × ');

  // A tap on the slice selects the smallest outline around the tapped point.
  function onCanvasClick(e: React.MouseEvent<HTMLCanvasElement>): void {
    const p = placementRef.current;
    const canvas = canvasRef.current;
    if (!p || !canvas) return;
    const box = canvas.getBoundingClientRect();
    const x = (e.clientX - box.left) * p.dpr;
    const y = (e.clientY - box.top) * p.dpr;
    const u = p.u0 + (x - p.left) / p.scale;
    const w = p.v0 + (p.top + p.drawH - y) / p.scale;
    let best: string | null = null;
    let bestArea = Infinity;
    for (const [id, segs] of sections) {
      if (!insideSection(segs, u, w)) continue;
      const area = sectionBoxArea(segs);
      if (area < bestArea) {
        bestArea = area;
        best = id;
      }
    }
    onSelect(best);
  }

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
        <canvas
          ref={canvasRef}
          className="slices__canvas"
          onClick={onCanvasClick}
          aria-label={t('viewer.slices.tapHint')}
        />
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
      <p className="note">{t('viewer.slices.tapHint')}</p>
    </section>
  );
}
