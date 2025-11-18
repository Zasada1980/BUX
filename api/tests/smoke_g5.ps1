#!/usr/bin/env pwsh
<#
.SYNOPSIS
G5 smoke test: Forbidden operations guard (403 for delete_item/update_total/mass_replace).

.DESCRIPTION
Validates runtime block of forbidden operations in invoice.suggest_change endpoint.
Expects HTTP 403 for all forbidden operations.

NO API server dependency required if running against local instance.
#>

Param(
    [string]$ApiBase = "http://127.0.0.1:8088"
)

$ErrorActionPreference = "Stop"
$t0 = [Environment]::TickCount64

Write-Host "=== G5 Smoke Test: Forbidden Ops Guard ===" -ForegroundColor Cyan

# Step 1: Create test invoice
Write-Host "`n[1/4] Creating test invoice..." -ForegroundColor Yellow
try {
    $inv = Invoke-RestMethod -Method Post -Uri "$ApiBase/api/invoice.build" -Body (@{
        client_id = 'smoke_g5'
        period_from = '2000-01-01'
        period_to = '2100-01-01'
        currency = 'ILS'
    } | ConvertTo-Json) -ContentType 'application/json'
    $invId = $inv.id
    Write-Host "  ✅ Invoice created: $invId" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Failed to create invoice: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 2: Issue preview token
Write-Host "`n[2/4] Issuing preview token..." -ForegroundColor Yellow
try {
    $tok = Invoke-RestMethod -Method Post -Uri "$ApiBase/api/invoice.preview/$invId/issue"
    $token = $tok.token
    Write-Host "  ✅ Token issued: $($token.Substring(0, 8))..." -ForegroundColor Green
} catch {
    Write-Host "  ❌ Failed to issue token: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 3: Test forbidden operations (expect 403)
Write-Host "`n[3/4] Testing forbidden operations..." -ForegroundColor Yellow
$forbidden = @("delete_item", "update_total", "mass_replace")
$results = @()

foreach ($kind in $forbidden) {
    try {
        $body = @{
            kind = $kind
            invoice_id = $invId
            token = $token
            payload = @{ id = 1 }
        } | ConvertTo-Json -Depth 6
        
        Invoke-RestMethod -Method Post -Uri "$ApiBase/api/invoice.suggest_change" `
            -Body $body -ContentType 'application/json' -ErrorAction Stop | Out-Null
        
        Write-Host "  ❌ $kind accepted (expected 403)" -ForegroundColor Red
        $results += "FAIL: $kind accepted"
        
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        if ($code -eq 403) {
            Write-Host "  ✅ $kind blocked (403)" -ForegroundColor Green
            $results += "PASS: $kind → 403"
        } else {
            Write-Host "  ❌ $kind unexpected code: $code" -ForegroundColor Red
            $results += "FAIL: $kind → $code"
        }
    }
}

# Step 4: Verify all forbidden
Write-Host "`n[4/4] Verification..." -ForegroundColor Yellow
$passed = ($results | Where-Object { $_ -match "^PASS:" }).Count
$failed = ($results | Where-Object { $_ -match "^FAIL:" }).Count

if ($failed -eq 0 -and $passed -eq 3) {
    $elapsed = [Environment]::TickCount64 - $t0
    Write-Host "`n✅ G5 smoke test PASSED (${elapsed}ms)" -ForegroundColor Green
    Write-Host "   - 3/3 forbidden operations blocked (403)" -ForegroundColor Green
    
    # Write evidence
    $output = "HTTP 403 OK - All forbidden ops blocked: $($forbidden -join ', ')"
    $output | Out-File "logs\g5_smoke_output.txt" -Encoding utf8
    Write-Host "   - Evidence: logs\g5_smoke_output.txt" -ForegroundColor Green
    
    exit 0
} else {
    Write-Host "`n❌ G5 smoke test FAILED" -ForegroundColor Red
    Write-Host "   - Passed: $passed/3" -ForegroundColor Yellow
    Write-Host "   - Failed: $failed/3" -ForegroundColor Red
    $results | ForEach-Object { Write-Host "     $_" -ForegroundColor Gray }
    exit 1
}
