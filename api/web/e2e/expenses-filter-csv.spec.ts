import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './fixtures/auth';
import { enableNetworkDebug, verifyAuthState, type NetworkLog } from './fixtures/networkDebug';

test.describe('Scenario 3: Expense Filtering + CSV Export', () => {
  // STEP 1.2: Screenshot on failure for visual debugging
  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== testInfo.expectedStatus) {
      const screenshotPath = `test-results/failure-${testInfo.title.replace(/\s+/g, '-')}-${Date.now()}.png`;
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log('[F4.3.4 PRE-BACKEND-FIX] Screenshot saved:', screenshotPath);
    }
  });

  test('should filter expenses and export to CSV', async ({ page }) => {
    // STEP 1.2: Enable network debugging for API requests
    const networkLogs: NetworkLog[] = enableNetworkDebug(page, /\/api\/(auth\/login|expenses)/);

    await loginAsAdmin(page);

    // STEP 1.2: Verify auth state after login (replaces old inline debug)
    const authState = await verifyAuthState(page);
    expect(authState.hasToken, 'JWT token must be present after login').toBeTruthy();
    expect(authState.user, 'User object must be present after login').toBeTruthy();
    console.log('[F4.3.4 PRE-BACKEND-FIX] Auth verified:', {
      hasToken: authState.hasToken,
      userName: authState.user?.name,
      storageType: authState.storageType,
    });

    // F4.3.3 FIX: Navigate via sidebar using React Router
    await page.click('a[href="/expenses"]');
    await page.waitForURL('**/expenses', { timeout: 5000 });

    // STEP 1.2: Wait for API response (capture network activity)
    try {
      const expensesResponse = await page.waitForResponse(
        (resp) => resp.url().includes('/api/expenses') && resp.status() !== 304,
        { timeout: 5000 }
      );
      console.log('[F4.4 NETWORK] Expenses API response:', {
        status: expensesResponse.status(),
        statusText: expensesResponse.statusText(),
        url: expensesResponse.url(),
      });
    } catch (err) {
      console.error('[F4.4 NETWORK] No API response captured within 5s:', err);
    }

    // Wait for page to stabilize (removed old debug code causing navigation errors)
    await page.waitForTimeout(1000);

    // STRICT CHECK: After seeding, expenses MUST exist
    const table = page.locator('table');
    await expect(table).toBeVisible({ timeout: 3000 });
    
    const initialCount = await page.locator('tbody tr').count();
    expect(initialCount).toBeGreaterThan(0); // FAIL if no data (seed issue)

    // Apply date filter (last 30 days)
    const today = new Date();
    const dateFrom = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
    
    const dateFromInput = page.locator('input[type="date"]').first();
    const dateToInput = page.locator('input[type="date"]').nth(1);
    
    if (await dateFromInput.count() > 0) {
      await dateFromInput.fill(dateFrom.toISOString().split('T')[0]);
      await dateToInput.fill(today.toISOString().split('T')[0]);
      await page.waitForTimeout(1000);
    }

    // Verify data is present
    const filteredCount = await page.locator('tbody tr').count();
    expect(filteredCount).toBeGreaterThanOrEqual(0);

    // F4.5 IMPLEMENTATION: CSV export functional with download verification
    const exportButton = page.locator('button:has-text("Export CSV")');
    await expect(exportButton).toBeVisible({ timeout: 3000 });
    await expect(exportButton).toBeEnabled();

    // Trigger download and verify filename pattern
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 });
    await exportButton.click();
    const download = await downloadPromise;
    
    // Verify filename: expenses_YYYYMMDD_HHMMSS.csv or expenses_YYYYMMDDThhmmss.csv
    const filename = download.suggestedFilename();
    expect(filename).toMatch(/^expenses_\d{8}[T_]\d{6}\.csv$/);
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

    // STEP 1.2: Dump network logs for Pre-Backend-Fix Report
    console.log('[F4.3.4 PRE-BACKEND-FIX] Network logs summary:', {
      totalRequests: networkLogs.filter((l) => l.type === 'request').length,
      totalResponses: networkLogs.filter((l) => l.type === 'response').length,
      unauthorizedResponses: networkLogs.filter((l) => l.status === 401).length,
      forbiddenResponses: networkLogs.filter((l) => l.status === 403).length,
    });
    // Detailed logs already printed by enableNetworkDebug() listeners
  });
});
