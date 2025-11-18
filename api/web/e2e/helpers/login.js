/**
 * Playwright Helper: Login Utilities
 * Reusable functions for authentication in E2E tests.
 */

/**
 * Login as admin user.
 * @param {import('@playwright/test').Page} page - Playwright page
 * @returns {Promise<void>}
 */
export async function loginAsAdmin(page) {
  await page.goto('/login.html');
  await page.evaluate(() => sessionStorage.clear());
  
  // Switch to password tab
  await page.click('button.login-tab:has-text("Пароль")');
  await page.waitForSelector('#password-form.active', { timeout: 5000 });
  
  await page.fill('input[name="username"]', 'admin');
  await page.fill('input[name="password"]', 'admin123');
  await page.click('button[type="submit"]');
  
  // Wait for redirect (either / or /index.html)
  await page.waitForURL(/.*\/(index\.html)?$/, { timeout: 5000 });
}

/**
 * Login as specific user.
 * @param {import('@playwright/test').Page} page - Playwright page
 * @param {string} username - Username
 * @param {string} password - Password
 * @returns {Promise<void>}
 */
export async function login(page, username, password) {
  await page.goto('/login.html');
  await page.evaluate(() => sessionStorage.clear());
  
  // Switch to password tab
  await page.click('button.login-tab:has-text("Пароль")');
  await page.waitForSelector('#password-form.active', { timeout: 5000 });
  
  await page.fill('input[name="username"]', username);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');
  
  await page.waitForURL(/.*\/(index\.html)?$/, { timeout: 5000 });
}

/**
 * Logout current user.
 * @param {import('@playwright/test').Page} page - Playwright page
 * @returns {Promise<void>}
 */
export async function logout(page) {
  const logoutButton = page.locator('button:has-text("Logout"), a:has-text("Logout"), #logout-btn');
  await logoutButton.click();
  
  await page.waitForURL(/.*login\.html/, { timeout: 5000 });
}

/**
 * Check if user is authenticated.
 * @param {import('@playwright/test').Page} page - Playwright page
 * @returns {Promise<boolean>}
 */
export async function isAuthenticated(page) {
  const token = await page.evaluate(() => sessionStorage.getItem('access_token'));
  return token !== null && token !== '';
}

/**
 * Get current access token.
 * @param {import('@playwright/test').Page} page - Playwright page
 * @returns {Promise<string|null>}
 */
export async function getAccessToken(page) {
  return await page.evaluate(() => sessionStorage.getItem('access_token'));
}
