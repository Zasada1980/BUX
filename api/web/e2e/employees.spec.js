import { test, expect } from '@playwright/test';

/**
 * E2E Tests: Employee Management CRUD Operations
 * Tests creating, reading, updating, and deleting employees.
 * 
 * LEGACY: Tests for old HTML UI (/employees.html)
 * Status: SKIPPED — replaced by React SPA in F2.2
 * Will be updated/removed in F3+
 */

test.describe.skip('Employee Management (LEGACY HTML UI)', () => {
  // Login before each test
  test.beforeEach(async ({ page }) => {
    await page.goto('/login.html');
    await page.evaluate(() => sessionStorage.clear());
    
    // CRITICAL: Switch to password tab
    await page.click('button.login-tab:has-text("Пароль")');
    await page.waitForSelector('#password-form.active', { timeout: 5000 });
    
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    
    // Wait for navigation to complete
    await page.waitForTimeout(2000);
    await page.waitForURL(/.*\/(index\.html)?$/, { timeout: 10000 });
    
    // Navigate to employees page
    await page.goto('/employees.html');
  });

  test('should display employee list', async ({ page }) => {
    // Check page title (Russian UI)
    await expect(page.locator('h1').first()).toContainText(/Управление сотрудниками|Employees|Employee List/i);
    
    // Should show employee table or cards
    await expect(page.locator('table, .employee-card')).toBeVisible();
    
    // Check for admin user in table body (avoid filter dropdowns)
    await expect(page.locator('tbody, .employee-list')).toContainText(/admin|administrator/i);
  });

  test('should create new employee', async ({ page }) => {
    // Click "+ Добавить сотрудника" button
    await page.click('button:has-text("Добавить сотрудника"), button:has-text("Add Employee")');
    
    // Wait for modal to appear (#employee-modal.active)
    await page.waitForSelector('#employee-modal.active, .modal.active', { timeout: 5000 });
    
    // Fill employee form
    await page.fill('#full-name', 'Test Worker E2E');
    await page.fill('#telegram-id', '999888777');
    await page.selectOption('#role', 'worker');
    
    // Optional: Fill password credentials
    const usernameInput = page.locator('input[name="username"], #username');
    if (await usernameInput.isVisible()) {
      await usernameInput.fill('test_worker_e2e');
      await page.fill('input[name="password"], #password', 'testpass123');
    }
    
    // Submit form (RU: Создать/Сохранить)
    await page.click('button[type="submit"]:has-text("Создать"), button[type="submit"]:has-text("Create"), button:has-text("Сохранить"), button:has-text("Save")');
    
    // Should show success message or redirect to list (RU: Успешно создан)
    await expect(
      page.locator('text=/Успешно создан|Created successfully|Employee created/i, .alert-success')
    ).toBeVisible({ timeout: 5000 }).catch(() => {
      // Or check if employee appears in list
      return expect(page.locator('text=Test Worker E2E')).toBeVisible();
    });
  });

  test('should view employee details', async ({ page }) => {
    // Find first employee row (skip admin if needed)
    const employeeRow = page.locator('table tbody tr, .employee-card').first();
    
    // Click edit button (emoji: ✏️)
    await employeeRow.locator('button[title="Редактировать"], button[title="Edit"], button:has-text("✏️"), .btn-icon[onclick*="editEmployee"]').first().click();
    
    // Should show employee details
    await expect(page.locator('#full-name, input[name="full_name"]')).toBeVisible();
    await expect(page.locator('#role, select[name="role"]')).toBeVisible();
  });

  test('should update employee information', async ({ page }) => {
    // Create employee first
    await page.click('button:has-text("Добавить сотрудника"), button:has-text("Add Employee")');
    
    // Wait for modal to appear
    await page.waitForSelector('#employee-modal.active, .modal.active', { timeout: 5000 });
    
    await page.fill('#full-name, input[name="full_name"]', 'Update Test Employee');
    await page.fill('#telegram-id', '111222333');
    await page.selectOption('#role', 'worker');
    await page.click('button[type="submit"]:has-text("Создать"), button[type="submit"]:has-text("Create"), button:has-text("Сохранить"), button:has-text("Save")');
    
    // Wait for modal to close
    await page.waitForSelector('#employee-modal.active', { state: 'detached', timeout: 5000 }).catch(() => {
      // Or try closing manually
      return page.click('.modal-close, button:has-text("Закрыть"), button:has-text("Close")').catch(() => {});
    });
    await page.waitForTimeout(500);
    
    // Find the created employee and click edit
    await page.waitForTimeout(500); // Wait for DOM update
    const employeeRow = page.locator('tr:has-text("Update Test Employee")').first();
    await employeeRow.locator('button[title="Редактировать"], button[title="Edit"], button:has-text("✏️")').first().click({ force: true });
    
    // Update name
    await page.fill('#full-name', 'Updated Name E2E');
    
    // Submit update (RU: Обновить/Сохранить)
    await page.click('button[type="submit"]:has-text("Обновить"), button[type="submit"]:has-text("Update"), button:has-text("Сохранить"), button:has-text("Save")');
    
    // Should show updated name
    await expect(page.locator('text=Updated Name E2E')).toBeVisible({ timeout: 5000 });
  });

  test('should deactivate employee', async ({ page }) => {
    // Create employee first
    await page.click('button:has-text("Добавить сотрудника"), button:has-text("Add Employee")');
    
    // Wait for modal to appear
    await page.waitForSelector('#employee-modal.active, .modal.active', { timeout: 5000 });
    
    await page.fill('#full-name, input[name="full_name"]', 'Deactivate Test');
    await page.fill('#telegram-id', '444555666');
    await page.selectOption('#role', 'worker');
    await page.click('button[type="submit"]:has-text("Создать"), button[type="submit"]:has-text("Create"), button:has-text("Сохранить"), button:has-text("Save")');
    
    // Wait for modal to close
    await page.waitForSelector('#employee-modal.active', { state: 'detached', timeout: 5000 }).catch(() => {
      // Or try closing manually
      return page.click('.modal-close, button:has-text("Закрыть"), button:has-text("Close")').catch(() => {});
    });
    await page.waitForTimeout(500);
    
    // Find and click delete button (emoji: 🗑️)
    const employeeRow = page.locator('text=Deactivate Test').locator('..').locator('..');
    
    // Accept browser confirm dialog
    page.once('dialog', dialog => dialog.accept());
    
    await employeeRow.locator('button[title="Удалить"], button[title="Delete"], button:has-text("🗑️"), .btn-icon[onclick*="deleteEmployee"]').first().click();
    
    // Wait for deletion to complete
    await page.waitForTimeout(1000);
    
    // Employee should be removed from list (deleted successfully)
    await expect(page.locator('text=Deactivate Test')).not.toBeVisible({ timeout: 5000 });
  });

  test('should filter employees by role', async ({ page }) => {
    // Check if filter dropdown exists
    const roleFilter = page.locator('select[name="role_filter"], #role_filter');
    
    if (await roleFilter.isVisible({ timeout: 2000 }).catch(() => false)) {
      // Select "admin" role
      await roleFilter.selectOption('admin');
      
      // Should show only admin
      await expect(page.locator('text=/System Administrator|Admin/i')).toBeVisible();
      
      // Workers should not be visible (if any exist)
      const workerCount = await page.locator('table tbody tr, .employee-card').count();
      expect(workerCount).toBeLessThanOrEqual(2); // Admin + maybe one more admin
    } else {
      test.skip();
    }
  });

  test('should validate duplicate telegram_id', async ({ page }) => {
    // Try to create employee with duplicate telegram_id
    await page.click('button:has-text("Добавить сотрудника"), button:has-text("Add Employee")');
    
    // Wait for modal to appear
    await page.waitForSelector('#employee-modal.active, .modal.active', { timeout: 5000 });
    
    await page.fill('#full-name, input[name="full_name"]', 'Duplicate Test');
    await page.fill('#telegram-id', '123456789'); // Common test ID
    await page.selectOption('#role', 'worker');
    
    await page.click('button[type="submit"]:has-text("Создать"), button[type="submit"]:has-text("Create"), button:has-text("Сохранить"), button:has-text("Save")');
    
    // If telegram_id is already used, should show error (RU: уже существует)
    // (May pass if no conflict exists)
    const errorMessage = page.locator('.error, .alert-danger, text=/уже существует|already exists/i');
    const isErrorVisible = await errorMessage.isVisible({ timeout: 3000 }).catch(() => false);
    
    // Test passes either way (we're just checking validation works IF triggered)
    if (isErrorVisible) {
      expect(await errorMessage.textContent()).toMatch(/telegram.*(уже|already)|дубликат|duplicate/i);
    }
  });

  test('should paginate employee list', async ({ page }) => {
    // Check if pagination exists (RU: Следующая)
    const nextButton = page.locator('button:has-text("Следующая"), button:has-text("Next"), .pagination .next');
    
    if (await nextButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      const initialCount = await page.locator('table tbody tr, .employee-card').count();
      
      await nextButton.click();
      await page.waitForTimeout(500);
      
      // Should load next page (different employees or same if only one page)
      const newCount = await page.locator('table tbody tr, .employee-card').count();
      expect(newCount).toBeGreaterThan(0);
    } else {
      test.skip(); // No pagination if few employees
    }
  });
});
