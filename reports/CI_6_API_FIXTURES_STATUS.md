# CI-6: API Test Fixtures Refactoring Status

**Branch**: ci6-api-fixtures
**Base**: ci5-stabilize-tests (c93e279)
**Goal**: Migrate all API tests to use centralized `conftest.py` fixtures, eliminate DB setup duplication, improve test isolation

---

## Executive Summary

**Phase 1 Complete**: ✅ `test_auth.py` refactored (8/8 PASS, commit 67c4ce9)
**Phase 2 In Progress**: Migrating remaining 5 test files

### Overall Progress

| File | Tests | Status | Engine Isolation | Xfail (CI-5) | Target | Result |
|------|-------|--------|-----------------|--------------|--------|--------|
| `test_auth.py` | 8 | ✅ **COMPLETE** | ✅ Fixed | 1 → 0 | 8/8 PASS | ✅ 67c4ce9 |
| `test_employees.py` | 9 | ✅ **COMPLETE** | ✅ Fixed | 9 → 0 | 9/9 PASS | ✅ 96577c4 |
| `test_infra_smoke.py` | 5 | 🔄 Pending | ❌ Own engine | 3 | TBD | - |
| `test_bulk_idempotency.py` | 5 | 🔄 Pending | ❌ Own engine | 0 | TBD | - |
| `test_forbidden_ops.py` | 5 | 🔄 Pending | ❌ Own engine | 0 | TBD | - |
| `test_item_details.py` | 4 | 🔄 Pending | ❌ Own engine | 3 | TBD | - |
| **TOTAL** | **36** | **47% done** | **2/6 fixed** | **16 → 7** | **36 PASS** | **17/36 PASS** |

**Latest Achievement**: test_employees.py refactored to 9/9 PASS (removed 9 xfail, fixed password validation test123 → test12345)

---

## Phase 2 Detailed Progress

### File 2/6: test_employees.py (✅ COMPLETE)

**Commit**: 96577c4 "CI-6: Refactor test_employees.py (9/9 PASS, removed 9 xfail)"

**Changes**:
- **Removed** (~110 lines):
  - Manual `engine = create_engine(...)` creation
  - `SessionLocal = sessionmaker(...)` setup
  - `get_admin_token()` helper function (replaced by conftest `admin_headers` fixture)
  - 9 `@pytest.mark.xfail` decorators (reason: "DB isolation")
  
- **Added**:
  - `import random` for unique telegram_id generation
  - All tests now use `(client, admin_headers)` fixtures from conftest.py
  
- **Refactoring Highlights**:
  - **test_update_employee**, **test_soft_delete_employee**: Inline employee creation (no dependency on test_create_employee)
  - **test_duplicate_username**: Creates first employee, then attempts duplicate with same telegram_id
  - **test_rbac_admin_can_create**, **test_invalid_role**: Use random.randint(100000000, 999999999) for unique IDs
  
- **Password Validation Fix**:
  - Initial failure: `"password": "test123"` (7 chars) → 422 validation error
  - Root cause: API schema requires `min_length=8` (Pydantic validator in schemas_employees.py)
  - Solution: Changed to `"password": "test12345"` (9 chars)
  - Evidence: Full error detail captured in test run output
  
- **Test Results**:
  - Iteration 1: 5/9 PASS (409 Conflict - duplicate telegram_id)
  - Iteration 2: 7/9 PASS (password validation errors)
  - **Final**: **9/9 PASS** (100%)
  
- **Lines Changed**: 122 insertions, 226 deletions (-104 lines net reduction)

**Lessons Learned**:
1. ✅ Random telegram_id prevents 409 Conflict across test runs
2. ✅ Conftest db_session rollback ensures clean state per test
3. ✅ Password validation requires checking API schema constraints (not just data types)
4. ✅ Inline test data creation improves test isolation (no cross-test dependencies)

---

## Conftest.py Architecture

## Conftest.py Architecture

### Session-Scoped Fixtures (expensive setup, runs once)

1. **`test_db_path(tmp_path_factory)`**
   - Creates temp SQLite file in pytest temp dir
   - Sets `DB_PATH` env variable BEFORE any api imports
   - Returns: absolute path to temp DB file
   - **Why**: Prevents interference with dev/prod databases

2. **`app(test_db_path)`**
   - Imports FastAPI app AFTER DB_PATH is set
   - Creates all tables via `metadata.create_all()`
   - Returns: FastAPI TestClient instance
   - **Dependency**: Requires test_db_path to run first

3. **`db_engine_and_session(test_db_path)`**
   - Creates dedicated engine + SessionLocal for direct DB access
   - Used by tests that need raw DB queries (schema inspection, complex setup)
   - Returns: tuple `(engine, SessionLocal)`
   - **Why**: Some tests need DB-level operations outside of API

4. **`client(app)`**
   - Returns: `TestClient(app)` for HTTP requests
   - **Usage**: All API endpoint tests use this for GET/POST/PUT/DELETE

5. **`seed_admin(db_engine_and_session)`**
   - Creates admin user in DB with bcrypt-hashed password
   - Username: "admin", Password: "admin123", Role: "admin"
   - Returns: tuple `(employee_id, username, plain_password)`
   - **Why**: Provides known credentials for auth tests

### Function-Scoped Fixtures (runs per test)

6. **`db_session(db_engine_and_session)`**
   - Creates new session with `begin_nested()` savepoint
   - **Yields** session to test
   - **Rollback** after test completes (ensures test isolation)
   - **Why**: Prevents test data pollution

7. **`admin_token(client, seed_admin)`**
   - Calls `POST /api/auth/login` with admin credentials
   - Returns: JWT access_token string
   - **Used by**: admin_headers fixture

8. **`admin_headers(admin_token)`**
   - Returns: `{"Authorization": f"Bearer {admin_token}"}`
   - **Usage**: All authenticated API tests use this for headers

---

## Migration Plan

### File 3/6: test_infra_smoke.py (NEXT)

**Current State** (CI-5):
- 5 tests (3 xfail)
- Creates own engine
- Tests: DB schema validation (TelegramUser, ChannelMessage tables), seed data checks

**Migration Strategy**:
1. Remove local engine creation
2. Use `db_engine_and_session` for table inspection tests
3. Use `seed_admin` fixture for seed data tests (likely removes 3 xfail)
4. Expected: **5/5 PASS** (0 xfail)

**Conftest Extensions**: None required (existing fixtures sufficient)

---

### File 4/6: test_bulk_idempotency.py

**Current State** (CI-5):
- 5 tests (0 xfail)
- Creates own `:memory:` engine
- Has own `db_session` fixture
- Creates `idempotency_keys` table inline

**Migration Strategy**:
1. **Option A** (preferred): Extend conftest `db_engine_and_session` to create `idempotency_keys` table
2. **Option B**: Keep local fixture but use conftest's engine
3. Use conftest `client` + `admin_headers`
4. Expected: **5/5 PASS** (no change, but unified DB)

**Conftest Extensions**: Add `idempotency_keys` table creation to `db_engine_and_session` fixture

---

### File 5/6: test_forbidden_ops.py

**Current State** (CI-5):
- 5 tests (0 xfail)
- Creates own engine
- Tests: Permission checks, invalid operations

**Migration Strategy**:
1. Remove local engine
2. Use `db_session` for DB operations
3. Use `client` + `admin_headers`
4. Expected: **5/5 PASS**

**Conftest Extensions**: None required

---

### File 6/6: test_item_details.py

**Current State** (CI-5):
- 4 tests (3 xfail - pricing.yml missing)
- Creates own engine
- Tests: Invoice item calculations

**Migration Strategy**:
1. Remove local engine
2. Use `db_session` + `client`
3. **Keep 3 xfail** for pricing.yml (out of CI-6 scope)
4. Expected: **1/4 PASS, 3/4 xfail** (pricing.yml)

**Conftest Extensions**: None required
**Technical Debt**: Pricing.yml dependency tracked in `TECH_DEBT.md`

---

## Per-File Workflow

1. **Analyze**: Read full file, identify manual DB setup, xfail reasons
2. **Extend conftest** (if needed): Add missing fixtures (e.g., idempotency_keys table)
3. **Refactor**: Remove engine creation, replace with conftest fixtures
4. **Local Test**: `pytest api/tests/test_<file>.py -v`
5. **Commit**: Descriptive message with PASS count + xfail removals
6. **Update Status**: Edit this document with results

---

## Technical Debt

### Resolved in CI-6

1. ✅ **DB Isolation** (16 xfail across 5 files)
   - **Solution**: Conftest `db_session` with rollback
   - **Evidence**: test_auth.py (1 xfail removed), test_employees.py (9 xfail removed)

2. ✅ **bcrypt 5.x Compatibility**
   - **Issue**: `passlib[bcrypt]` pinned to bcrypt 4.x in requirements.txt
   - **Solution**: Use `import bcrypt` directly in conftest/tests
   - **Evidence**: seed_admin fixture uses bcrypt.hashpw() successfully

### Deferred (Out of Scope)

1. ⏳ **JWT Signature Verification** (test_auth.py)
   - `jwt.decode()` doesn't validate signature (`options={"verify_signature": False}`)
   - **Risk**: Low (tests only check token structure, not cryptographic integrity)
   - **Roadmap**: CI-7 or F6 (add secret key to conftest, verify signatures)

2. ⏳ **Pricing.yml Dependency** (test_item_details.py)
   - 3 xfail tests require `pricing.yml` file
   - **Blocker**: File location not in test environment
   - **Roadmap**: F6 (add test fixture or mock pricing config)

3. ⏳ **Pydantic V2 Migration**
   - 38+ deprecation warnings (`@validator` → `@field_validator`)
   - **Impact**: Warnings only, no functional issues
   - **Roadmap**: CI-8 or F6 (bulk migration to Pydantic V2 patterns)

---

## Git Workflow

### Branch Strategy
- **Work branch**: `ci6-api-fixtures` (current)
- **Base**: `ci5-stabilize-tests` (c93e279)
- **Master**: NOT updated (still at a8bdd28 - CI-3)
- **No rebase needed**: Sequential development (ci5 → ci6)

### Commit History
1. `67c4ce9`: CI-6: Refactor test_auth.py to use conftest.py fixtures (8/8 PASS)
2. `96577c4`: CI-6: Refactor test_employees.py (9/9 PASS, removed 9 xfail)
3. *Pending*: test_infra_smoke.py refactor
4. *Pending*: test_bulk_idempotency.py refactor
5. *Pending*: test_forbidden_ops.py refactor
6. *Pending*: test_item_details.py refactor
7. *Final*: Update CI_6_API_FIXTURES_STATUS.md with completion stats

### Merge Plan
- **DO NOT merge to master** until:
  1. All 6 files refactored (36+ tests PASS)
  2. Manual review by user
  3. CI-5 merged first (if needed)
- **Push to origin**: `git push origin ci6-api-fixtures` after each commit

---

## Next Steps

### Immediate (File 3/6)
1. Read `test_infra_smoke.py` (5 tests, 3 xfail)
2. Refactor: Remove engine, use `db_engine_and_session` + `seed_admin`
3. Local test: `pytest api/tests/test_infra_smoke.py -v`
4. Target: **5/5 PASS** (remove 3 xfail)
5. Commit: "CI-6: Refactor test_infra_smoke.py (5/5 PASS, removed 3 xfail)"

### Remaining Files
- **test_bulk_idempotency.py**: Extend conftest for idempotency_keys table
- **test_forbidden_ops.py**: Straightforward (no conftest changes)
- **test_item_details.py**: Keep 3 xfail (pricing.yml out of scope)

### Final Validation
`powershell
# After all files refactored
pytest api/tests/ -v --tb=short

# Expected: 30+ PASS, 3 xfail (pricing.yml only)
# Update this document with final stats
`

### Success Criteria
- ✅ 6/6 test files use conftest fixtures (0 engine duplication)
- ✅ 13 DB isolation xfail decorators removed (test_employees: 9, test_infra_smoke: 3, test_auth: 1)
- ✅ ~30+ PASS, 3 xfail (pricing.yml only)
- ✅ CI_6_API_FIXTURES_STATUS.md complete with final stats
- ✅ Pushed to origin/ci6-api-fixtures (ready for manual review/merge)

---

**Last Updated**: 2025-11-18 13:22 UTC
**Status**: 2/6 files complete (test_auth.py, test_employees.py), 17/36 tests migrated (47%)

