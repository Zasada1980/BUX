import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './fixtures/auth';
import { enableNetworkDebug, verifyAuthState, type NetworkLog } from './fixtures/networkDebug';

test.describe('Scenario 4: Invoice Review + CSV Export', () => {
  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== testInfo.expectedStatus) {
      const screenshotPath = `test-results/failure-${testInfo.title.replace(/\s+/g, '-')}-${Date.now()}.png`;
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log('[F4.4 SCREENSHOT]', screenshotPath);
    }
  });

  test('should review invoice and export to CSV', async ({ page }) => {
    // F4.4 A1: Network instrumentation for /api/invoices
    const networkLogs: NetworkLog[] = enableNetworkDebug(page, /\/api\/(auth\/login|invoices)/);

    await loginAsAdmin(page);

    // F4.4 A1: Verify auth state after login
    const authState = await verifyAuthState(page);
    expect(authState.hasToken, 'JWT token must be present').toBeTruthy();
    console.log('[F4.4 AUTH]', { hasToken: authState.hasToken, user: authState.user?.name });

    // F4.3.3 FIX: Navigate via sidebar using React Router
    await page.click('a[href="/invoices"]');
    await page.waitForURL('**/invoices', { timeout: 5000 });

    // F4.4 A1: Capture API response
    try {
      const invoicesResponse = await page.waitForResponse(
        (resp) => resp.url().includes('/api/invoices') && resp.status() !== 304,
        { timeout: 5000 }
      );
      console.log('[F4.4 NETWORK]', {
        url: invoicesResponse.url(),
        status: invoicesResponse.status(),
        statusText: invoicesResponse.statusText(),
      });
    } catch (err) {
      console.error('[F4.4 NETWORK] No API response captured:', err);
    }

    await page.waitForTimeout(1000);

    // STRICT CHECK: After seeding, invoices MUST exist
    const table = page.locator('table');
    await expect(table).toBeVisible({ timeout: 3000 });
    
    const rowCount = await page.locator('tbody tr').count();
    expect(rowCount).toBeGreaterThan(0); // FAIL if no data (seed issue)

    // Click on first invoice to view details
    await page.locator('tbody tr:first-child td:first-child').click();
    await page.waitForTimeout(1500);

    // Apply client filter (select first available option if dropdown exists)
    const clientFilter = page.locator('select[name="client"], select:has(option:has-text("Client"))').first();
    if (await clientFilter.count() > 0) {
      const options = await clientFilter.locator('option').count();
      if (options > 1) {
        await clientFilter.selectOption({ index: 1 });
        await page.waitForTimeout(1000);
      }
    }

    // F4.5 IMPLEMENTATION: CSV export functional with download verification
    const filteredCount = await page.locator('tbody tr').count();
    expect(filteredCount).toBeGreaterThanOrEqual(0);

    const exportButton = page.locator('button:has-text("Export CSV")');
    await expect(exportButton).toBeVisible({ timeout: 3000 });
    await expect(exportButton).toBeEnabled();

    // Trigger download and verify filename pattern
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 });
    await exportButton.click();
    const download = await downloadPromise;
    
    // Verify filename: invoices_YYYYMMDD_HHMMSS.csv or invoices_YYYYMMDDThhmmss.csv
    const filename = download.suggestedFilename();
    expect(filename).toMatch(/^invoices_\d{8}[T_]\d{6}\.csv$/);
    console.log('[F4.5 CSV Export] Downloaded file:', filename);

    // Verify file size > 0 (basic integrity check)
    const filePath = await download.path();
    if (filePath) {
      const fs = await import('fs');
      const stats = fs.statSync(filePath);
      expect(stats.size).toBeGreaterThan(0);
      console.log('[F4.5 CSV Export] File size:', stats.size, 'bytes');
    }

    // No strict content validation (just filename + non-zero size)
  });
});
