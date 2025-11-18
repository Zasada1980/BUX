#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Smoke test for I1 Admin Authentication (S38 gate).
.DESCRIPTION
    Tests admin authentication via X-Admin-Secret header:
    - Missing header → 401 Unauthorized
    - Wrong secret → 403 Forbidden  
    - Correct secret → 200/204 OK
.PARAMETER Base
    API base URL (default: http://127.0.0.1:8088)
.PARAMETER Secret
    Admin secret to test (default: change-me)
#>
param(
    [string]$Base = "http://127.0.0.1:8088",
    [string]$Secret = "change-me"
)

$ErrorActionPreference = "Stop"

try {
    $t0 = [Environment]::TickCount64
    
    Write-Host "`n=== Admin Auth Smoke Test (S38) ===" -ForegroundColor Cyan
    Write-Host "Target: $Base/api/admin/pending" -ForegroundColor Gray
    Write-Host "Secret: ${Secret}" -ForegroundColor Gray
    
    # Test 1: Missing header → 401
    Write-Host "`n[1/3] Testing missing X-Admin-Secret header..." -ForegroundColor Yellow
    try {
        $response1 = Invoke-WebRequest -Uri "$Base/api/admin/pending" -UseBasicParsing -ErrorAction Stop
        throw "Expected 401 Unauthorized, but got HTTP $($response1.StatusCode)"
    }
    catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 401) {
            Write-Host "   ✅ Correctly rejected with 401 Unauthorized" -ForegroundColor Green
        }
        else {
            throw "Expected 401, got: $($_.Exception.Response.StatusCode.value__) - $_"
        }
    }
    
    # Test 2: Wrong secret → 403
    Write-Host "`n[2/3] Testing wrong X-Admin-Secret..." -ForegroundColor Yellow
    try {
        $response2 = Invoke-WebRequest `
            -Uri "$Base/api/admin/pending" `
            -Headers @{ "X-Admin-Secret" = "wrong-secret" } `
            -UseBasicParsing `
            -ErrorAction Stop
        throw "Expected 403 Forbidden, but got HTTP $($response2.StatusCode)"
    }
    catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 403) {
            Write-Host "   ✅ Correctly rejected with 403 Forbidden" -ForegroundColor Green
        }
        else {
            throw "Expected 403, got: $($_.Exception.Response.StatusCode.value__) - $_"
        }
    }
    
    # Test 3: Correct secret → 200/204
    Write-Host "`n[3/3] Testing correct X-Admin-Secret..." -ForegroundColor Yellow
    $response3 = Invoke-WebRequest `
        -Uri "$Base/api/admin/pending" `
        -Headers @{ "X-Admin-Secret" = $Secret } `
        -UseBasicParsing `
        -ErrorAction Stop
    
    if ($response3.StatusCode -notin 200, 204) {
        throw "Expected 200 or 204, got HTTP $($response3.StatusCode)"
    }
    
    Write-Host "   ✅ Accepted with HTTP $($response3.StatusCode)" -ForegroundColor Green
    
    # Generate artifact
    $logDir = "logs"
    if (-not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir | Out-Null
    }
    
    $artifactPath = Join-Path $logDir "smoke_i1_admin_auth.txt"
    $summary = @"
I1 Admin Auth Test Results
==========================
Test 1 (Missing header): 401 ✓
Test 2 (Wrong secret): 403 ✓
Test 3 (Correct secret): $($response3.StatusCode) ✓
"@
    $summary | Set-Content -Path $artifactPath -Encoding UTF8
    
    $elapsed = [Environment]::TickCount64 - $t0
    
    Write-Host "`n✅ S38 PASS: Admin authentication working" -ForegroundColor Green
    Write-Host "   Tests: 3/3 passed" -ForegroundColor White
    Write-Host "   Artifact: $artifactPath" -ForegroundColor Gray
    Write-Host "`nВремя: ${elapsed}ms" -ForegroundColor Gray
    
    exit 0
}
catch {
    Write-Host "`n❌ S38 FAIL: $_" -ForegroundColor Red
    exit 1
}
