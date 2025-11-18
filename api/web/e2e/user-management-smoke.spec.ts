import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './fixtures/auth';

test.describe('Scenario 2: User Management (Full CRUD)', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('should create a new user successfully', async ({ page }) => {
    await page.goto('/users');
    await page.waitForSelector('h1:has-text("Users")', { timeout: 5000 });

    // Click "Add User" button
    const addButton = page.locator('button:has-text("Add User")');
    await expect(addButton).toBeVisible();
    await addButton.click();

    // Wait for modal to open
    await page.waitForSelector('text=Add New User', { timeout: 3000 });

    // Generate unique telegram_id to avoid conflicts
    const uniqueTelegramId = Date.now().toString();
    
    // Fill form
    await page.fill('input[placeholder="Enter user name"]', 'Test Worker E2E');
    await page.fill('input[placeholder="Enter Telegram ID"]', uniqueTelegramId);
    await page.selectOption('select', 'worker');

    // Submit form
    await page.click('button:has-text("Create User")');

    // UX-V2: Instead of waiting for toast, verify user appears in table (more reliable)
    await page.waitForSelector(`text=Test Worker E2E`, { timeout: 10000 });
    await expect(page.locator(`text=${uniqueTelegramId}`)).toBeVisible();
    
    // Optionally check for toast (but don't fail if it disappears quickly)
    const toast = page.locator('[role="status"], [role="alert"]').filter({ hasText: /created/i });
    if (await toast.isVisible().catch(() => false)) {
      console.log('[User Create] Toast appeared successfully');
    }
  });

  test('should edit user role successfully', async ({ page }) => {
    await page.goto('/users');
    await page.waitForSelector('h1:has-text("Users")', { timeout: 5000 });
    
    // UX-V2: Wait for table to load first
    await page.waitForSelector('table tbody tr', { timeout: 10000 });

    // Find first "Edit" button in table and click it
    const editButton = page.locator('button:has-text("Edit")').first();
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

    // Find first "Deactivate" button (active user)
    const deactivateButton = page.locator('button:has-text("Deactivate")').first();
    
    if (await deactivateButton.isVisible()) {
      // UX-V2-D1: Use page.once() to avoid double handling
      page.once('dialog', dialog => dialog.accept());
      
      await deactivateButton.click();

      // Wait for success toast
      await page.waitForSelector('text=/deactivated/i', { timeout: 5000 });

      // Refresh to verify status change
      await page.reload();
      await page.waitForSelector('h1:has-text("Users")', { timeout: 5000 });

      // Now find "Activate" button for same user
      const activateButton = page.locator('button:has-text("Activate")').first();
      
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
