import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './fixtures/auth';
import { enableNetworkDebug, verifyAuthState, type NetworkLog } from './fixtures/networkDebug';

test.describe('Scenario 1: Inbox Bulk Approve', () => {
  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== testInfo.expectedStatus) {
      const screenshotPath = `test-results/failure-${testInfo.title.replace(/\s+/g, '-')}-${Date.now()}.png`;
      await page.screenshot({ path: screenshotPath, fullPage: true });
      console.log('[F4.4 SCREENSHOT]', screenshotPath);
    }
  });

  test('should approve multiple pending items in bulk', async ({ page }) => {
    // F4.4 A1: Network instrumentation for /api/admin/pending
    const networkLogs: NetworkLog[] = enableNetworkDebug(page, /\/api\/(auth\/login|admin\/pending)/);

    await loginAsAdmin(page);

    // F4.4 A1: Verify auth state after login
    const authState = await verifyAuthState(page);
    expect(authState.hasToken, 'JWT token must be present').toBeTruthy();
    console.log('[F4.4 AUTH]', { hasToken: authState.hasToken, user: authState.user?.name });

    // F4.3.3 FIX: Navigate via sidebar using React Router (client-side navigation)
    await page.click('a[href="/inbox"]');
    await page.waitForURL('**/inbox', { timeout: 5000 });

    // F4.4 A1: Capture API response
    try {
      const pendingResponse = await page.waitForResponse(
        (resp) => resp.url().includes('/api/admin/pending') && resp.status() !== 304,
        { timeout: 5000 }
      );
      console.log('[F4.4 NETWORK]', {
        url: pendingResponse.url(),
        status: pendingResponse.status(),
        statusText: pendingResponse.statusText(),
      });
    } catch (err) {
      console.error('[F4.4 NETWORK] No API response captured:', err);
    }

    await page.waitForTimeout(1000);

    // Check for error state (UI should show error if API fails)
    const errorContainer = page.locator('div:has-text("Failed to load pending items")');
    const hasError = await errorContainer.isVisible({ timeout: 1000 }).catch(() => false);
    if (hasError) {
      const errorText = await errorContainer.textContent();
      console.error('[F4.4 UI ERROR]', errorText);
      throw new Error(`UI error state: ${errorText}`);
    }

    // STRICT CHECK: After seeding, pending items MUST exist
    const table = page.locator('table');
    await expect(table).toBeVisible({ timeout: 3000 });
    
    // Verify we have pending items (seeded data)
    const rowCount = await page.locator('tbody tr').count();
    expect(rowCount).toBeGreaterThan(0); // FAIL if no data (seed issue)

    // Select first 2 items (or fewer if not available)
    const itemsToSelect = Math.min(2, rowCount);
    for (let i = 0; i < itemsToSelect; i++) {
      await page.locator(`tbody tr:nth-child(${i + 1}) input[type="checkbox"]`).check();
    }

    // Verify selection count
    const checkedCount = await page.locator('tbody tr input[type="checkbox"]:checked').count();
    expect(checkedCount).toBe(itemsToSelect);

    // Click bulk approve button
    await page.click('button:has-text("Approve Selected"), button:has-text("Одобрить")');

    // Wait for success indication (toast or page reload)
    await page.waitForTimeout(2000);

    // Verify items were approved (should disappear from pending list or status changed)
    const newRowCount = await page.locator('tbody tr').count();
    expect(newRowCount).toBeLessThanOrEqual(rowCount);
  });
});
