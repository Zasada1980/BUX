import { test, expect } from '@playwright/test';
import { loginAsAdmin } from './fixtures/auth';

test.describe('Scenario 8: Settings Management', () => {
  test('should load Settings page with General tab', async ({ page }) => {
    // F5.1: Settings refactored (Bot Menu removed, General/Backup/System working)
    // test.skip() removed after full cleanup

    // F4.5: Catch ALL console messages for detailed diagnostics
    const consoleMessages: Array<{type: string, text: string}> = [];
    page.on('console', msg => {
      consoleMessages.push({ type: msg.type(), text: msg.text() });
    });

    // F4.5: Minimal working scenario — verify General tab renders
    await loginAsAdmin(page); // This ends on /dashboard

    // F4.5 FIX: Navigate directly to Settings (skip Dashboard wait - it has its own errors)
    await page.goto('/settings', { waitUntil: 'domcontentloaded', timeout: 10000 });
    
    // Wait for page to stabilize (reduced from 2000ms to prevent timeout)
    await page.waitForTimeout(500);

    // DEBUG: Dump ALL console messages to find root cause
    console.log('[F4.5 CONSOLE DUMP] Total messages:', consoleMessages.length);
    consoleMessages.forEach((msg, i) => {
      console.log(`[F4.5 CONSOLE ${i}] [${msg.type}]`, msg.text.substring(0, 500));
    });

    // Verify page loaded (h1 title)
    const pageTitle = page.locator('h1:has-text("Настройки"), h1:has-text("Settings")');
    await expect(pageTitle).toBeVisible({ timeout: 5000 });

    // Find and click General tab
    const generalTab = page.locator('button:has-text("Общие"), [role="tab"]:has-text("Общие")').first();
    await expect(generalTab).toBeVisible({ timeout: 5000 });
    await generalTab.click();

    // Verify content is displayed (card title)
    const cardTitle = page.locator('text=/Общие настройки|General Settings/i');
    await expect(cardTitle).toBeVisible({ timeout: 3000 });

    // Verify company name field
    const companyField = page.locator('text=/Компания:|Company:/i');
    await expect(companyField).toBeVisible({ timeout: 3000 });

    // Verify no error UI
    const errorText = page.locator('text=/Ошибка загрузки|Failed to load/i');
    await expect(errorText).toHaveCount(0);

    console.log('[F4.5 Settings] General tab verification: PASS');
  });
});
