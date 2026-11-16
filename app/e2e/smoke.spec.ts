import { expect, test } from '@playwright/test';

const CREDIT_EN = 'Designed under the supervision of Dr. Ali R. Muhammad';
const CREDIT_AR = 'تم تصميم التطبيق بإشراف د. علي ر. محمد';

test.describe('English', () => {
  test.use({ locale: 'en-US' });

  test('splash shows the credit, then the home screen opens', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('splash-screen')).toContainText(CREDIT_EN);
    await expect(page.getByTestId('home-screen')).toBeVisible({ timeout: 6000 });
    await expect(page.locator('footer')).toContainText(CREDIT_EN);
    await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
  });

  test('viewer renders and measures the phantom gap', async ({ page }, testInfo) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Open the viewer' }).click({ timeout: 8000 });
    await expect(page.locator('.viewer__canvas canvas')).toBeVisible();
    await expect(page.getByText('This device or browser cannot start 3D graphics.')).toHaveCount(0);
    await expect(page.getByText('Synthetic test phantom, not anatomy')).toBeVisible();

    // Sphere A (r = 3 mm) and sphere B (r = 2 mm) are 8 mm apart: the true gap is 3.00 mm.
    await page.getByRole('button', { name: 'Closest surfaces' }).click();
    const result = page.getByTestId('measurement-result');
    await expect(result).toContainText(/3\.0\d mm/);
    await expect(result).toContainText('PHANTOM-01');
    await expect(result).toContainText('Minimum distance between two triangulated surfaces');
    await page.screenshot({ path: testInfo.outputPath('viewer-en.png') });
  });
});

test.describe('Arabic', () => {
  test.use({ locale: 'ar-SY' });

  test('starts in Arabic, right to left, with the Arabic credit', async ({ page }, testInfo) => {
    await page.goto('/');
    await expect(page.getByTestId('splash-screen')).toContainText(CREDIT_AR);
    await page.screenshot({ path: testInfo.outputPath('splash-ar.png') });
    await expect(page.getByTestId('home-screen')).toBeVisible({ timeout: 6000 });
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await expect(page.locator('footer')).toContainText(CREDIT_AR);
    await page.screenshot({ path: testInfo.outputPath('home-ar.png') });
  });

  test('viewer panel sits on the left in right-to-left layout', async ({ page }, testInfo) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'افتح العارض' }).click({ timeout: 8000 });
    const panel = await page.locator('.viewer__panel').boundingBox();
    const stage = await page.locator('.viewer__stage').boundingBox();
    expect(panel && stage && panel.x < stage.x).toBeTruthy();
    await page.getByRole('button', { name: 'أقرب مسافة بين سطحين' }).click();
    await expect(page.getByTestId('measurement-result')).toContainText(/3\.0\d مم/);
    await page.screenshot({ path: testInfo.outputPath('viewer-ar.png') });
  });

  test('About lists the credit, version and dataset citations', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'حول التطبيق' }).click({ timeout: 8000 });
    const about = page.getByTestId('about-screen');
    await expect(about).toContainText(CREDIT_AR);
    await expect(about).toContainText('10.5281/zenodo.1473724');
    await expect(about).toContainText('10.5281/zenodo.3355272');
  });
});
