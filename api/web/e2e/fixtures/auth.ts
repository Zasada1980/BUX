import { test as base, Page } from '@playwright/test';

/**
 * F4.3.3 FIX: Simplified E2E auth fixture for synchronous AuthContext
 * 
 * With synchronous initialization in AuthContext (lazy useState + readAuthFromStorage),
 * we no longer need excessive delays, waitForFunction checks, or custom event handling.
 * 
 * Login flow:
 * 1. Navigate to /login
 * 2. Fill credentials (admin/admin123)
 * 3. Submit form
 * 4. Wait for redirect to /dashboard
 * 
 * AuthContext initializes synchronously on first render, so auth state is immediately available.
 */

const ADMIN_CREDENTIALS = {
  username: 'admin',
  password: 'admin123',
};

async function loginAsAdmin(page: Page) {
  await page.goto('/login');
  
  // Wait for login form
  await page.waitForSelector('input[name="username"]', { timeout: 5000 });
  
  // Fill credentials
  await page.fill('input[name="username"]', ADMIN_CREDENTIALS.username);
  await page.fill('input[name="password"]', ADMIN_CREDENTIALS.password);
  
  // Submit form
  await page.click('button[type="submit"]');
  
  // Wait for API login call to complete
  await page.waitForResponse(response => 
    response.url().includes('/api/auth/login') && response.status() === 200,
    { timeout: 10000 }
  );
  
  // Wait for successful redirect to dashboard (after AuthContext processes token)
  await page.waitForURL('**/dashboard', { timeout: 10000 });
  
  // No excessive delays needed - AuthContext is synchronous now
}

export { loginAsAdmin };
