# 🤖 COPILOT FIX TASKS — Test Failures Audit 2025-11-19

**Date**: 2025-11-19 10:48:25  
**Branch**: `fix/test-failures-audit-2025-11-19`  
**Status**: 🔴 CRITICAL — CI/CD Pipeline Blocked  
**Estimated Time**: 2-4 hours

---

## 📊 EXECUTIVE SUMMARY

**Current State**:
- ❌ 16 out of 17 recent workflow runs FAILED
- ❌ 5 critical unit tests failing (SQLAlchemy mapping error)
- ❌ 2 Copilot workflows broken (autofind config issues)
- ⚠️ E2E tests partially skipped (legacy HTML UI → React migration incomplete)

**Impact**:
- 🚫 Cannot merge PRs (CI checks failing)
- 🚫 No test coverage validation
- 🚫 Potential production bugs undetected

---

## 🎯 TASK 1: FIX SQLALCHEMY EMPLOYEE MODEL MAPPING

### Priority: 🔴 CRITICAL
### Files to modify:
- `api/models/employee.py` (or wherever Employee model is defined)
- Create new Alembic migration
- `api/tests/test_employees.py` (verify fix)

### Problem:
```
sqlalchemy.orm.exc.UnmappedColumnError: No column users.id is configured on mapper Mapper[Employee(users)]
Can't execute sync rule for source column 'users.id'; mapper 'Mapper[Employee(users)]' does not map this column.
```

**Failed Tests**:
1. `api/tests/test_employees.py::test_create_employee`
2. `api/tests/test_employees.py::test_update_employee`
3. `api/tests/test_employees.py::test_soft_delete_employee`
4. `api/tests/test_employees.py::test_rbac_admin_can_create`
5. `api/tests/test_employees.py::test_duplicate_username`

### Root Cause:
The `Employee` model is mapped to the `users` table, but the primary key column `id` is not explicitly defined in the SQLAlchemy model.

### Action Items:

#### Step 1: Locate Employee Model
```bash
# Find the Employee model definition
find api -name "*.py" -type f -exec grep -l "class Employee" {} \;
```

**Expected file**: `api/models/employee.py` or `api/models/user.py`

#### Step 2: Fix Model Definition
Add explicit primary key and ensure proper column mapping:

```python
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from api.database import Base

class Employee(Base):
    __tablename__ = 'users'
    
    # ✅ REQUIRED: Explicit primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Existing columns (verify against actual schema)
    telegram_id = Column(Integer, unique=True, nullable=False)
    telegram_username = Column(String, nullable=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    active = Column(Integer, default=1)  # or Boolean if schema uses INTEGER
    
    # ✅ FIX: If there's a relationship with AuthCredential, specify foreign_keys
    # Example (adjust based on actual schema):
    # auth_credentials = relationship(
    #     "AuthCredential",
    #     back_populates="employee",
    #     foreign_keys="[AuthCredential.employee_id]"
    # )
```

#### Step 3: Verify Database Schema
```bash
# Check actual table schema
sqlite3 db/shifts.db ".schema users"
```

**Expected output**:
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    telegram_username TEXT,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    active INTEGER DEFAULT 1
);
```

If schema differs, update model to match.

#### Step 4: Create Alembic Migration
```bash
# Generate migration
alembic revision --autogenerate -m "fix: explicit Employee model primary key mapping"

# Review generated migration in db/alembic/versions/
# Ensure it doesn't try to recreate existing columns

# Apply migration
alembic upgrade head
```

#### Step 5: Run Tests
```bash
# Set test database
export DB_PATH="db/shifts.test.db"

# Reset test DB
rm -f db/shifts.test.db
alembic upgrade head

# Seed test data
python -m api.seeds.seed_e2e_minimal

# Run failing tests
pytest api/tests/test_employees.py::test_create_employee -v
pytest api/tests/test_employees.py::test_update_employee -v
pytest api/tests/test_employees.py::test_soft_delete_employee -v
pytest api/tests/test_employees.py::test_rbac_admin_can_create -v
pytest api/tests/test_employees.py::test_duplicate_username -v

# Run all employee tests
pytest api/tests/test_employees.py -v
```

**Expected result**: All 5 tests should PASS ✅

#### Step 6: Verify CI Workflow
```bash
# Push changes to trigger CI
git add api/models/
git add db/alembic/versions/
git commit -m "fix: SQLAlchemy Employee model explicit primary key mapping"
git push origin fix/test-failures-audit-2025-11-19
```

**Success Criteria**:
- ✅ All 5 employee tests pass locally
- ✅ GitHub Actions CI run passes
- ✅ No new Alembic migration conflicts

---

## 🎯 TASK 2: FIX OR DISABLE COPILOT WORKFLOWS

### Priority: 🟡 HIGH
### Files to modify:
- `.github/workflows/copilot-pull-request-reviewer.yml` (or dynamic workflow)
- `.github/workflows/copilot-swe-agent.yml` (or dynamic workflow)

### Problem:
```
Error getting common flags: diff references file 'rules' that is not present in repo
fatal: unable to access 'https://github.com/Zasada1980/BUX/': The requested URL returned error: 500
Error: Branch copilot/sub-pr-2 does not exist in repo Zasada1980/BUX
```

**Failed Workflows**:
1. Copilot code review (run 19480058086)
2. Addressing comment on PR #3 (run 19480484655)

### Root Cause:
- Missing `rules` file for autofind configuration
- GitHub API 500 errors (intermittent)
- Non-existent branch references

### Action Items:

#### Option A: Temporary Disable (RECOMMENDED)
```bash
# Rename workflow files to disable
mv .github/workflows/copilot-pull-request-reviewer.yml .github/workflows/copilot-pull-request-reviewer.yml.disabled
mv .github/workflows/copilot-swe-agent.yml .github/workflows/copilot-swe-agent.yml.disabled

# Or if workflows are in dynamic/ folder:
find .github/workflows/dynamic -name "*copilot*" -type f -exec mv {} {}.disabled \;
```

#### Option B: Fix Configuration
If you want to keep Copilot workflows:

1. **Create missing `rules` file**:
```bash
# Create autofind rules file
cat > rules << 'EOF'
# Autofind rules for Copilot code review
# Add your project-specific rules here
EOF

git add rules
```

2. **Add error handling to workflow**:
```yaml
# In .github/workflows/copilot-*.yml
- name: Run Copilot Review
  continue-on-error: true  # ← Add this to prevent blocking CI
  run: |
    # ... existing steps
```

3. **Add retry logic**:
```yaml
- name: Clone repository
  uses: nick-fields/retry@v2
  with:
    timeout_minutes: 5
    max_attempts: 3
    retry_on: error
    command: |
      git clone -b ${{ github.head_ref }} ...
```

**Recommendation**: Choose Option A for now, revisit Copilot setup in separate task.

---

## 🎯 TASK 3: UPDATE E2E TESTS (REACT MIGRATION)

### Priority: 🟢 MEDIUM
### Files to modify:
- `api/web/e2e/auth.spec.js` (remove `.skip`)
- `api/web/e2e/employees.spec.js`
- `api/web/e2e/work-records.spec.js`
- `api/web/e2e/invoices.spec.js`

### Problem:
Many E2E tests are skipped with `.skip` due to legacy HTML UI → React SPA migration:

```javascript
test.describe.skip('Authentication Flow (LEGACY HTML UI)', () => {
  // Tests skipped...
});
```

### Action Items:

#### Step 1: Audit Skipped Tests
```bash
cd api/web/e2e
grep -r "test.describe.skip\|test.skip" . --include="*.js" --include="*.ts"
```

#### Step 2: Identify React Components
Check if React SPA login page exists:
```bash
# Find React login component
find api/web/src -name "*Login*" -o -name "*Auth*"
```

#### Step 3: Update Test Selectors
For React SPA, update selectors from:
```javascript
// OLD (HTML)
await page.goto('/login.html');
await page.click('button.login-tab:has-text("Пароль")');
await page.fill('input[name="username"]', 'admin');
```

To:
```javascript
// NEW (React)
await page.goto('/login');
await page.fill('input[name="username"]', 'admin');
await page.fill('input[name="password"]', 'admin123');
await page.click('button[type="submit"]');
await page.waitForURL('**/dashboard');
```

#### Step 4: Use Existing Fixtures
The repo already has updated fixtures:
- ✅ `api/web/e2e/fixtures/auth.ts` (synchronous AuthContext)
- ✅ `api/web/e2e/helpers/login.js`

Use these instead of inline login logic:
```typescript
import { loginAsAdmin } from './fixtures/auth';

test('should access dashboard after login', async ({ page }) => {
  await loginAsAdmin(page);
  await expect(page).toHaveURL('**/dashboard');
});
```

#### Step 5: Run E2E Tests Locally
```bash
cd api/web

# Install dependencies
npm ci

# Install Playwright browsers
npx playwright install --with-deps chromium

# Start backend (in separate terminal)
cd ../..
export DB_PATH="db/shifts.e2e.db"
alembic upgrade head
python -m api.seeds.seed_e2e_minimal
python -m uvicorn api.main:app --host 0.0.0.0 --port 8188

# Run E2E tests
cd api/web
npm run test:e2e

# Or with UI mode
npm run test:e2e:ui
```

#### Step 6: Remove `.skip` Gradually
Only remove `.skip` from tests that:
- ✅ Use React SPA routes (`/login`, `/dashboard`, etc.)
- ✅ Have updated selectors for React components
- ✅ Pass locally

**Success Criteria**:
- ✅ At least 50% of skipped tests re-enabled
- ✅ All re-enabled tests pass in CI

---

## 🎯 TASK 4: IMPROVE CI/CD ROBUSTNESS

### Priority: 🟢 MEDIUM
### Files to modify:
- `api/web/playwright.config.ts`
- `.github/workflows/ci.yml`

### Problem:
- No retry logic for flaky tests
- No browser cache for Playwright (slow CI)
- Missing test artifacts on failure

### Action Items:

#### Step 1: Add Playwright Retry
Edit `api/web/playwright.config.ts`:
```typescript
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,  // ← ADD: Retry flaky tests in CI
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:8188',
    trace: 'on-first-retry',  // ← ADD: Trace on retry
    screenshot: 'only-on-failure',  // ← ADD: Screenshot on failure
  },
});
```

#### Step 2: Add Browser Cache
Edit `.github/workflows/ci.yml`:
```yaml
- name: Setup Node.js
  uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'  # ← ADD: Cache npm packages
    cache-dependency-path: api/web/package-lock.json

- name: Cache Playwright browsers
  uses: actions/cache@v3
  with:
    path: ~/.cache/ms-playwright
    key: ${{ runner.os }}-playwright-${{ hashFiles('api/web/package-lock.json') }}
    restore-keys: |
      ${{ runner.os }}-playwright-

- name: Install Playwright browsers
  working-directory: api/web
  run: npx playwright install --with-deps chromium
```

#### Step 3: Add Better Error Reporting
```yaml
- name: Upload test results on failure
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: test-results-${{ github.run_id }}
    path: |
      api/web/playwright-report/
      api/web/test-results/
      api.log
    retention-days: 14  # ← Increase retention
```

#### Step 4: Add Test Summary
```yaml
- name: Publish test summary
  if: always()
  uses: dorny/test-reporter@v1
  with:
    name: Playwright Tests
    path: api/web/test-results/*.xml
    reporter: java-junit
```

**Success Criteria**:
- ✅ CI runs faster (cached browsers)
- ✅ Flaky tests auto-retry (up to 2 times)
- ✅ Better failure diagnostics (screenshots, traces)

---

## 🎯 TASK 5: ADD PRE-COMMIT HOOKS

### Priority: 🟢 LOW
### Files to create:
- `.pre-commit-config.yaml`
- `scripts/run-tests-changed.sh`

### Goal:
Catch test failures BEFORE pushing to GitHub.

### Action Items:

#### Step 1: Install pre-commit
```bash
pip install pre-commit
```

#### Step 2: Create config
Create `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json

  - repo: local
    hooks:
      - id: pytest-changed
        name: Run pytest on changed Python files
        entry: scripts/run-tests-changed.sh
        language: system
        types: [python]
        pass_filenames: false
```

#### Step 3: Create test runner script
Create `scripts/run-tests-changed.sh`:
```bash
#!/bin/bash
set -e

echo "Running tests on changed files..."

# Get changed Python files
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)

if [ -z "$CHANGED_FILES" ]; then
  echo "No Python files changed, skipping tests."
  exit 0
fi

# Run pytest on api/tests/
export DB_PATH="db/shifts.test.db"
pytest api/tests/ -v --tb=short

echo "✅ Tests passed!"
```

#### Step 4: Install hooks
```bash
chmod +x scripts/run-tests-changed.sh
pre-commit install
```

**Success Criteria**:
- ✅ Tests run automatically on `git commit`
- ✅ Commit blocked if tests fail

---

## 📋 VERIFICATION CHECKLIST

After completing all tasks, verify:

```
[ ] Task 1: SQLAlchemy Employee model fixed
    [ ] All 5 employee tests pass locally
    [ ] Alembic migration created and applied
    [ ] No new migration conflicts
    [ ] CI passes for employee tests

[ ] Task 2: Copilot workflows fixed or disabled
    [ ] No workflow failures in recent runs
    [ ] CI completes without errors
    [ ] (Optional) Copilot workflows re-enabled with fixes

[ ] Task 3: E2E tests updated
    [ ] At least 50% of skipped tests re-enabled
    [ ] All re-enabled tests pass locally
    [ ] Playwright tests pass in CI

[ ] Task 4: CI/CD improvements
    [ ] Retry logic added to playwright.config.ts
    [ ] Browser cache added to ci.yml
    [ ] Test artifacts uploaded on failure
    [ ] CI run time improved by >30%

[ ] Task 5: Pre-commit hooks (optional)
    [ ] .pre-commit-config.yaml created
    [ ] Hooks installed locally
    [ ] Tests run on commit

[ ] Overall validation
    [ ] All CI checks pass (green ✅)
    [ ] No test failures in last 3 runs
    [ ] README updated with test instructions
```

---

## 🚀 FINAL STEPS

### Commit and Push
```bash
git add .
git commit -m "fix: resolve all test failures from 2025-11-19 audit

- Fix SQLAlchemy Employee model primary key mapping
- Disable broken Copilot workflows
- Update E2E tests for React SPA
- Improve CI/CD robustness (retry, cache, artifacts)
- Add pre-commit hooks for local testing

Resolves critical CI/CD pipeline blockage.
Closes #[issue-number]"

git push origin fix/test-failures-audit-2025-11-19
```

### Create Pull Request
```bash
gh pr create \
  --title "🔧 Fix: Resolve all test failures (2025-11-19 audit)" \
  --body "$(cat COPILOT_FIX_TASKS.md)" \
  --base master \
  --head fix/test-failures-audit-2025-11-19
```

### Monitor CI
- Watch GitHub Actions: https://github.com/Zasada1980/BUX/actions
- Verify all checks pass ✅
- Review Playwright report artifacts

---

## 📚 RESOURCES

- [SQLAlchemy ORM Mapping](https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html)
- [Alembic Migrations](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [GitHub Actions Caching](https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows)

---

**Generated by**: @Copilot  
**Date**: 2025-11-19 10:48:25 UTC  
**Audit Run**: https://github.com/Zasada1980/BUX/actions
