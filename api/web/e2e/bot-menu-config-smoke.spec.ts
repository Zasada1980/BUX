import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './fixtures/auth';
import { enableNetworkDebug, verifyAuthState, type NetworkLog } from './fixtures/networkDebug';

test.describe('Scenario 6: Bot Menu Config', () => {
  test('should toggle command enabled state and persist after reload', async ({ page }) => {
    // Enable network debugging
    const networkLogs: NetworkLog[] = enableNetworkDebug(page, /\/api\/(auth\/login|admin\/bot-menu)/);

    // Login as admin and verify auth
    await loginAsAdmin(page);
    const authState = await verifyAuthState(page);
    expect(authState.hasToken).toBeTruthy();

    // Navigate to Bot Menu page
    await page.goto('/bot-menu');
    await page.waitForTimeout(2000);

    // Verify page loaded
    await expect(page.locator('h1').filter({ hasText: /Bot Menu/i }).first()).toBeVisible();

    // Wait for table to load
    const table = page.locator('table');
    await expect(table).toBeVisible();

    // Verify we have commands in Worker tab (default active tab)
    const workerTab = page.locator('button').filter({ hasText: /Worker/ });
    await expect(workerTab).toHaveClass(/border-blue-600/); // Active tab class

    // Count rows in Worker tab
    const rowCount = await table.locator('tbody tr').count();
    expect(rowCount).toBeGreaterThan(0);
    console.log(`[F5.3 Bot Menu] Worker tab has ${rowCount} commands`);

    // Use 3rd row (index 2) for testing — 1st and 2nd are core commands (/start, /end) which cannot be toggled OFF
    const testRowIndex = Math.min(2, rowCount - 1); // Use 3rd row if exists (non-core command /expense), else last row
    const testRow = table.locator('tbody tr').nth(testRowIndex);
    
    // Find toggle button (unique class combination: h-6 w-11 rounded-full)
    const toggleButton = testRow.locator('button.rounded-full.h-6.w-11');
    
    // Wait for button to be in DOM with increased timeout
    await toggleButton.waitFor({ state: 'attached', timeout: 10000 });
    
    // Get initial state (enabled by default from seed data)
    const initialClass = await toggleButton.getAttribute('class');
    const isInitiallyEnabled = initialClass?.includes('bg-blue-600') ?? false;
    console.log(`[F5.3 Bot Menu] Initial toggle state (row ${testRowIndex}): ${isInitiallyEnabled ? 'enabled' : 'disabled'}`);

    // Scroll row into view first
    await testRow.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);

    // Save button should be disabled initially (no changes)
    const saveButtonBefore = page.locator('button').filter({ hasText: /Save Changes/i });
    await expect(saveButtonBefore).toBeDisabled();

    // Toggle the command (disable it) - use evaluate to trigger React onClick
    await toggleButton.evaluate((btn) => {
      (btn as HTMLElement).click();
    });
    await page.waitForTimeout(1000); // Wait for React state update

    // Save button should now be enabled (hasChanges = true)
    const saveButtonAfter = page.locator('button').filter({ hasText: /Save Changes/i });
    await expect(saveButtonAfter).toBeEnabled({ timeout: 3000 });

    // Click Save button
    const saveButton = page.locator('button').filter({ hasText: /Save Changes/i });
    await expect(saveButton).toBeEnabled();
    await saveButton.click();

    // Wait for save to complete (alert or network request)
    await page.waitForTimeout(1500);

    // Reload page to verify persistence
    await page.reload();
    await page.waitForTimeout(2000);

    // Verify table reloaded
    await expect(table).toBeVisible();

    // Check that toggle state persisted (should be opposite of initial)
    const testRowAfterReload = table.locator('tbody tr').nth(testRowIndex);
    const toggleAfterReload = testRowAfterReload.locator('button.rounded-full.h-6.w-11');
    await toggleAfterReload.waitFor({ state: 'attached', timeout: 10000 });
    
    const classAfterReload = await toggleAfterReload.getAttribute('class');
    const isEnabledAfterReload = classAfterReload?.includes('bg-blue-600') ?? false;

    expect(isEnabledAfterReload).toBe(!isInitiallyEnabled);
    console.log(`[F5.3 Bot Menu] ✅ PASS — Toggle persisted after reload (${isInitiallyEnabled} → ${isEnabledAfterReload})`);
  });
});

