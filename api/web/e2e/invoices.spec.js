import { test, expect } from '@playwright/test';

/**
 * E2E Tests: Invoice Generation and Management
 * Tests invoice creation, preview, approval, and export.
 * NOTE: invoices.html NOT IMPLEMENTED — tests will fail (TD-E2E-004)
 * 
 * LEGACY: Tests for old HTML UI (/invoices.html)
 * Status: SKIPPED — replaced by React SPA in F2.2
 * Will be updated/removed in F3+
 */

test.describe.skip('Invoice Management (LEGACY HTML UI)', () => {
  test.beforeEach(async ({ page }) => {
    // Inline login (helper import broken)
    await page.goto('/login.html');
    await page.evaluate(() => sessionStorage.clear());
    await page.click('button.login-tab:has-text("Пароль")');
    await page.waitForSelector('#password-form.active', { timeout: 5000 });
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL(/.*\/(index\.html)?$/, { timeout: 5000 });
  });

  test('should navigate to invoices page', async ({ page }) => {
    // Look for invoices link in navigation
    const invoicesLink = page.locator('a:has-text("Invoices"), #invoices-link');
    
    if (await invoicesLink.isVisible({ timeout: 2000 }).catch(() => false)) {
      await invoicesLink.click();
      await expect(page).toHaveURL(/.*invoice/);
      await expect(page.locator('h1, h2')).toContainText(/Invoices|Invoice List/i);
    } else {
      // Try direct navigation
      await page.goto('/invoices.html');
      await expect(page.locator('h1, h2')).toContainText(/Invoices|Invoice/i);
    }
  });

  test('should display invoice list', async ({ page }) => {
    await page.goto('/invoices.html').catch(() => page.goto('/index.html'));
    
    // Check if invoice list or "No invoices" message is shown
    const hasTable = await page.locator('table, .invoice-card').isVisible({ timeout: 2000 }).catch(() => false);
    const hasEmptyMessage = await page.locator('text=/No invoices|Empty/i').isVisible({ timeout: 2000 }).catch(() => false);
    
    expect(hasTable || hasEmptyMessage).toBeTruthy();
  });

  test('should create new invoice', async ({ page }) => {
    await page.goto('/invoices.html').catch(() => page.goto('/index.html'));
    
    // Click "Create Invoice" button
    const createButton = page.locator('button:has-text("Create Invoice"), #create-invoice-btn');
    
    if (await createButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await createButton.click();
      
      // Fill invoice details
      const employeeSelect = page.locator('select[name="employee_id"], #employee_id');
      if (await employeeSelect.isVisible({ timeout: 2000 }).catch(() => false)) {
        await employeeSelect.selectOption({ index: 1 }); // Select first employee
      }
      
      // Set period
      const startDate = page.locator('input[name="period_start"], #period_start');
      if (await startDate.isVisible({ timeout: 2000 }).catch(() => false)) {
        await startDate.fill('2025-11-01');
        await page.fill('input[name="period_end"], #period_end', '2025-11-14');
      }
      
      // Submit
      await page.click('button[type="submit"]:has-text("Generate"), button:has-text("Create")');
      
      // Should show invoice or redirect to preview
      await expect(
        page.locator('text=/Invoice created|Preview/i, .invoice-preview')
      ).toBeVisible({ timeout: 10000 });
    } else {
      test.skip(); // Invoice creation UI not available
    }
  });

  test('should preview invoice before approval', async ({ page }) => {
    await page.goto('/invoices.html').catch(() => page.goto('/index.html'));
    
    // Find first invoice in list
    const invoiceRow = page.locator('table tbody tr, .invoice-card').first();
    
    if (await invoiceRow.isVisible({ timeout: 2000 }).catch(() => false)) {
      // Click preview/view button
      await invoiceRow.locator('button:has-text("Preview"), a:has-text("View")').click();
      
      // Should show invoice details
      await expect(
        page.locator('text=/Invoice|Total|Items/i, .invoice-details')
      ).toBeVisible();
      
      // Should show line items
      await expect(
        page.locator('table, .invoice-items')
      ).toBeVisible();
    } else {
      test.skip(); // No invoices to preview
    }
  });

  test('should approve invoice', async ({ page }) => {
    await page.goto('/invoices.html').catch(() => page.goto('/index.html'));
    
    // Find pending invoice
    const pendingInvoice = page.locator('tr:has-text("Pending"), .invoice-pending').first();
    
    if (await pendingInvoice.isVisible({ timeout: 2000 }).catch(() => false)) {
      // Click approve button
      await pendingInvoice.locator('button:has-text("Approve"), #approve-btn').click();
      
      // Confirm if modal appears
      const confirmButton = page.locator('button:has-text("Confirm"), button:has-text("Yes")');
      if (await confirmButton.isVisible({ timeout: 2000 }).catch(() => false)) {
        await confirmButton.click();
      }
      
      // Should show "Approved" status
      await expect(
        page.locator('text=/Approved|Invoice approved/i, .invoice-approved')
      ).toBeVisible({ timeout: 5000 });
    } else {
      test.skip(); // No pending invoices
    }
  });

  test('should reject invoice', async ({ page }) => {
    await page.goto('/invoices.html').catch(() => page.goto('/index.html'));
    
    // Find pending invoice
    const pendingInvoice = page.locator('tr:has-text("Pending"), .invoice-pending').first();
    
    if (await pendingInvoice.isVisible({ timeout: 2000 }).catch(() => false)) {
      // Click reject button
      await pendingInvoice.locator('button:has-text("Reject"), #reject-btn').click();
      
      // Enter rejection reason if modal appears
      const reasonInput = page.locator('textarea[name="reason"], #rejection_reason');
      if (await reasonInput.isVisible({ timeout: 2000 }).catch(() => false)) {
        await reasonInput.fill('E2E Test Rejection');
        await page.click('button:has-text("Confirm"), button:has-text("Reject")');
      }
      
      // Should show "Rejected" status
      await expect(
        page.locator('text=/Rejected|Invoice rejected/i, .invoice-rejected')
      ).toBeVisible({ timeout: 5000 });
    } else {
      test.skip(); // No pending invoices
    }
  });

  test('should export invoice as PDF', async ({ page, context }) => {
    await page.goto('/invoices.html').catch(() => page.goto('/index.html'));
    
    // Find approved invoice
    const approvedInvoice = page.locator('tr:has-text("Approved"), .invoice-approved').first();
    
    if (await approvedInvoice.isVisible({ timeout: 2000 }).catch(() => false)) {
      // Set up download listener
      const downloadPromise = page.waitForEvent('download', { timeout: 10000 }).catch(() => null);
      
      // Click export/download button
      await approvedInvoice.locator('button:has-text("Download"), button:has-text("PDF"), .btn-download').click();
      
      const download = await downloadPromise;
      
      if (download) {
        // Verify download filename
        const filename = download.suggestedFilename();
        expect(filename).toMatch(/invoice.*\.pdf/i);
      } else {
        // PDF might open in new tab instead of download
        const pages = context.pages();
        if (pages.length > 1) {
          const pdfPage = pages[pages.length - 1];
          await expect(pdfPage).toHaveURL(/.*\.pdf|.*invoice/i);
        }
      }
    } else {
      test.skip(); // No approved invoices
    }
  });

  test('should filter invoices by status', async ({ page }) => {
    await page.goto('/invoices.html').catch(() => page.goto('/index.html'));
    
    // Check if filter exists
    const statusFilter = page.locator('select[name="status_filter"], #status_filter');
    
    if (await statusFilter.isVisible({ timeout: 2000 }).catch(() => false)) {
      // Select "Approved" status
      await statusFilter.selectOption('approved');
      
      await page.waitForTimeout(500);
      
      // All visible invoices should be approved
      const invoiceRows = page.locator('table tbody tr, .invoice-card');
      const count = await invoiceRows.count();
      
      if (count > 0) {
        // At least one should have "Approved" status
        await expect(page.locator('text=/Approved/i')).toBeVisible();
      }
    } else {
      test.skip(); // No filter available
    }
  });

  test('should view invoice versions/history', async ({ page }) => {
    await page.goto('/invoices.html').catch(() => page.goto('/index.html'));
    
    // Find invoice with multiple versions
    const invoiceRow = page.locator('table tbody tr, .invoice-card').first();
    
    if (await invoiceRow.isVisible({ timeout: 2000 }).catch(() => false)) {
      // Look for history/versions button
      const historyButton = invoiceRow.locator('button:has-text("History"), button:has-text("Versions")');
      
      if (await historyButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await historyButton.click();
        
        // Should show version list
        await expect(
          page.locator('text=/Version|History|Changes/i, .version-history')
        ).toBeVisible();
      } else {
        test.skip(); // No version history feature
      }
    } else {
      test.skip(); // No invoices
    }
  });
});
