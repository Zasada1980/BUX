import { test } from '@playwright/test';

test('Check parent visibility', async ({ page }) => {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');

  const parentInfo = await page.evaluate(() => {
    const input = document.querySelector('input[name="username"]');
    if (!input) return null;

    const parents = [];
    let el: Element | null = input;
    while (el && el !== document.body) {
      const computed = window.getComputedStyle(el);
      parents.push({
        tag: el.tagName,
        class: el.className,
        display: computed.display,
        visibility: computed.visibility,
        opacity: computed.opacity,
        height: computed.height,
        overflow: computed.overflow,
      });
      el = el.parentElement;
    }
    return parents;
  });

  console.log('Parent chain:', JSON.stringify(parentInfo, null, 2));

  await page.screenshot({ path: 'test-results/login-full-page.png', fullPage: true });
});
