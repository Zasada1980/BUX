import { test, expect, Page } from '@playwright/test';

test.describe('Login Debug', () => {
  test('should debug login page rendering', async ({ page }) => {
    // Capture console logs
    page.on('console', (msg) => {
      console.log('[BROWSER]', msg.type(), msg.text());
    });

    // Capture page errors
    page.on('pageerror', (error) => {
      console.error('[PAGE ERROR]', error.message);
    });

    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    // Take screenshot
    await page.screenshot({ path: 'test-results/login-debug.png', fullPage: true });

    // Check if inputs exist in DOM
    const usernameInput = await page.locator('input[name="username"]');
    const passwordInput = await page.locator('input[name="password"]');

    console.log('Username input count:', await usernameInput.count());
    console.log('Password input count:', await passwordInput.count());

    // Check visibility
    const isUsernameVisible = await usernameInput.isVisible().catch(() => false);
    const isPasswordVisible = await passwordInput.isVisible().catch(() => false);

    console.log('Username visible:', isUsernameVisible);
    console.log('Password visible:', isPasswordVisible);

    // Get computed styles
    if (await usernameInput.count() > 0) {
      const styles = await page.evaluate(() => {
        const input = document.querySelector('input[name="username"]');
        if (!input) return null;
        const computed = window.getComputedStyle(input);
        return {
          display: computed.display,
          visibility: computed.visibility,
          opacity: computed.opacity,
          width: computed.width,
          height: computed.height,
        };
      });
      console.log('Username input styles:', JSON.stringify(styles, null, 2));
    }

    // Get page HTML for inspection
    const bodyHTML = await page.locator('body').innerHTML();
    console.log('Body HTML length:', bodyHTML.length);
  });
});
