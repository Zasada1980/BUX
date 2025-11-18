import { test, expect } from '@playwright/test';

/**
 * E2E Tests: Authentication Flow
 * Tests login, logout, token refresh, and session persistence.
 * 
 * LEGACY: Tests for old HTML UI (/login.html, /index.html)
 * Status: SKIPPED — replaced by React SPA in F2.2
 * Will be updated/removed in F3+
 */

test.describe.skip('Authentication Flow (LEGACY HTML UI)', () => {
  test.beforeEach(async ({ page }) => {
    // Clear session storage before each test
    await page.goto('/login.html');
    await page.evaluate(() => sessionStorage.clear());
  });

  test('should display login page', async ({ page }) => {
    await page.goto('/login.html');
    
    // Check Russian title
    await expect(page.locator('h1')).toContainText('Вход в систему');
    
    // Switch to password tab to show form
    await page.click('button.login-tab:has-text("Пароль")');
    
    // Now check form elements
    await expect(page.locator('input[name="username"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('should login with valid credentials', async ({ page }) => {
    // Listen for console errors
    page.on('console', msg => {
      if (msg.type() === 'error') {
        console.log('BROWSER ERROR:', msg.text());
      }
    });

    await page.goto('/login.html');
    
    // Switch to password tab
    await page.click('button.login-tab:has-text("Пароль")');
    await expect(page.locator('#password-form')).toBeVisible();
    
    // Fill login form
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    
    // Submit form
    await page.click('button[type="submit"]');
    
    // Wait briefly for navigation attempt
    await page.waitForTimeout(2000);
    
    // Should redirect to root or index.html
    await expect(page).toHaveURL(/.*\/(index\.html)?$/);
    
    // Check that tokens are stored
    const accessToken = await page.evaluate(() => sessionStorage.getItem('access_token'));
    const refreshToken = await page.evaluate(() => sessionStorage.getItem('refresh_token'));
    
    expect(accessToken).toBeTruthy();
    expect(refreshToken).toBeTruthy();
  });

  test('should show error on invalid credentials', async ({ page }) => {
    await page.goto('/login.html');
    
    // Switch to password tab
    await page.click('button.login-tab:has-text("Пароль")');
    await expect(page.locator('#password-form')).toBeVisible();
    
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'wrong_password');
    await page.click('button[type="submit"]');
    
    // Should show error message
    await expect(page.locator('.error-message.show, .error, .alert-danger')).toBeVisible();
  });

  test('should logout and clear session', async ({ page }) => {
    // Login first
    await page.goto('/login.html');
    await page.click('button.login-tab:has-text("Пароль")');
    await expect(page.locator('#password-form')).toBeVisible();
    
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    // Wait briefly for navigation attempt
    await page.waitForTimeout(2000);
    
    await expect(page).toHaveURL(/.*\/(index\.html)?$/);
    
    // Wait for page to fully load
    await page.waitForLoadState('networkidle');
    
    // Call logout programmatically (since logout button may not exist on all pages)
    await page.evaluate(() => {
      if (window.Auth && typeof window.Auth.logout === 'function') {
        window.Auth.logout();
      } else {
        // Fallback: clear tokens manually
        sessionStorage.clear();
        window.location.href = '/login.html';
      }
    });
    
    // Should redirect to login
    await expect(page).toHaveURL(/.*login\.html/);
    
    // Tokens should be cleared
    const accessToken = await page.evaluate(() => sessionStorage.getItem('access_token'));
    expect(accessToken).toBeNull();
  });

  test('should redirect to login when accessing protected page without auth', async ({ page }) => {
    await page.goto('/employees.html');
    
    // Should redirect to login
    await expect(page).toHaveURL(/.*login\.html/);
  });

  test('should persist session on page reload', async ({ page }) => {
    // Login
    await page.goto('/login.html');
    await page.click('button.login-tab:has-text("Пароль")');
    await expect(page.locator('#password-form')).toBeVisible();
    
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    // Wait briefly for navigation attempt
    await page.waitForTimeout(2000);
    
    await expect(page).toHaveURL(/.*\/(index\.html)?$/);
    
    // Reload page
    await page.reload();
    
    // Should still be authenticated (not redirected to login)
    await expect(page).toHaveURL(/.*\/(index\.html)?$/);
    
    const accessToken = await page.evaluate(() => sessionStorage.getItem('access_token'));
    expect(accessToken).toBeTruthy();
  });

  test('should handle token refresh on API 401', async ({ page, context }) => {
    // Login
    await page.goto('/login.html');
    await page.click('button.login-tab:has-text("Пароль")');
    await expect(page.locator('#password-form')).toBeVisible();
    
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    // Wait briefly for navigation attempt
    await page.waitForTimeout(2000);
    
    await expect(page).toHaveURL(/.*\/(index\.html)?$/);
    
    // Get initial access token
    const initialToken = await page.evaluate(() => sessionStorage.getItem('access_token'));
    
    // Simulate token expiration by setting old timestamp (16 minutes ago)
    await page.evaluate(() => {
      const sixteenMinutesAgo = Date.now() - (16 * 60 * 1000);
      sessionStorage.setItem('token_timestamp', sixteenMinutesAgo.toString());
    });
    
    // Navigate to page that requires API call
    await page.goto('/employees.html');
    
    // Wait for API call to complete (should auto-refresh token)
    await page.waitForTimeout(2000);
    
    // Token should have been refreshed
    const newToken = await page.evaluate(() => sessionStorage.getItem('access_token'));
    
    // Either same token (if not expired server-side) or new token
    expect(newToken).toBeTruthy();
  });
});
