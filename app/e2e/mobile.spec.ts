import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

/**
 * Every viewer feature driven by touch on phone and tablet screens, with the synthetic
 * package (malleus ellipsoid and scala tympani sphere, 2.50 mm apart).
 */
const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures', 'content');

async function serveFixtureContent(page: Page): Promise<void> {
  await page.route('**/content/**', async (route) => {
    const relative = new URL(route.request().url()).pathname.split('/content/')[1] ?? '';
    try {
      await route.fulfill({ body: await readFile(path.join(FIXTURES, relative)) });
    } catch {
      await route.fulfill({ status: 404, body: 'not found' });
    }
  });
}

/** Screen points of the label anchors (points on each structure's surface), by structure id. */
async function anchors(page: Page): Promise<Record<string, { x: number; y: number }>> {
  const view = await page.locator('.viewer__view').boundingBox();
  if (!view) throw new Error('no 3D view');
  const ids = await page.locator('.labels__label').evaluateAll((ls) => ls.map((l) => (l as HTMLElement).dataset.label ?? ''));
  const ends = await page
    .locator('.labels__lines line')
    .evaluateAll((ls) => ls.map((l) => [Number(l.getAttribute('x1')), Number(l.getAttribute('y1'))] as const));
  return Object.fromEntries(ids.map((id, i) => [id, { x: view.x + (ends[i]?.[0] ?? 0), y: view.y + (ends[i]?.[1] ?? 0) }]));
}

function pt<T>(value: T | null | undefined, what: string): T {
  if (value === null || value === undefined) throw new Error(`missing ${what}`);
  return value;
}

async function noSidewaysScroll(page: Page): Promise<void> {
  const [scroll, client] = await page.evaluate(() => [
    document.documentElement.scrollWidth,
    document.documentElement.clientWidth,
  ]);
  expect(scroll).toBeLessThanOrEqual(client);
}

const SCREENS = {
  phone: { width: 390, height: 844 },
  'phone landscape': { width: 844, height: 390 },
  'tablet portrait': { width: 820, height: 1180 },
  'tablet landscape': { width: 1180, height: 820 },
} as const;

for (const [name, viewport] of Object.entries(SCREENS)) {
  test.describe(`touch, ${name}`, () => {
    test.use({ viewport, isMobile: true, hasTouch: true, deviceScaleFactor: 2, locale: 'en-US' });

    test('select, card, slices and both measurements work by touch', async ({ page }, testInfo) => {
      const errors: string[] = [];
      page.on('pageerror', (e) => errors.push(String(e)));
      await serveFixtureContent(page);
      await page.goto('/');
      await page.getByRole('button', { name: 'Open the viewer' }).tap({ timeout: 8000 });
      await expect(page.locator('.labels__label[data-label="malleus"]')).toBeVisible();
      await noSidewaysScroll(page);

      // Every label stays inside the 3D view.
      const view = await page.locator('.viewer__view').boundingBox();
      for (const box of await page.locator('.labels__label').evaluateAll((ls) => ls.map((l) => l.getBoundingClientRect().toJSON() as DOMRect))) {
        expect(box.left).toBeGreaterThanOrEqual((view?.x ?? 0) - 1);
        expect(box.right).toBeLessThanOrEqual((view?.x ?? 0) + (view?.width ?? 0) + 1);
      }

      // Tap a structure in the 3D view: its card opens and reads without sideways scrolling.
      const at = await anchors(page);
      await page.touchscreen.tap(pt(at.malleus, 'malleus').x, pt(at.malleus, 'malleus').y);
      const card = page.getByTestId('structure-card');
      await expect(card).toContainText('Malleus');
      expect(await card.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
      await page.screenshot({ path: testInfo.outputPath('card.png') });
      await card.getByRole('button', { name: 'Close' }).tap();
      await expect(card).toHaveCount(0);

      // A card with long measurement names and the duct length estimate still fits.
      await page.locator('[data-structure="scala_tympani"] .structure-name').tap();
      await expect(card.getByTestId('cdl-estimate')).toContainText('33.4 mm');
      await expect(card.getByTestId('cdl-estimate')).toContainText('Alexiades');
      expect(await card.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(true);
      await page.screenshot({ path: testInfo.outputPath('card-cdl.png') });
      await card.getByRole('button', { name: 'Close' }).tap();

      // Opacity and isolate from the panel.
      const row = page.locator('[data-structure="scala_tympani"]');
      await row.getByRole('button', { name: 'Isolate' }).tap();
      await expect(page.locator('[data-structure="malleus"] input[type="checkbox"]')).not.toBeChecked();
      await page.getByRole('button', { name: 'Show all' }).tap();
      await expect(page.locator('[data-structure="malleus"] input[type="checkbox"]')).toBeChecked();

      // Slices: open, tap inside the malleus outline, change plane, close.
      await page.getByRole('button', { name: 'Show scan slices' }).tap();
      const pane = page.getByTestId('slice-pane');
      await expect(pane.getByRole('status')).toHaveCount(0, { timeout: 8000 });
      const paneBox = await pane.boundingBox();
      expect(paneBox?.width ?? 0).toBeGreaterThan(300);
      // Nothing covers the plane buttons.
      await pane.getByRole('button', { name: 'XZ plane' }).tap();
      await expect(pane).toContainText(/y = /);
      await pane.getByRole('button', { name: 'XY plane' }).tap();
      const target = await pane.locator('canvas').evaluate((c: HTMLCanvasElement) => {
        const ctx = c.getContext('2d');
        if (!ctx) return null;
        const { width, height } = c;
        const d = ctx.getImageData(0, 0, width, height).data;
        const isOrange = (i: number) => (d[i] ?? 0) > 200 && (d[i + 1] ?? 0) > 120 && (d[i + 1] ?? 0) < 190 && (d[i + 2] ?? 0) < 60;
        for (let y = Math.floor(height / 2); y < height; y += 1) {
          let lo = -1;
          let hi = -1;
          for (let x = 0; x < width; x += 1) if (isOrange(4 * (y * width + x))) { if (lo < 0) lo = x; hi = x; }
          if (hi - lo > 12) {
            const r = c.getBoundingClientRect();
            return { x: r.left + ((lo + hi) / 2) * (r.width / width), y: r.top + y * (r.height / height) };
          }
        }
        return null;
      });
      expect(target).not.toBeNull();
      const t = pt(target, 'malleus outline');
      await page.touchscreen.tap(t.x, t.y);
      await expect(card).toContainText('Malleus');
      await page.screenshot({ path: testInfo.outputPath('slices.png') });
      await card.getByRole('button', { name: 'Close' }).tap();
      await pane.getByRole('button', { name: 'Close' }).tap();
      await expect(pane).toHaveCount(0);

      // Point to point: two taps on the two structures.
      await page.getByRole('button', { name: 'Point to point' }).tap();
      const again = await anchors(page);
      await page.touchscreen.tap(pt(again.malleus, 'malleus').x, pt(again.malleus, 'malleus').y);
      await page.touchscreen.tap(pt(again.scala_tympani, 'scala_tympani').x, pt(again.scala_tympani, 'scala_tympani').y);
      const result = page.getByTestId('measurement-result');
      await expect(result).toContainText(/\d\.\d\d mm/);

      // Closest surfaces.
      await page.getByRole('button', { name: 'Closest surfaces' }).tap();
      await expect(result).toContainText(/2\.(4[5-9]|5\d) mm/);
      await noSidewaysScroll(page);
      await page.screenshot({ path: testInfo.outputPath('measure.png') });
      expect(errors).toEqual([]);
    });

    test('a drag rotates without selecting', async ({ page }) => {
      await serveFixtureContent(page);
      await page.goto('/');
      await page.getByRole('button', { name: 'Open the viewer' }).tap({ timeout: 8000 });
      await expect(page.locator('.labels__label[data-label="malleus"]')).toBeVisible();
      const at = await anchors(page);
      const cdp = await page.context().newCDPSession(page);
      const touch = (type: string, x: number, y: number) =>
        cdp.send('Input.dispatchTouchEvent', {
          type,
          touchPoints: type === 'touchEnd' ? [] : [{ x, y }],
        });
      await touch('touchStart', pt(at.malleus, 'malleus').x, pt(at.malleus, 'malleus').y);
      for (let i = 1; i <= 8; i += 1) await touch('touchMove', pt(at.malleus, 'malleus').x + i * 8, pt(at.malleus, 'malleus').y);
      await touch('touchEnd', 0, 0);
      await page.waitForTimeout(300);
      await expect(page.getByTestId('structure-card')).toHaveCount(0);
    });
  });
}

test.describe('touch, phone, settings and about', () => {
  test.use({ viewport: SCREENS.phone, isMobile: true, hasTouch: true, deviceScaleFactor: 2, locale: 'en-US' });

  test('switches to Arabic and shows the credit in About', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Settings' }).tap({ timeout: 8000 });
    await page.getByText('العربية').tap();
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await page.getByRole('button', { name: 'رجوع' }).tap();
    await page.getByRole('button', { name: 'حول التطبيق' }).tap();
    await expect(page.getByText('تم تصميم التطبيق بإشراف د. علي ر. محمد').first()).toBeVisible();
    await noSidewaysScroll(page);
  });
});

test.describe('touch, phone, parts of a structure', () => {
  test.use({ viewport: SCREENS.phone, isMobile: true, hasTouch: true, deviceScaleFactor: 2, locale: 'en-US' });

  test('parts are listed under their structure and can be shown, hidden and opened', async ({ page }) => {
    await serveFixtureContent(page);
    // Make both fixture structures parts of one group, as the ossicle parts are.
    await page.route('**/content/TEST-SYNTHETIC-01/manifest.json', async (route) => {
      const m = JSON.parse(await readFile(path.join(FIXTURES, 'TEST-SYNTHETIC-01', 'manifest.json'), 'utf8'));
      for (const s of m.structures) {
        s.group = { id: 'test_bone', names: { en: 'Test bone', ar: 'عظم اختباري', latin: 'Os probationis' } };
        s.source_part = s.id;
      }
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(m) });
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Open the viewer' }).tap({ timeout: 8000 });
    const group = page.locator('[data-group="test_bone"]');
    await expect(group).toContainText('Test bone');
    await expect(group).toContainText('2 parts');
    await expect(page.locator('[data-structure="malleus"]')).toHaveCount(0);

    // Folded, the structure has one label; hide and show every part from the group's box.
    const groupLabel = page.locator('.labels__label[data-label="test_bone"]');
    await expect(groupLabel).toHaveText('Test bone');
    await expect(page.locator('.labels__label[data-label="malleus"]')).toHaveCount(0);
    const box = group.getByRole('checkbox', { name: 'Show: Test bone' });
    await box.tap();
    await expect(groupLabel).toBeHidden();
    await box.tap();
    await expect(groupLabel).toBeVisible();

    // Unfolded, each part has its own label; tapping a part in 3D opens its card.
    await group.getByRole('button', { name: 'Show the parts of Test bone' }).tap();
    await expect(page.locator('.labels__label[data-label="malleus"]')).toBeVisible();
    await expect(groupLabel).toHaveCount(0);
    const at = await anchors(page);
    await page.touchscreen.tap(pt(at.malleus, 'malleus').x, pt(at.malleus, 'malleus').y);
    const card = page.getByTestId('structure-card');
    await expect(card).toContainText('Malleus');
    await expect(card).toContainText('divided by a stated rule');
    await expect(page.locator('[data-structure="malleus"] .structure-name')).toHaveAttribute('aria-pressed', 'true');

    await group.getByRole('button', { name: 'Hide the parts of Test bone' }).tap();
    await expect(page.locator('[data-structure="malleus"]')).toHaveCount(0);
  });
});
