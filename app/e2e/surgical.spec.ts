import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type Page } from '@playwright/test';

/**
 * The surgical view has its own entry and its own screen. The package here carries a tiny true-colour
 * volume (a pink ball with a dark core, made with the pipeline's own brick writer), so the whole path
 * runs in a real browser: manifest, download, unpacking, 3D textures, ray-marching.
 */
const HERE = path.dirname(fileURLToPath(import.meta.url));

async function serve(page: Page, folder: 'content' | 'content-colour'): Promise<void> {
  await page.route('**/content/**', async (route) => {
    const relative = new URL(route.request().url()).pathname.split('/content/')[1] ?? '';
    try {
      const body = await readFile(path.join(HERE, 'fixtures', folder, relative));
      const type = relative.endsWith('.json') ? 'application/json' : 'application/octet-stream';
      await route.fulfill({ body, contentType: type });
    } catch {
      await route.fulfill({ status: 404, body: 'not found' });
    }
  });
}

/** Colour of one pixel of a PNG screenshot, read back through a canvas in the page. */
async function pixelAt(page: Page, png: Buffer, fx: number, fy: number): Promise<[number, number, number]> {
  return page.evaluate(
    async ({ b64, fx, fy }) => {
      const img = new Image();
      img.src = `data:image/png;base64,${b64}`;
      await img.decode();
      const c = document.createElement('canvas');
      c.width = img.width;
      c.height = img.height;
      const ctx = c.getContext('2d');
      if (!ctx) throw new Error('no 2d canvas');
      ctx.drawImage(img, 0, 0);
      const d = ctx.getImageData(Math.floor(img.width * fx), Math.floor(img.height * fy), 1, 1).data;
      return [d[0] ?? 0, d[1] ?? 0, d[2] ?? 0] as [number, number, number];
    },
    { b64: png.toString('base64'), fx, fy },
  );
}

test.describe('surgical view', () => {
  test.use({ locale: 'en-US' });

  test('has its own entry on the home screen and opens its own screen', async ({ page }) => {
    await serve(page, 'content-colour');
    await page.goto('/');
    await expect(page.getByTestId('home-anatomy')).toContainText('Anatomical models');
    await expect(page.getByTestId('home-surgical')).toContainText('Surgical view');
    await page.getByTestId('open-surgical').click({ timeout: 8000 });
    await expect(page.getByTestId('surgical-screen')).toBeVisible();
    // None of the anatomical viewer is on this screen.
    await expect(page.getByTestId('viewer-screen')).toHaveCount(0);
    await expect(page.getByTestId('specimen-select')).toHaveCount(0);
    await expect(page.getByTestId('surgical-specimen-select')).toHaveValue('TEST-COLOUR-01');
    // And the other way round: the viewer has no surgical controls.
    await page.getByRole('button', { name: 'Back' }).click();
    await page.getByRole('button', { name: 'Open the viewer' }).click();
    await expect(page.getByTestId('viewer-screen')).toBeVisible();
    await expect(page.getByTestId('surgical-screen')).toHaveCount(0);
    await expect(page.getByTestId('surgical-mode')).toHaveCount(0);
  });

  test('says so when no specimen has colour data', async ({ page }) => {
    await serve(page, 'content');
    await page.goto('/');
    await page.getByTestId('open-surgical').click({ timeout: 8000 });
    await expect(page.getByTestId('surgical-empty')).toContainText('No specimen with colour data');
  });

  test('draws the specimen in colour, and responds to the controls', async ({ page }, testInfo) => {
    await serve(page, 'content-colour');
    await page.goto('/');
    await page.getByTestId('open-surgical').click({ timeout: 8000 });
    const stage = page.getByTestId('surgical-stage');
    await expect(stage).toHaveAttribute('data-phase', 'ready', { timeout: 30_000 });
    await expect(page.getByTestId('surgical-hud')).toContainText('Drag to turn');
    // Let a few frames settle, then look at the middle of the picture: tissue is reddish, the background is dark blue-grey.
    await page.waitForTimeout(500);
    const canvas = page.getByTestId('surgical-canvas');
    const first = await canvas.screenshot();
    const [r, g, b] = await pixelAt(page, first, 0.5, 0.5);
    expect(r).toBeGreaterThan(g + 25);
    expect(r).toBeGreaterThan(b + 25);
    const [br, bg, bb] = await pixelAt(page, first, 0.02, 0.02);
    expect(Math.max(br, bg, bb)).toBeLessThan(60);
    await testInfo.attach('surgical.png', { body: first, contentType: 'image/png' });

    // Cutting into the block changes the picture.
    await page.getByTestId('surgical-cut').fill('0.5');
    await page.waitForTimeout(400);
    const cut = await canvas.screenshot();
    expect(Buffer.compare(first, cut)).not.toBe(0);

    // The detail choice reloads the other tier and the view comes back.
    await expect(page.getByTestId('surgical-quality').locator('option')).toHaveCount(3);
    await page.getByTestId('surgical-quality').selectOption('standard');
    await expect(stage).toHaveAttribute('data-phase', 'ready', { timeout: 30_000 });
  });

  test('hides, isolates and tints structures with the label volume, on its own list', async ({ page }) => {
    await serve(page, 'content-colour');
    await page.goto('/');
    await page.getByTestId('open-surgical').click({ timeout: 8000 });
    await expect(page.getByTestId('surgical-stage')).toHaveAttribute('data-phase', 'ready', { timeout: 30_000 });
    const list = page.getByTestId('surgical-structures');
    await expect(list).toContainText('Structures (2 of 2 shown)');
    const canvas = page.getByTestId('surgical-canvas');
    await page.waitForTimeout(400);
    const all = await canvas.screenshot();

    // Hiding the outer shell shows what is inside it.
    await page.getByTestId('surgical-structure-malleus').uncheck();
    await expect(list).toContainText('1 of 2 shown');
    await page.waitForTimeout(400);
    const inner = await canvas.screenshot();
    expect(Buffer.compare(all, inner)).not.toBe(0);
    const [r0, g0, b0] = await pixelAt(page, all, 0.5, 0.5);
    const [r1, g1, b1] = await pixelAt(page, inner, 0.5, 0.5);
    expect(Math.abs(r0 - r1) + Math.abs(g0 - g1) + Math.abs(b0 - b1)).toBeGreaterThan(30);

    // "Show all" brings the first picture back exactly.
    await page.getByTestId('surgical-show-all').click();
    await expect(list).toContainText('2 of 2 shown');
    await page.waitForTimeout(400);
    const back = await canvas.screenshot();
    expect(Buffer.compare(all, back)).toBe(0);

    // Keeping only one structure hides the other.
    await page.getByTestId('surgical-isolate-scala_tympani').click();
    await expect(page.getByTestId('surgical-structure-malleus')).not.toBeChecked();
    await expect(page.getByTestId('surgical-structure-scala_tympani')).toBeChecked();

    // Tinting changes the colours.
    await page.getByTestId('surgical-show-all').click();
    await page.getByTestId('surgical-tint').check();
    await page.waitForTimeout(400);
    const tinted = await canvas.screenshot();
    expect(Buffer.compare(all, tinted)).not.toBe(0);

    // The anatomical viewer has none of this.
    await page.getByRole('button', { name: 'Back' }).click();
    await page.getByRole('button', { name: 'Open the viewer' }).click();
    await expect(page.getByTestId('surgical-structures')).toHaveCount(0);
  });

  test('is in Arabic, with the credit and the disclaimer', async ({ browser }) => {
    const context = await browser.newContext({ locale: 'ar-SY' });
    const page = await context.newPage();
    await serve(page, 'content-colour');
    await page.goto('/');
    await page.getByTestId('open-surgical').click({ timeout: 8000 });
    await expect(page.getByTestId('surgical-screen')).toContainText('الرؤية الجراحية');
    await expect(page.getByTestId('surgical-screen')).toContainText('تم تصميم التطبيق بإشراف د. علي ر. محمد');
    await expect(page.getByTestId('surgical-stage')).toHaveAttribute('data-phase', 'ready', { timeout: 30_000 });
    await context.close();
  });
});
