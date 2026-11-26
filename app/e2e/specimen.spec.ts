import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

/**
 * A content package built by the real pipeline from synthetic labels: an ellipsoid
 * mapped to "Malleus" (radii 1.5, 1, 1 mm at the origin) and a 1 mm sphere mapped to
 * "Scala Tympani" 5 mm away. The true gap between them is 2.50 mm.
 */
const FIXTURES = path.join(path.dirname(fileURLToPath(import.meta.url)), 'fixtures', 'content');

async function serveFixtureContent(page: Page): Promise<void> {
  await page.route('**/content/**', async (route) => {
    const relative = new URL(route.request().url()).pathname.split('/content/')[1] ?? '';
    try {
      const body = await readFile(path.join(FIXTURES, relative));
      const contentType = relative.endsWith('.json')
        ? 'application/json'
        : relative.endsWith('.gz')
          ? 'application/octet-stream'
          : 'model/gltf-binary';
      await route.fulfill({ body, contentType });
    } catch {
      await route.fulfill({ status: 404, body: 'not found' });
    }
  });
}

test.describe('specimen package', () => {
  test.use({ locale: 'en-US' });

  test('loads an installed package and measures on it', async ({ page }, testInfo) => {
    await serveFixtureContent(page);
    await page.goto('/');
    await page.getByRole('button', { name: 'Open the viewer' }).click({ timeout: 8000 });

    await expect(page.getByTestId('specimen-select')).toHaveValue('TEST-SYNTHETIC-01');
    await expect(page.locator('[data-structure="malleus"]')).toContainText('Malleus');
    await expect(page.locator('[data-structure="scala_tympani"]')).toContainText('Scala tympani');
    await expect(page.getByText('Draft: not yet reviewed by an expert')).toBeVisible();
    await expect(page.getByTestId('specimen-attribution')).toContainText('10.5281/zenodo.1473724');

    await page.getByRole('button', { name: 'Closest surfaces' }).click();
    const result = page.getByTestId('measurement-result');
    // Voxelised at 0.125 mm and smoothed within 0.05 mm of the label surface.
    await expect(result).toContainText(/2\.(4[5-9]|5\d) mm/);
    await expect(result).toContainText('TEST-SYNTHETIC-01');
    await expect(result).toContainText('Source voxel size: 0.125 mm');
    await page.screenshot({ path: testInfo.outputPath('specimen-en.png') });
  });

  test('shows a structure card and labels', async ({ page }, testInfo) => {
    await serveFixtureContent(page);
    await page.goto('/');
    await page.getByRole('button', { name: 'Open the viewer' }).click({ timeout: 8000 });
    await expect(page.locator('.labels__label[data-label="malleus"]')).toHaveText('Malleus');

    await page.locator('[data-structure="malleus"] .structure-name').click();
    const card = page.getByTestId('structure-card');
    await expect(card).toContainText('Malleus');
    await expect(card).toContainText("Specimen-derived: built from this specimen's own segmentation");
    await expect(card).toContainText(/Within 0\.\d\d mm of its label \(limit 0\.10 mm\)/);
    await page.screenshot({ path: testInfo.outputPath('card-en.png') });

    await card.getByRole('button', { name: 'Close' }).click();
    await expect(card).toHaveCount(0);
    await page.getByRole('checkbox', { name: 'Labels' }).uncheck();
    await expect(page.locator('.labels')).toBeHidden();
  });

  test('opens the scan slices with structure outlines', async ({ page }, testInfo) => {
    await serveFixtureContent(page);
    await page.goto('/');
    await page.getByRole('button', { name: 'Open the viewer' }).click({ timeout: 8000 });
    await page.getByRole('button', { name: 'Show scan slices' }).click();
    const pane = page.getByTestId('slice-pane');
    await expect(pane).toBeVisible();
    await expect(pane.getByRole('status')).toHaveCount(0, { timeout: 8000 });
    await expect(pane).toContainText(/z = -?\d+\.\d+ mm · synthetic, voxel 0\.25 mm/);
    // Some outline colour (malleus orange) must be drawn on the slice.
    const coloured = await pane.locator('canvas').evaluate((c: HTMLCanvasElement) => {
      const ctx = c.getContext('2d');
      if (!ctx) return 0;
      const d = ctx.getImageData(0, 0, c.width, c.height).data;
      let n = 0;
      for (let i = 0; i < d.length; i += 4) if ((d[i] ?? 0) > 150 && (d[i + 2] ?? 0) < 80) n += 1;
      return n;
    });
    expect(coloured).toBeGreaterThan(20);
    // Tap inside the malleus outline: halfway between its leftmost and rightmost pixels on one row.
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
        if (hi - lo > 20) {
          const r = c.getBoundingClientRect();
          return { x: ((lo + hi) / 2) * (r.width / width), y: y * (r.height / height) };
        }
      }
      return null;
    });
    expect(target).not.toBeNull();
    await pane.locator('canvas').click({ position: target as { x: number; y: number } });
    await expect(page.getByTestId('structure-card')).toContainText('Malleus');
    await pane.getByRole('button', { name: 'YZ plane' }).click();
    await expect(pane).toContainText(/x = /);
    await page.screenshot({ path: testInfo.outputPath('slices-en.png') });
  });

  test('falls back to the phantom when the package is broken', async ({ page }) => {
    await page.route('**/content/index.json', (route) =>
      route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ specimens: [{ id: 'BROKEN', path: 'BROKEN' }] }),
      }),
    );
    await page.route('**/content/BROKEN/**', (route) => route.fulfill({ status: 404, body: '' }));
    await page.goto('/');
    await page.getByRole('button', { name: 'Open the viewer' }).click({ timeout: 8000 });
    await expect(page.getByText('This specimen could not be loaded.')).toBeVisible();
    await page.getByTestId('specimen-select').selectOption('phantom');
    await expect(page.getByText('Synthetic test phantom, not anatomy')).toBeVisible();
  });
});

test.describe('specimen package in Arabic', () => {
  test.use({ locale: 'ar-SY' });

  test('shows Arabic names with the Latin term beneath', async ({ page }, testInfo) => {
    await serveFixtureContent(page);
    await page.goto('/');
    await page.getByRole('button', { name: 'افتح العارض' }).click({ timeout: 8000 });
    const malleus = page.locator('[data-structure="malleus"]');
    await expect(malleus).toContainText('المطرقة');
    await expect(malleus).toContainText('Malleus');
    await expect(page.getByText('مسودة: لم يراجعها خبير بعد')).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('specimen-ar.png') });
  });
});

test.describe('chapter topics', () => {
  test.use({ locale: 'en-US' });

  test('a topic shows its structures on the specimen', async ({ page }, testInfo) => {
    await serveFixtureContent(page);
    await page.goto('/');
    await page.getByTestId('open-topics').click({ timeout: 8000 });
    await page.getByTestId('topics-search').fill('malleus');
    await page.getByRole('button', { name: 'Malleus', exact: true }).click();
    await expect(page.getByTestId('topic-reader')).toContainText('Surgical relevance');
    await page.screenshot({ path: testInfo.outputPath('topic-en.png'), fullPage: true });
    await page.getByTestId('topic-show').click();
    await expect(page.getByTestId('specimen-select')).toHaveValue('TEST-SYNTHETIC-01');
    await expect(page.getByTestId('structure-card')).toContainText('Malleus');
  });

  test('says so when the specimen lacks the structures of a topic', async ({ page }) => {
    await serveFixtureContent(page);
    await page.goto('/');
    await page.getByTestId('open-topics').click({ timeout: 8000 });
    await page.getByRole('button', { name: 'Segments of the facial nerve' }).click();
    await page.getByTestId('topic-show').click();
    await expect(page.getByRole('status').filter({ hasText: 'does not include' })).toContainText('Facial nerve');
  });

  test('the structure card opens a topic over the 3D view', async ({ page }, testInfo) => {
    await serveFixtureContent(page);
    await page.goto('/');
    await page.getByRole('button', { name: 'Open the viewer' }).click({ timeout: 8000 });
    await page.locator('[data-structure="malleus"] .structure-name').click();
    const card = page.getByTestId('structure-card');
    await card.getByRole('button', { name: 'Malleus', exact: true }).click();
    const overlay = page.getByRole('dialog');
    await expect(overlay.getByTestId('topic-reader')).toContainText('lateral (short) process');
    await page.screenshot({ path: testInfo.outputPath('topic-overlay-en.png') });
    await overlay.getByRole('button', { name: 'Close the topic' }).click();
    await expect(overlay).toHaveCount(0);
    await expect(card).toBeVisible();
  });
});
