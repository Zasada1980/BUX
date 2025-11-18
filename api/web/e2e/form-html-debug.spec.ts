import { test } from '@playwright/test';

test('Extract full form HTML', async ({ page }) => {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');

  const formHTML = await page.locator('.login-form').innerHTML();
  console.log('=== FORM HTML ===');
  console.log(formHTML);

  const allClasses = await page.evaluate(() => {
    const loginForm = document.querySelector('.login-form');
    return {
      formClasses: loginForm?.className,
      computedDisplay: window.getComputedStyle(loginForm!).display,
      allStylesheets: Array.from(document.styleSheets).map((s: any) => s.href),
    };
  });
  console.log('=== CLASS INFO ===');
  console.log(JSON.stringify(allClasses, null, 2));
});
