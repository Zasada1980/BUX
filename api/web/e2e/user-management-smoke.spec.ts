import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './fixtures/auth';

// E2E cloud-safe setup:
// - Container name can differ between environments (demo_api vs prod_api)
// - In CI or when Docker is unavailable, silently skip docker-based tweaks
const E2E_API_CONTAINER = process.env.E2E_API_CONTAINER || 'demo_api';
const E2E_USE_DOCKER = process.env.E2E_USE_DOCKER !== 'false';

test.describe('Scenario 2: User Management (Full CRUD)', () => {
  test.beforeEach(async ({ page, context }) => {
    // CI11 FIX (cloud-safe): Try to force admin role via docker when available; otherwise continue
    try {
      if (E2E_USE_DOCKER) {
        const { execSync } = await import('child_process');
        // Try to run seed inside the specified container (demo_api by default, prod_api on cloud)
        execSync(`docker exec ${E2E_API_CONTAINER} python /app/seeds/fix_admin_role.py`, { stdio: 'inherit' });
        // Best-effort: attempt restart to clear JWT cache; ignore failures on cloud/CI
        try {
          execSync(`docker restart ${E2E_API_CONTAINER}`, { stdio: 'inherit' });
        } catch (e) {
          console.log(`[E2E Setup] Skip docker restart for container '${E2E_API_CONTAINER}': ${String((e as Error)?.message || e)}`);
        }
      }
    } catch (e) {
      console.log(`[E2E Setup] Skip docker-based admin role fix: ${String((e as Error)?.message || e)}`);
    }

    // Wait for API to be healthy (retry up to 10s)
    for (let i = 0; i < 10; i++) {
      try {
        const response = await page.request.get('http://localhost:8188/health');
        if (response.ok()) break;
      } catch (e) {
        await page.waitForTimeout(1000);
      }
    }
    
    // Capture console logs and errors
    page.on('console', msg => {
      if (msg.type() === 'error' || msg.text().includes('Error') || msg.text().includes('Failed')) {
        console.log(`[Browser Console] ${msg.type()}: ${msg.text()}`);
      }
    });
    page.on('pageerror', err => {
      console.log(`[Browser Error] ${err.message}`);
    });
    
    await loginAsAdmin(page);
  });
  
  // Note: No afterEach cleanup needed - Playwright automatically clears browser context after each test

  test('should create a new user successfully', async ({ page }) => {
    await page.goto('/users');
    await page.waitForSelector('h1:has-text("Users")', { timeout: 5000 });

    // Click "Add User" button
    const addButton = page.locator('button:has-text("Add User")');
    await expect(addButton).toBeVisible();
    await addButton.click();

    // Wait for modal to open
    await page.waitForSelector('text=Add New User', { timeout: 3000 });

    // Generate unique telegram_username to avoid conflicts
    const timestamp = Date.now();
    const uniqueUsername = `testworker_${timestamp}`;
    const uniqueName = `Test Worker E2E ${timestamp}`;  // Make name unique too (409 Conflict fix)
    
    console.log(`[E2E Test] Creating user with username: ${uniqueUsername}, name: ${uniqueName}`);
    
    // Fill form (UX-V2: Updated to new schema - telegram_username instead of telegram_id)
    await page.fill('input[placeholder="Enter user name"]', uniqueName);
    await page.fill('input[placeholder="@username (or use ID/Phone)"]', `@${uniqueUsername}`);
    await page.selectOption('select', 'worker');
    
    console.log('[E2E Test] Form filled, clicking Create User button...');

    // Submit form
    await page.click('button:has-text("Create User")');

    // UX-V2: Wait for modal to close first (indicates submission success)
    await page.waitForSelector('text=Add New User', { state: 'hidden', timeout: 5000 });

    // Wait for table to reload with new user (F14-4: Fixed - apiClient now used instead of direct fetch)
    await page.waitForSelector('table tbody tr', { timeout: 15000 });
    
    // Verify user appears in table by unique name (name is always displayed, username might not be in columns)
    await expect(page.locator(`text=${uniqueName}`)).toBeVisible({ timeout: 10000 });
    
    console.log('[E2E Test] ✅ User created and visible in table');
  });

  test('should edit user role successfully', async ({ page }) => {
    await page.goto('/users');
    await page.waitForSelector('h1:has-text("Users")', { timeout: 5000 });
    
    // UX-V2: Wait for table to load first
    await page.waitForSelector('table tbody tr', { timeout: 10000 });

    // CI11 FIX: Edit SECOND user (not admin) to avoid losing admin rights
    // First user in table is always Admin User (id=1), skip it
    const editButton = page.locator('button:has-text("Edit")').nth(1);  // nth(1) = second button
    await expect(editButton).toBeVisible();
    await editButton.click();

    // Wait for edit modal
    await page.waitForSelector('text=Edit User', { timeout: 3000 });

    // Change role to "foreman"
    await page.selectOption('select', 'foreman');

    // Submit
    await page.click('button:has-text("Save Changes")');

    // Wait for success toast
    await page.waitForSelector('text=/updated successfully/i', { timeout: 5000 });

    // Verify modal closed
    await expect(page.locator('text=Edit User')).not.toBeVisible();
  });

  test('should deactivate and activate user successfully', async ({ page }) => {
    await page.goto('/users');
    await page.waitForSelector('h1:has-text("Users")', { timeout: 5000 });

    // CI11 FIX: Deactivate SECOND user (not admin) to avoid losing admin access
    // First "Deactivate" button is for Admin User (id=1), skip it
    const deactivateButton = page.locator('button:has-text("Deactivate")').nth(1);  // nth(1) = second button
    
    if (await deactivateButton.isVisible()) {
      // UX-V2-D1: Use page.once() to avoid double handling
      page.once('dialog', dialog => dialog.accept());
      
      await deactivateButton.click();

      // Wait for success toast
      await page.waitForSelector('text=/deactivated/i', { timeout: 5000 });

      // Refresh to verify status change
      await page.reload();
      await page.waitForSelector('h1:has-text("Users")', { timeout: 5000 });

      // CI11 FIX: Find SECOND "Activate" button (same user we deactivated)
      const activateButton = page.locator('button:has-text("Activate")').nth(1);  // nth(1) = second button
      
      if (await activateButton.isVisible()) {
        // UX-V2-D1: Use page.once() for second dialog
        page.once('dialog', dialog => dialog.accept());
        await activateButton.click();

        // Wait for success toast
        await page.waitForSelector('text=/activated/i', { timeout: 5000 });
      }
    }
  });

  test('should handle validation errors on create', async ({ page }) => {
    await page.goto('/users');
    await page.waitForSelector('h1:has-text("Users")', { timeout: 5000 });

    // Click "Add User"
    await page.click('button:has-text("Add User")');
    await page.waitForSelector('text=Add New User', { timeout: 3000 });

    // Try to submit empty form
    await page.click('button:has-text("Create User")');

    // Wait for error toast
    await page.waitForSelector('text=/required/i', { timeout: 3000 });

    // Close modal
    await page.click('button:has-text("Cancel")');
    await expect(page.locator('text=Add New User')).not.toBeVisible();
  });

  test('should export users to CSV', async ({ page }) => {
    await page.goto('/users');
    await page.waitForSelector('h1:has-text("Users")', { timeout: 5000 });

    // UX-V2: Wait for table with tbody (more specific selector)
    await page.waitForSelector('table tbody tr', { timeout: 10000 });

    // Click "Export CSV" button
    const exportButton = page.locator('button:has-text("Export CSV")');
    await expect(exportButton).toBeVisible();
    await expect(exportButton).toBeEnabled();

    await exportButton.click();

    // Wait for success toast
    await page.waitForSelector('text=/exported successfully/i', { timeout: 3000 });
  });

  test('should handle empty state gracefully', async ({ page }) => {
    await page.goto('/users');
    await page.waitForSelector('h1:has-text("Users")', { timeout: 5000 });

    // Page should render without errors even if no users
    const noUsersMessage = page.locator('text=No users found');
    const table = page.locator('table');

    // Either table exists OR "No users" message
    const hasContent = await table.isVisible().catch(() => false) || 
                       await noUsersMessage.isVisible().catch(() => false);
    
    expect(hasContent).toBe(true);
  });
});
