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
    try {
        $e2eOutput = npm run test:e2e -- user-management-smoke --reporter=line 2>&1
        if ($e2eOutput -match "6 passed") {
            Write-Host "   ✅ PASS (6/6 User Management tests)" -ForegroundColor Green
        } else {
            Write-Host "   ❌ FAIL (E2E tests failed)" -ForegroundColor Red
            $allPassed = $false
        }
    } catch {
        Write-Host "   ❌ FAIL (E2E error: $_)" -ForegroundColor Red
        $allPassed = $false
    }
    Pop-Location
}

# Check 7: Cloud Health (only if -Cloud flag)
if ($Cloud) {
    Write-Host "7. Cloud Server (46.224.36.109)" -ForegroundColor Yellow
    try {
        $cloudHealthJson = ssh root@46.224.36.109 'curl -s http://localhost:8088/health'
        $cloudHealth = $cloudHealthJson | ConvertFrom-Json
        if ($cloudHealth.status -eq "ok") {
            Write-Host "   ✅ PASS (cloud status: $($cloudHealth.status), uptime: $([math]::Round($cloudHealth.uptime_s))s)" -ForegroundColor Green
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
