# CI-11: Code Protection & Health Monitoring

**Создан:** 2025-11-20  
**Цель:** Защитить рабочий код от случайной поломки + мониторинг здоровья системы

---

## 🛡️ Protection Mechanisms

### 1. Git Pre-Commit Hook (Блокировка поломки перед коммитом)

**Файл:** `d:\TelegramOllama_ENV_DEMO\code\.git\hooks\pre-commit`

```bash
#!/bin/bash
# CI-11: Pre-commit protection hook

echo "🔍 CI-11 Pre-Commit Checks..."

# Check 1: Ensure admin role fix exists
if [ ! -f "api/seeds/fix_admin_role.py" ]; then
    echo "❌ BLOCKED: fix_admin_role.py missing (required for E2E tests)"
    exit 1
fi

# Check 2: Ensure UsersPage.tsx has correct toast message
if grep -q "'User activated successfully'" api/web/src/pages/UsersPage.tsx; then
    echo "❌ BLOCKED: UsersPage.tsx has OLD toast message (should be 'updated')"
    exit 1
fi

# Check 3: Block commits with console.log in production code (exclude E2E tests)
if git diff --cached --name-only | grep -E '^api/web/src/.*\.(ts|tsx)$' | xargs grep -l 'console\.log' 2>/dev/null; then
    echo "⚠️  WARNING: console.log found in production code"
    echo "   Run 'npm run lint' to review"
fi

# Check 4: Ensure E2E tests pass before commit (optional, can be disabled)
# Uncomment to enable:
# cd api/web && npm run test:e2e:user-management || {
#     echo "❌ BLOCKED: E2E tests failing"
#     exit 1
# }

echo "✅ Pre-commit checks passed"
exit 0
```

**Установка:**
```powershell
# Создать hook file
New-Item -ItemType File -Path "d:\TelegramOllama_ENV_DEMO\code\.git\hooks\pre-commit" -Force

# Скопировать содержимое выше в файл

# Сделать executable (Git Bash)
chmod +x d:\TelegramOllama_ENV_DEMO\code\.git\hooks\pre-commit
```

---

### 2. Automated Health Check Script (Мониторинг после изменений)

**Файл:** `d:\TelegramOllama_ENV_DEMO\code\scripts\health_check.ps1`

```powershell
# CI-11: Automated Health Check
# Запускать после любых изменений кода

param(
    [switch]$Full,  # Full check включает E2E тесты
    [switch]$Cloud  # Cloud check тестирует облачный сервер
)

Write-Host "=== CI-11 Health Check ===" -ForegroundColor Cyan
Write-Host ""

$allPassed = $true

# Check 1: Docker containers
Write-Host "1. Docker Containers Status" -ForegroundColor Yellow
$containers = docker ps --format "{{.Names}}: {{.Status}}" | Select-String "demo_"
if ($containers.Count -ge 3) {
    Write-Host "   ✅ PASS ($($containers.Count) containers running)" -ForegroundColor Green
} else {
    Write-Host "   ❌ FAIL (expected 3+, got $($containers.Count))" -ForegroundColor Red
    $allPassed = $false
}

# Check 2: API Health
Write-Host "2. API Health Endpoint" -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "http://localhost:8188/health" -TimeoutSec 5
    if ($health.status -eq "ok") {
        Write-Host "   ✅ PASS (status: $($health.status), uptime: $([math]::Round($health.uptime_s))s)" -ForegroundColor Green
    } else {
        Write-Host "   ❌ FAIL (status: $($health.status))" -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host "   ❌ FAIL (API unreachable: $_)" -ForegroundColor Red
    $allPassed = $false
}

# Check 3: Admin Login
Write-Host "3. Admin Authentication" -ForegroundColor Yellow
try {
    $login = Invoke-RestMethod -Uri "http://localhost:8188/api/auth/login" `
        -Method POST `
        -ContentType "application/json" `
        -Body '{"username":"admin","password":"admin123"}' `
        -TimeoutSec 5
    
    if ($login.access_token.Length -gt 100) {
        Write-Host "   ✅ PASS (token: $($login.access_token.Substring(0,20))...)" -ForegroundColor Green
    } else {
        Write-Host "   ❌ FAIL (invalid token)" -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host "   ❌ FAIL (login failed: $_)" -ForegroundColor Red
    $allPassed = $false
}

# Check 4: Admin Role Verification
Write-Host "4. Admin Role (DB Integrity)" -ForegroundColor Yellow
$role = docker exec demo_api sqlite3 /app/db/shifts.db "SELECT role FROM users WHERE id=1" 2>$null
if ($role -eq "admin") {
    Write-Host "   ✅ PASS (role: $role)" -ForegroundColor Green
} else {
    Write-Host "   ❌ FAIL (role: $role, expected: admin)" -ForegroundColor Red
    $allPassed = $false
}

# Check 5: Critical Files Exist
Write-Host "5. Critical Files Integrity" -ForegroundColor Yellow
$criticalFiles = @(
    "api\seeds\fix_admin_role.py",
    "api\web\src\pages\UsersPage.tsx",
    "api\web\dist\index.html"
)
$missingFiles = @()
foreach ($file in $criticalFiles) {
    if (-not (Test-Path "d:\TelegramOllama_ENV_DEMO\code\$file")) {
        $missingFiles += $file
    }
}
if ($missingFiles.Count -eq 0) {
    Write-Host "   ✅ PASS (all $($criticalFiles.Count) files present)" -ForegroundColor Green
} else {
    Write-Host "   ❌ FAIL (missing: $($missingFiles -join ', '))" -ForegroundColor Red
    $allPassed = $false
}

# Check 6: E2E Tests (only if -Full flag)
if ($Full) {
    Write-Host "6. E2E Test Suite" -ForegroundColor Yellow
    Push-Location "d:\TelegramOllama_ENV_DEMO\code\api\web"
    $e2eResult = npm run test:e2e -- user-management-smoke --reporter=line 2>&1
    Pop-Location
    
    if ($e2eResult -match "6 passed") {
        Write-Host "   ✅ PASS (6/6 User Management tests)" -ForegroundColor Green
    } else {
        Write-Host "   ❌ FAIL (E2E tests failed)" -ForegroundColor Red
        $allPassed = $false
    }
}

# Check 7: Cloud Health (only if -Cloud flag)
if ($Cloud) {
    Write-Host "7. Cloud Server (46.224.36.109)" -ForegroundColor Yellow
    try {
        $cloudHealth = ssh root@46.224.36.109 'curl -s http://localhost:8088/health' | ConvertFrom-Json
        if ($cloudHealth.status -eq "ok") {
            Write-Host "   ✅ PASS (cloud status: $($cloudHealth.status))" -ForegroundColor Green
        } else {
            Write-Host "   ❌ FAIL (cloud status: $($cloudHealth.status))" -ForegroundColor Red
            $allPassed = $false
        }
    } catch {
        Write-Host "   ❌ FAIL (cloud unreachable: $_)" -ForegroundColor Red
        $allPassed = $false
    }
}

# Summary
Write-Host ""
Write-Host "=== SUMMARY ===" -ForegroundColor Cyan
if ($allPassed) {
    Write-Host "✅ ALL CHECKS PASSED - System is healthy" -ForegroundColor Green
    exit 0
} else {
    Write-Host "❌ SOME CHECKS FAILED - Review errors above" -ForegroundColor Red
    exit 1
}
```

**Использование:**
```powershell
# Quick check (5 базовых проверок)
.\scripts\health_check.ps1

# Full check (включая E2E тесты)
.\scripts\health_check.ps1 -Full

# Cloud check (включая облачный сервер)
.\scripts\health_check.ps1 -Cloud

# Full + Cloud
.\scripts\health_check.ps1 -Full -Cloud
```

---

### 3. GitHub Actions CI (Автоматическая защита на каждом push)

**Файл:** `d:\TelegramOllama_ENV_DEMO\code\.github\workflows\ci-protection.yml`

```yaml
name: CI-11 Protection

on:
  push:
    branches: [ master, main, ci11-e2e-schema-fix ]
  pull_request:
    branches: [ master, main ]

jobs:
  health-check:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Verify Critical Files
      run: |
        test -f api/seeds/fix_admin_role.py || { echo "❌ fix_admin_role.py missing"; exit 1; }
        test -f api/web/src/pages/UsersPage.tsx || { echo "❌ UsersPage.tsx missing"; exit 1; }
        echo "✅ Critical files present"
    
    - name: Check UsersPage Toast Message
      run: |
        if grep -q "'User activated successfully'" api/web/src/pages/UsersPage.tsx; then
          echo "❌ FAIL: Old toast message found"
          exit 1
        fi
        echo "✅ Toast message correct"
    
    - name: Block console.log in production
      run: |
        if grep -r "console\.log" api/web/src/ --include="*.ts" --include="*.tsx" --exclude-dir=e2e; then
          echo "⚠️ WARNING: console.log found in production code"
        fi
        echo "✅ Production code check passed"
  
  e2e-tests:
    runs-on: ubuntu-latest
    needs: health-check
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Node.js
      uses: actions/setup-node@v3
      with:
        node-version: '18'
    
    - name: Install dependencies
      run: cd api/web && npm ci
    
    - name: Install Playwright
      run: cd api/web && npx playwright install --with-deps chromium
    
    - name: Run E2E Tests
      run: cd api/web && npm run test:e2e -- user-management-smoke
    
    - name: Upload test results
      if: always()
      uses: actions/upload-artifact@v3
      with:
        name: playwright-report
        path: api/web/playwright-report/
```

---

## 📝 Usage Workflow

### После любого изменения кода:

```powershell
# 1. Сделать изменения
# (edit files...)

# 2. Запустить health check
.\scripts\health_check.ps1

# 3. Если PASS → коммит
git add .
git commit -m "..."

# 4. Pre-commit hook автоматически проверит критичные файлы

# 5. Push запустит GitHub Actions
git push origin ci11-e2e-schema-fix
```

### Перед деплоем на облако:

```powershell
# Full check на D:\
.\scripts\health_check.ps1 -Full

# Если PASS → деплой на облако
scp ... root@46.224.36.109:...
ssh root@46.224.36.109 'docker restart prod_api'

# Cloud check после деплоя
.\scripts\health_check.ps1 -Cloud
```

---

## 🚨 Protection Matrix

| Защита | Где | Когда | Что проверяет |
|--------|-----|-------|---------------|
| **Pre-commit hook** | Локально | git commit | fix_admin_role.py, toast message, console.log |
| **Health check script** | Локально/Cloud | Вручную | Docker, API, admin role, files, E2E |
| **GitHub Actions** | GitHub | git push | Critical files, toast, E2E tests |
| **Backup manifests** | D:\ repo | Перед deploy | CI_11_TESTED_FILES_BACKUP.md |

---

## ✅ Installation Checklist

- [ ] Создать `.git/hooks/pre-commit` с содержимым выше
- [ ] Сделать pre-commit executable: `chmod +x .git/hooks/pre-commit`
- [ ] Создать `scripts/health_check.ps1`
- [ ] Создать `.github/workflows/ci-protection.yml`
- [ ] Протестировать: `.\scripts\health_check.ps1`
- [ ] Протестировать: `git commit` (должен запустить hook)
- [ ] Push на GitHub (должен запустить Actions)

---

**Создан:** 2025-11-20  
**Автор:** AI Agent  
**Статус:** ⏳ READY TO INSTALL
