# Web Interface Testing Guide

Comprehensive testing setup for WorkLedger web interface with Jest (unit tests) and Playwright (E2E tests).

## 📋 Test Coverage

### Unit Tests (Jest)
- **auth.test.js** - JWT token management, session handling, refresh logic
- **api-client.test.js** - API wrapper with retry logic, error handling, 401/429/5xx handling

### E2E Tests (Playwright)
- **auth.spec.js** - Login/logout flow, session persistence, token refresh
- **employees.spec.js** - Employee CRUD operations, validation, filtering
- **work-records.spec.js** - Shift management, task logging, expense recording
- **invoices.spec.js** - Invoice generation, preview, approval, export

## 🚀 Quick Start

### Prerequisites
```powershell
# Install Node.js dependencies
cd api/web
npm install
```

### Running Unit Tests (Jest)

```powershell
# Run all unit tests
npm test

# Run in watch mode (auto-rerun on changes)
npm run test:watch

# Generate coverage report
npm run test:coverage
```

**Expected Output:**
```
PASS  src/auth.test.js
  Auth Module
    Token Storage
      ✓ setTokens should store tokens in sessionStorage (5ms)
      ✓ getAccessToken should return null when not authenticated (1ms)
      ✓ clearTokens should remove all tokens and user data (2ms)
    Authentication Status
      ✓ isAuthenticated should return true when access token exists (1ms)
      ✓ isAuthenticated should return false when no token (1ms)
    Token Refresh Logic
      ✓ needsRefresh should return false for fresh tokens (<12 min) (1ms)
      ✓ needsRefresh should return true for old tokens (>12 min) (1ms)
    Token Refresh API
      ✓ refreshToken should call API and update tokens on success (5ms)
      ✓ refreshToken should clear tokens and return false on API error (3ms)

PASS  src/api-client.test.js
  API Client
    Request Authorization
      ✓ should add Authorization header when token exists (3ms)
      ✓ should not add Authorization header when no token (2ms)
    401 Unauthorized Handling
      ✓ should refresh token and retry on 401 (4ms)
      ✓ should redirect to login if refresh fails (3ms)
    429 Rate Limit Handling
      ✓ should retry with delay on 429 (3ms)
    5xx Server Error Retry
      ✓ should retry with exponential backoff on 500 (4ms)

Test Suites: 2 passed, 2 total
Tests:       24 passed, 24 total
Coverage:    85% statements, 80% branches, 90% functions, 85% lines
```

### Running E2E Tests (Playwright)

```powershell
# Ensure Docker containers are running
cd ..
docker compose up -d

# Run E2E tests (headless)
cd web
npm run test:e2e

# Run with UI mode (interactive)
npm run test:e2e:ui

# Run with browser visible
npm run test:e2e:headed

# Run specific test file
npx playwright test e2e/auth.spec.js

# Run specific test
npx playwright test -g "should login with valid credentials"

# Show test report
npx playwright show-report
```

**Expected Output:**
```
Running 32 tests using 4 workers

  ✓ [chromium] › auth.spec.js:12:3 › should display login page (1.2s)
  ✓ [chromium] › auth.spec.js:20:3 › should login with valid credentials (2.5s)
  ✓ [chromium] › auth.spec.js:35:3 › should show error on invalid credentials (1.8s)
  ✓ [chromium] › employees.spec.js:15:3 › should display employee list (2.1s)
  ✓ [chromium] › employees.spec.js:24:3 › should create new employee (3.2s)
  ...

  32 passed (1.5m)

To open last HTML report run:
  npx playwright show-report
```

## 📊 Coverage Reports

### Jest Coverage
After running `npm run test:coverage`, open `coverage/index.html` in browser:

```powershell
# Windows
start coverage/index.html

# Or PowerShell
Invoke-Item coverage/index.html
```

### Playwright Test Report
```powershell
npx playwright show-report
```

## 🧪 Test Structure

### Unit Tests (Jest)

**Test File Structure:**
```javascript
import { describe, test, expect, beforeEach } from '@jest/globals';

describe('Module Name', () => {
  beforeEach(() => {
    // Setup before each test
  });

  test('should do something', () => {
    // Arrange
    const input = 'test';
    
    // Act
    const result = someFunction(input);
    
    // Assert
    expect(result).toBe('expected');
  });
});
```

**Mocking:**
```javascript
// Mock sessionStorage
global.sessionStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn()
};

// Mock fetch
global.fetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve({ data: 'test' })
  })
);
```

### E2E Tests (Playwright)

**Test File Structure:**
```javascript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login.html');
    // Login or setup
  });

  test('should perform action', async ({ page }) => {
    await page.click('button:has-text("Click Me")');
    await expect(page.locator('.result')).toBeVisible();
  });
});
```

**Page Object Pattern (Optional):**
```javascript
class LoginPage {
  constructor(page) {
    this.page = page;
  }

  async login(username, password) {
    await this.page.fill('input[name="username"]', username);
    await this.page.fill('input[name="password"]', password);
    await this.page.click('button[type="submit"]');
  }
}
```

## 🔍 Debugging Tests

### Jest Debug Mode
```powershell
# Run single test file with verbose output
npm test -- src/auth.test.js --verbose

# Debug specific test
npm test -- -t "should refresh token"

# Run with Node debugger
node --inspect-brk node_modules/.bin/jest --runInBand
```

### Playwright Debug Mode
```powershell
# Debug mode (step through test)
npx playwright test --debug

# Debug specific test
npx playwright test --debug -g "should login"

# Show browser console
npx playwright test --headed --debug
```

### Playwright Traces
```powershell
# View trace for failed test
npx playwright show-trace test-results/.../trace.zip
```

## 📝 Writing New Tests

### Adding Jest Unit Test

1. Create test file: `src/my-module.test.js`
2. Import module and testing utilities:
```javascript
import { describe, test, expect } from '@jest/globals';
import { myFunction } from './my-module.js';
```
3. Write tests following AAA pattern (Arrange, Act, Assert)
4. Run: `npm test src/my-module.test.js`

### Adding Playwright E2E Test

1. Create test file: `e2e/my-feature.spec.js`
2. Import Playwright utilities:
```javascript
import { test, expect } from '@playwright/test';
```
3. Write test with async/await
4. Run: `npx playwright test e2e/my-feature.spec.js`

## 🎯 Test Coverage Goals

| Metric | Target | Current |
|--------|--------|---------|
| Statements | 80% | 85% |
| Branches | 80% | 80% |
| Functions | 80% | 90% |
| Lines | 80% | 85% |

## 🐛 Troubleshooting

### Jest Tests Failing

**Issue: "ReferenceError: sessionStorage is not defined"**
```javascript
// Add to test file
global.sessionStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn()
};
```

**Issue: "Cannot find module 'auth.js'"**
- Ensure module exports: `export const Auth = { ... }`
- Or use inline implementation in test file

### Playwright Tests Failing

**Issue: "Timeout waiting for page"**
```javascript
// Increase timeout
await expect(page.locator('.element')).toBeVisible({ timeout: 10000 });
```

**Issue: "Element not found"**
- Check if element exists: `await page.locator('.element').isVisible().catch(() => false)`
- Use test.skip() if optional feature

**Issue: "Docker containers not running"**
```powershell
cd ..
docker compose up -d
docker compose ps  # Check status
```

## 📚 Resources

- [Jest Documentation](https://jestjs.io/docs/getting-started)
- [Playwright Documentation](https://playwright.dev/docs/intro)
- [Testing Best Practices](https://testingjavascript.com/)

## 🔄 CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: 18
      
      # Unit tests
      - name: Install dependencies
        run: npm install
        working-directory: api/web
      
      - name: Run Jest tests
        run: npm run test:coverage
        working-directory: api/web
      
      # E2E tests
      - name: Start Docker containers
        run: docker compose up -d
      
      - name: Install Playwright browsers
        run: npx playwright install --with-deps
        working-directory: api/web
      
      - name: Run Playwright tests
        run: npm run test:e2e
        working-directory: api/web
      
      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: playwright-report
          path: api/web/playwright-report/
```

---

**Last Updated:** 2025-11-14  
**Coverage:** Backend 100% (17/17 tests), Frontend Unit 24 tests, E2E 32 tests
