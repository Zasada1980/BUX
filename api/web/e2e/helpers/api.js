/**
 * Playwright Helper: API Utilities
 * Reusable functions for API interactions in E2E tests.
 */

/**
 * Make authenticated API request.
 * @param {import('@playwright/test').Page} page - Playwright page
 * @param {string} endpoint - API endpoint (e.g., '/api/employees')
 * @param {object} options - Fetch options
 * @returns {Promise<any>} - Response data
 */
export async function apiRequest(page, endpoint, options = {}) {
  return await page.evaluate(async ({ endpoint, options }) => {
    const token = sessionStorage.getItem('access_token');
    
    const response = await fetch(endpoint, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers
      },
      body: options.body ? JSON.stringify(options.body) : undefined
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Request failed');
    }
    
    return response.json();
  }, { endpoint, options });
}

/**
 * Create employee via API.
 * @param {import('@playwright/test').Page} page - Playwright page
 * @param {object} employeeData - Employee data
 * @returns {Promise<object>} - Created employee
 */
export async function createEmployee(page, employeeData) {
  return await apiRequest(page, '/api/employees', {
    method: 'POST',
    body: {
      telegram_id: Math.floor(Date.now() / 1000), // Unique ID
      full_name: 'Test Employee',
      role: 'worker',
      ...employeeData
    }
  });
}

/**
 * Delete employee via API.
 * @param {import('@playwright/test').Page} page - Playwright page
 * @param {number} employeeId - Employee ID
 * @returns {Promise<void>}
 */
export async function deleteEmployee(page, employeeId) {
  await page.evaluate(async ({ employeeId }) => {
    const token = sessionStorage.getItem('access_token');
    
    const response = await fetch(`/api/employees/${employeeId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (!response.ok && response.status !== 204) {
      throw new Error('Delete failed');
    }
  }, { employeeId });
}

/**
 * Get all employees via API.
 * @param {import('@playwright/test').Page} page - Playwright page
 * @returns {Promise<array>} - List of employees
 */
export async function getEmployees(page) {
  const data = await apiRequest(page, '/api/employees');
  return data.employees || data;
}

/**
 * Clean up test data (delete employees created during test).
 * @param {import('@playwright/test').Page} page - Playwright page
 * @param {array<number>} employeeIds - Array of employee IDs to delete
 * @returns {Promise<void>}
 */
export async function cleanupEmployees(page, employeeIds) {
  for (const id of employeeIds) {
    try {
      await deleteEmployee(page, id);
    } catch (error) {
      console.error(`Failed to cleanup employee ${id}:`, error);
    }
  }
}
