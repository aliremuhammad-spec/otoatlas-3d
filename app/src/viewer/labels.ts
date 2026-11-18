/**
 * Structure labels drawn as HTML over the 3D canvas, each joined to its structure by a
 * leader line. The browser shapes the text, so Arabic and mixed Arabic and Latin names
 * render correctly with no shaping code of our own. Framework-free, like ViewerCore.
 */
import type { Vec3 } from '../measure/geometry';

export interface LabelSpec {
  id: string;
  text: string;
  anchor: Vec3;
}

export interface LabelHost {
  project(point: Vec3): { x: number; y: number } | null;
  viewSize(): { width: number; height: number };
  isVisible(id: string): boolean;
}

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Leader length in CSS pixels before collision pushes a label further out. */
const LEADER_PX = 44;
const PUSH_PX = 10;
const MAX_PUSHES = 14;
const ROW_STEPS = [0, 1, -1, 2, -2, 3, -3] as const;
const SVG_NS = 'http://www.w3.org/2000/svg';

function overlaps(a: Box, b: Box): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
}

/**
 * Places labels: each moves out from its anchor, away from the view centre, and keeps
 * moving outwards while it overlaps a label already placed. Pure, so it can be tested.
 */
export function placeLabels(
  anchors: readonly { id: string; x: number; y: number; w: number; h: number }[],
  centre: { x: number; y: number },
): Map<string, Box> {
  const placed = new Map<string, Box>();
  // Nearest the centre first: they have the least room.
  const order = [...anchors].sort(
    (a, b) => Math.hypot(a.x - centre.x, a.y - centre.y) - Math.hypot(b.x - centre.x, b.y - centre.y),
  );
  for (const a of order) {
    let dx = a.x - centre.x;
    let dy = a.y - centre.y;
    const len = Math.hypot(dx, dy);
    if (len < 1e-6) {
      dx = 1;
      dy = 0;
    } else {
      dx /= len;
      dy /= len;
    }
    let box: Box | null = null;
    let fallback: Box = { x: 0, y: 0, w: a.w, h: a.h };
    // Try further out along the leader, and at each reach a few rows above and below.
    search: for (let push = 0; push <= MAX_PUSHES; push += 1) {
      const reach = LEADER_PX + push * PUSH_PX;
      const px = a.x + dx * reach;
      const py = a.y + dy * reach;
      for (const row of ROW_STEPS) {
        // Grow away from the anchor: to the right of it on the right side, to the left on the left.
        const candidate = { x: dx >= 0 ? px : px - a.w, y: py - a.h / 2 + row * (a.h + 2), w: a.w, h: a.h };
        if (push === 0 && row === 0) fallback = candidate;
        if (![...placed.values()].some((p) => overlaps(p, candidate))) {
          box = candidate;
          break search;
        }
      }
    }
    placed.set(a.id, box ?? fallback);
  }
  return placed;
}

export class LabelLayer {
  private readonly root: HTMLDivElement;
  private readonly svg: SVGSVGElement;
  private readonly items = new Map<string, { spec: LabelSpec; el: HTMLDivElement; line: SVGLineElement }>();
  private enabled = true;

  constructor(
    container: HTMLElement,
    private readonly host: LabelHost,
  ) {
    this.root = document.createElement('div');
    this.root.className = 'labels';
    this.root.setAttribute('aria-hidden', 'true');
    this.svg = document.createElementNS(SVG_NS, 'svg');
    this.svg.setAttribute('class', 'labels__lines');
    this.root.appendChild(this.svg);
    container.appendChild(this.root);
  }

  setLabels(specs: readonly LabelSpec[]): void {
    for (const item of this.items.values()) {
      item.el.remove();
      item.line.remove();
    }
    this.items.clear();
    for (const spec of specs) {
      const el = document.createElement('div');
      el.className = 'labels__label';
      el.dir = 'auto';
      el.textContent = spec.text;
      el.dataset.label = spec.id;
      const line = document.createElementNS(SVG_NS, 'line');
      this.root.appendChild(el);
      this.svg.appendChild(line);
      this.items.set(spec.id, { spec, el, line });
    }
    this.update();
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    this.root.hidden = !enabled;
    this.update();
  }

  update(): void {
    if (!this.enabled) return;
    const { width, height } = this.host.viewSize();
    this.svg.setAttribute('width', String(width));
    this.svg.setAttribute('height', String(height));
    const anchors: { id: string; x: number; y: number; w: number; h: number }[] = [];
    for (const { spec, el, line } of this.items.values()) {
      const p = this.host.isVisible(spec.id) ? this.host.project(spec.anchor) : null;
      const shown = p !== null && p.x >= 0 && p.y >= 0 && p.x <= width && p.y <= height;
      el.hidden = !shown;
      line.style.display = shown ? '' : 'none';
      if (shown) anchors.push({ id: spec.id, x: p.x, y: p.y, w: el.offsetWidth, h: el.offsetHeight });
    }
    const boxes = placeLabels(anchors, { x: width / 2, y: height / 2 });
    for (const a of anchors) {
      const item = this.items.get(a.id);
      const box = boxes.get(a.id);
      if (!item || !box) continue;
      item.el.style.transform = `translate(${Math.round(box.x)}px, ${Math.round(box.y)}px)`;
      // The line ends at the label's near edge, at its middle height.
      const endX = box.x + box.w / 2 < a.x ? box.x + box.w : box.x;
      item.line.setAttribute('x1', String(a.x));
      item.line.setAttribute('y1', String(a.y));
      item.line.setAttribute('x2', String(endX));
      item.line.setAttribute('y2', String(box.y + box.h / 2));
    }
  }

  dispose(): void {
    this.root.remove();
    this.items.clear();
  }
}
