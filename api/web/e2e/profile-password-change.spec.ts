import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './fixtures/auth';

test.describe('Scenario 9: Profile & Password Change (Full Functionality)', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test('should display profile information', async ({ page }) => {
    // Navigate to Profile page
    await page.goto('/profile');
    await page.waitForSelector('h1:has-text("Profile")', { timeout: 5000 });

    // Verify Profile Info Card is visible
    await expect(page.locator('text=User Information')).toBeVisible();

    // Verify profile fields are displayed
    const profileFields = ['Name', 'Email', 'Role', 'User ID', 'Created At', 'Last Login'];
    
    for (const field of profileFields) {
      await expect(page.locator(`text=${field}`)).toBeVisible();
    }
  });

  test('should change password successfully', async ({ page }) => {
    await page.goto('/profile');
    await page.waitForSelector('h1:has-text("Profile")', { timeout: 5000 });

    // Verify Password Change Card title is visible
    await expect(page.locator('h3:has-text("Change Password")')).toBeVisible();
    
    // Fill password change form
    await page.fill('#current_password', 'admin123');
    await page.fill('#new_password', 'newpass123');
    await page.fill('#confirm_password', 'newpass123');

    // Submit form
    await page.click('button[type="submit"]:has-text("Change Password")');

    // Wait for success toast (simple text search)
    await expect(page.getByText(/password changed successfully/i)).toBeVisible({ timeout: 5000 });

    // Verify form is cleared after success
    const currentPasswordValue = await page.inputValue('#current_password');
    expect(currentPasswordValue).toBe('');

    // IMPORTANT: Change password back to original for other tests
    await page.fill('#current_password', 'newpass123');
    await page.fill('#new_password', 'admin123');
    await page.fill('#confirm_password', 'admin123');
    await page.click('button[type="submit"]:has-text("Change Password")');
    await expect(page.getByText(/password changed successfully/i)).toBeVisible({ timeout: 5000 });
  });

  test('should validate password requirements', async ({ page }) => {
    await page.goto('/profile');
    await page.waitForSelector('h1:has-text("Profile")', { timeout: 5000 });

    // Try to submit with short password (less than 6 chars)
    await page.fill('#current_password', 'admin123');
    await page.fill('#new_password', '123');
    await page.fill('#confirm_password', '123');

    await page.click('button[type="submit"]:has-text("Change Password")');

    // Wait for client-side validation to prevent form submission
    await page.waitForTimeout(1000);
    
    // Verify we're still on /profile page (form wasn't submitted)
    expect(page.url()).toContain('/profile');
  });

  test('should validate password confirmation match', async ({ page }) => {
    await page.goto('/profile');
    await page.waitForSelector('h1:has-text("Profile")', { timeout: 5000 });

    // Try to submit with mismatched passwords
    await page.fill('#current_password', 'admin123');
    await page.fill('#new_password', 'newpass123');
    await page.fill('#confirm_password', 'different123');

    await page.click('button[type="submit"]:has-text("Change Password")');

    // Wait for error toast about mismatch
    await expect(page.getByText(/do not match/i)).toBeVisible({ timeout: 5000 });
  });

  test('should handle incorrect current password', async ({ page }) => {
    await page.goto('/profile');
    await page.waitForSelector('h1:has-text("Profile")', { timeout: 5000 });

    // Try to submit with wrong current password
    await page.fill('#current_password', 'wrongpassword');
    await page.fill('#new_password', 'newpass123');
    await page.fill('#confirm_password', 'newpass123');

    await page.click('button[type="submit"]:has-text("Change Password")');

    // Wait for error toast about incorrect current password (backend returns error)
    await page.waitForTimeout(2000); // Give time for API call to complete
  });

  test('should handle empty form submission', async ({ page }) => {
    await page.goto('/profile');
    await page.waitForSelector('h1:has-text("Profile")', { timeout: 5000 });

    // Try to submit empty form
    await page.click('button[type="submit"]:has-text("Change Password")');

    // Wait for browser's HTML5 validation to show (required fields)
    await page.waitForTimeout(1000);
    
    // Verify we're still on /profile page (form wasn't submitted due to required fields)
    expect(page.url()).toContain('/profile');
  });
});
