import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './fixtures/auth';
import { enableNetworkDebug, verifyAuthState, type NetworkLog } from './fixtures/networkDebug';

test.describe('Scenario 5: Shift Review', () => {
  test('should load Shifts page with table and data', async ({ page }) => {
    // F5.2: Basic Shifts Web UI (read-only admin/foreman access)
    // Enable network debugging for API requests
    const networkLogs: NetworkLog[] = enableNetworkDebug(page, /\/api\/(auth\/login|shifts)/);
    
    // Login as admin
    await loginAsAdmin(page);
    
    // Verify auth state after login
    const authState = await verifyAuthState(page);
    expect(authState.hasToken, 'JWT token must be present after login').toBeTruthy();
    expect(authState.user, 'User object must be present after login').toBeTruthy();
    console.log('[F5.2 Shifts] Auth verified:', {
      hasToken: authState.hasToken,
      userName: authState.user?.name,
      storageType: authState.storageType,
    });
    
    // Navigate to Shifts page
    await page.goto('/shifts');
    await page.waitForURL('**/shifts');
    
    // Wait for page to load (either table or error)
    await page.waitForTimeout(2000);  // Allow API call to complete
    
    // Check if we're stuck in loading state
    const isLoading = await page.locator('text=/Loading shifts/i').isVisible();
    if (isLoading) {
      console.error('[F5.2 ERROR] Page stuck in Loading state');
      console.error('[F5.2 NETWORK LOGS]', networkLogs);
      throw new Error('Shifts page stuck in Loading state - check network logs above');
    }
    
    // Verify page content (h1 in page content, not header logo)
    await expect(page.locator('h1').filter({ hasText: /Shifts/i }).first()).toBeVisible({ timeout: 5000 });
    
    // Verify table exists (DataTable component)
    const table = page.locator('table');
    await expect(table).toBeVisible({ timeout: 5000 });
    
    // Verify at least one row of data (excluding header)
    const rows = table.locator('tbody tr');
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);
    
    // Verify key columns are visible (use partial match due to dynamic column names)
    await expect(page.locator('th:has-text("ID")')).toBeVisible();
    await expect(page.locator('th').filter({ hasText: /Worker|User/i })).toBeVisible();
    await expect(page.locator('th:has-text("Duration")')).toBeVisible();
    await expect(page.locator('th:has-text("Status")')).toBeVisible();
    
    // Verify no error UI
    await expect(page.locator('text=/Ошибка загрузки|Failed to load|Error loading/i')).toHaveCount(0);
    
    console.log(`[F5.2 Shifts] ✅ PASS — Table visible with ${rowCount} shifts`);
  });
});
