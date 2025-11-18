import { test, expect } from '@playwright/test';

/**
 * E2E Tests: Work Records and Shift Management
 * Tests shift start/end, task logging, and expense recording.
 * 
 * LEGACY: Tests for old HTML UI (/work-records.html)
 * Status: SKIPPED — replaced by React SPA in F2.2
 * Will be updated/removed in F3+
 */

test.describe.skip('Work Records Management (LEGACY HTML UI)', () => {
  test.beforeEach(async ({ page }) => {
    // Login inline (helper import broken with ES modules)
    await page.goto('/login.html');
    await page.evaluate(() => sessionStorage.clear());
    await page.click('button.login-tab:has-text("Пароль")');
    await page.waitForSelector('#password-form.active', { timeout: 5000 });
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/.*\/(index\.html)?$/, { timeout: 5000 });
  });

  test('should display work records dashboard', async ({ page }) => {
    await page.goto('/index.html');
    
    // Check for shift status or work records section
    await expect(
      page.locator('text=/Current Shift|Work Records|Dashboard/i')
    ).toBeVisible();
  });

  test('should start work shift', async ({ page }) => {
    await page.goto('/index.html');
    
    // Look for "Start Shift" button
    const startButton = page.locator('button:has-text("Start Shift"), #start-shift-btn');
    
    if (await startButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await startButton.click();
      
      // Should show "Shift Started" or disable button
      await expect(
        page.locator('text=/Shift started|Active shift/i, button:has-text("End Shift")')
      ).toBeVisible({ timeout: 5000 });
    } else {
      // Shift already active
      await expect(
        page.locator('text=/Active|In progress/i, button:has-text("End Shift")')
      ).toBeVisible();
    }
  });

  test('should log task during shift', async ({ page }) => {
    await page.goto('/index.html');
    
    // Ensure shift is active
    const startButton = page.locator('button:has-text("Start Shift")');
    if (await startButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await startButton.click();
      await page.waitForTimeout(1000);
    }
    
    // Look for task logging UI
    const addTaskButton = page.locator('button:has-text("Add Task"), #add-task-btn');
    
    if (await addTaskButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await addTaskButton.click();
      
      // Fill task form
      await page.fill('textarea[name="description"], #task_description', 'E2E Test Task');
      await page.fill('input[name="quantity"], #task_quantity', '5');
      
      // Submit
      await page.click('button[type="submit"]:has-text("Add"), button:has-text("Save Task")');
      
      // Should show task in list
      await expect(page.locator('text=E2E Test Task')).toBeVisible({ timeout: 5000 });
    } else {
      test.skip(); // Task logging UI not available
    }
  });

  test('should record expense during shift', async ({ page }) => {
    await page.goto('/index.html');
    
    // Ensure shift is active
    const startButton = page.locator('button:has-text("Start Shift")');
    if (await startButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await startButton.click();
      await page.waitForTimeout(1000);
    }
    
    // Look for expense recording UI
    const addExpenseButton = page.locator('button:has-text("Add Expense"), #add-expense-btn');
    
    if (await addExpenseButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await addExpenseButton.click();
      
      // Fill expense form
      await page.fill('input[name="amount"], #expense_amount', '50.00');
      await page.selectOption('select[name="category"], #expense_category', 'transport');
      await page.fill('textarea[name="description"], #expense_description', 'E2E Test Expense');
      
      // Submit
      await page.click('button[type="submit"]:has-text("Add"), button:has-text("Save Expense")');
      
      // Should show expense in list
      await expect(page.locator('text=E2E Test Expense')).toBeVisible({ timeout: 5000 });
    } else {
      test.skip(); // Expense recording UI not available
    }
  });

  test('should end work shift', async ({ page }) => {
    await page.goto('/index.html');
    
    // Ensure shift is active
    const startButton = page.locator('button:has-text("Start Shift")');
    if (await startButton.isVisible({ timeout: 1000 }).catch(() => false)) {
      await startButton.click();
      await page.waitForTimeout(1000);
    }
    
    // End shift
    const endButton = page.locator('button:has-text("End Shift"), #end-shift-btn');
    await expect(endButton).toBeVisible({ timeout: 5000 });
    
    await endButton.click();
    
    // Confirm if modal appears
    const confirmButton = page.locator('button:has-text("Confirm"), button:has-text("Yes")');
    if (await confirmButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await confirmButton.click();
    }
    
    // Should show "Shift Ended" or "Start Shift" button available again
    await expect(
      page.locator('text=/Shift ended|No active shift/i, button:has-text("Start Shift")')
    ).toBeVisible({ timeout: 5000 });
  });

  test('should view shift history', async ({ page }) => {
    await page.goto('/index.html');
    
    // Look for history/reports section
    const historyLink = page.locator('a:has-text("History"), button:has-text("View History"), #shift-history');
    
    if (await historyLink.isVisible({ timeout: 2000 }).catch(() => false)) {
      await historyLink.click();
      
      // Should show list of past shifts
      await expect(
        page.locator('table, .shift-history-list, text=/Shift History|Past Shifts/i')
      ).toBeVisible();
    } else {
      test.skip(); // History UI not available
    }
  });
});
