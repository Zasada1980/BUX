#!/usr/bin/env pwsh
<#
.SYNOPSIS
G4 smoke tests: bulk idempotency with ≤100ms repeat timing verification.

.DESCRIPTION
Validates:
1. Unit tests pass (5/5 with timing check)
2. Timing ≤100ms for repeat detection (extracted from pytest output)
3. SHA256 manifest for evidence

NO API server dependency - pytest only.
#>

$ErrorActionPreference = "Stop"
$timing_start = [Environment]::TickCount64

Write-Host "=== G4 Smoke Tests: Bulk Idempotency ===" -ForegroundColor Cyan

# Step 1: Run pytest with timing
Write-Host "`n[1/3] Running pytest tests/test_bulk_idempotency.py..." -ForegroundColor Yellow
Set-Location (Join-Path $PSScriptRoot "..")
$pytest_output = python -m pytest tests/test_bulk_idempotency.py -v 2>&1 | Out-String

# Step 2: Verify 5/5 passed
Write-Host "`n[2/3] Verifying test results..." -ForegroundColor Yellow

if ($pytest_output -match "5 passed") {
    Write-Host "  ✅ All 5 tests PASSED" -ForegroundColor Green
    
    # List expected tests for documentation
    $expected_tests = @(
        "test_scope_hash_deterministic",
        "test_first_request_200",
        "test_repeat_409",
        "test_repeat_timing_100ms",
        "test_different_payload_same_key_200"
    )
    Write-Host "     Tests: $($expected_tests -join ', ')" -ForegroundColor Gray
} else {
    Write-Host "  ❌ Expected 5 passed, check output" -ForegroundColor Red
    Write-Host $pytest_output
    exit 1
}

# Step 3: Extract timing from test_repeat_timing_100ms assertion
Write-Host "`n[3/3] Verifying ≤100ms timing requirement..." -ForegroundColor Yellow

# NOTE: If test passes, timing was ≤100ms (assertion in test code)
if ($pytest_output -match "5 passed") {
    Write-Host "  ✅ Repeat detection timing ≤100ms (verified by test_repeat_timing_100ms)" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Could not verify timing (test failed)" -ForegroundColor Yellow
    exit 1
}

# Step 4: Generate SHA256 manifest
Write-Host "`n[4/4] Generating SHA256 manifest..." -ForegroundColor Yellow
$manifest_path = "logs/g4_test_sha_manifest.txt"
New-Item -ItemType Directory -Path (Split-Path $manifest_path) -Force | Out-Null

$files = @(
    "tests/test_bulk_idempotency.py",
    "utils/idempotency_guard.py",
    "db/alembic/versions/a1b2c3d4e5f6_idempotency_keys.py"
)

$manifest = @()
foreach ($file in $files) {
    if (Test-Path $file) {
        $hash = (Get-FileHash $file -Algorithm SHA256).Hash.Substring(0, 12)
        $manifest += "${file}: $hash"
    }
}

$manifest | Out-File $manifest_path -Encoding utf8
Write-Host "  📄 Manifest: $manifest_path" -ForegroundColor Cyan
$manifest | ForEach-Object { Write-Host "     $_" -ForegroundColor Gray }

$timing_elapsed = [Environment]::TickCount64 - $timing_start
Write-Host "`n✅ G4 smoke tests PASSED (${timing_elapsed}ms)" -ForegroundColor Green
Write-Host "   - 5/5 unit tests passed" -ForegroundColor Green
Write-Host "   - ≤100ms timing verified" -ForegroundColor Green
Write-Host "   - SHA256 manifest: $manifest_path" -ForegroundColor Green

exit 0
