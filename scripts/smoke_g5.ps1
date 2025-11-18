# smoke_g5.ps1 - Forbidden Operations Gate (G5)
# Validates that forbidden operations (delete_item, update_total, mass_replace) return 403

param(
    [string]$BaseUrl = "http://127.0.0.1:8088"
)

$ErrorActionPreference = "Stop"
Write-Host "`n=== G5: Forbidden Operations Gate ===" -ForegroundColor Cyan
Write-Host "Test: delete_item/update_total/mass_replace -> 403`n" -ForegroundColor Yellow

try {
    # Step 1: Create invoice
    Write-Host "[1/4] Creating invoice..." -ForegroundColor Gray
    $body = @{
        client_id = "g5_test"
        period_from = "2025-11-01"
        period_to = "2025-11-13"
    } | ConvertTo-Json
    
    try {
        $inv = Invoke-RestMethod -Method POST -Uri "$BaseUrl/api/invoice.build" `
            -Headers @{"Content-Type"="application/json"} `
            -Body $body -TimeoutSec 10 -ErrorAction Stop
        $invoiceId = $inv.invoice_id
        Write-Host "Invoice ID: $invoiceId" -ForegroundColor Green
    } catch {
        Write-Host "[WARNING] invoice.build unavailable (float bug), using fixed ID=1" -ForegroundColor Yellow
        $invoiceId = 1
    }
    
    # Step 2: Try delete_item (FORBIDDEN)
    Write-Host "[2/4] Testing suggest_change with kind=delete_item..." -ForegroundColor Gray
    $deleteBody = @{
        invoice_id = $invoiceId
        kind = "delete_item"
        payload_json = @{ item_index = 0 }
    } | ConvertTo-Json
    
    $deleteStatus = 0
    try {
        Invoke-RestMethod -Method POST -Uri "$BaseUrl/api/invoice.suggest_change" `
            -Headers @{"Content-Type"="application/json"} `
            -Body $deleteBody -TimeoutSec 10 -ErrorAction Stop | Out-Null
        $deleteStatus = 200
    } catch {
        $deleteStatus = $_.Exception.Response.StatusCode.value__
    }
    
    if ($deleteStatus -eq 403) {
        Write-Host "[PASS] delete_item blocked (403)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] delete_item returned $deleteStatus instead of 403" -ForegroundColor Red
    }
    
    # Step 3: Try update_total (FORBIDDEN)
    Write-Host "[3/4] Testing suggest_change with kind=update_total..." -ForegroundColor Gray
    $updateBody = @{
        invoice_id = $invoiceId
        kind = "update_total"
        payload_json = @{ new_total = "9999.99" }
    } | ConvertTo-Json
    
    $updateStatus = 0
    try {
        Invoke-RestMethod -Method POST -Uri "$BaseUrl/api/invoice.suggest_change" `
            -Headers @{"Content-Type"="application/json"} `
            -Body $updateBody -TimeoutSec 10 -ErrorAction Stop | Out-Null
        $updateStatus = 200
    } catch {
        $updateStatus = $_.Exception.Response.StatusCode.value__
    }
    
    if ($updateStatus -eq 403) {
        Write-Host "[PASS] update_total blocked (403)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] update_total returned $updateStatus instead of 403" -ForegroundColor Red
    }
    
    # Step 4: Try mass_replace (FORBIDDEN)
    Write-Host "[4/4] Testing suggest_change with kind=mass_replace..." -ForegroundColor Gray
    $massBody = @{
        invoice_id = $invoiceId
        kind = "mass_replace"
        payload_json = @{ pattern = ".*"; replacement = "HACKED" }
    } | ConvertTo-Json
    
    $massStatus = 0
    try {
        Invoke-RestMethod -Method POST -Uri "$BaseUrl/api/invoice.suggest_change" `
            -Headers @{"Content-Type"="application/json"} `
            -Body $massBody -TimeoutSec 10 -ErrorAction Stop | Out-Null
        $massStatus = 200
    } catch {
        $massStatus = $_.Exception.Response.StatusCode.value__
    }
    
    if ($massStatus -eq 403) {
        Write-Host "[PASS] mass_replace blocked (403)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] mass_replace returned $massStatus instead of 403" -ForegroundColor Red
    }
    
    # Final validation
    Write-Host "`n--- Results ---" -ForegroundColor Cyan
    Write-Host "delete_item: $deleteStatus (expected 403)" -ForegroundColor Gray
    Write-Host "update_total: $updateStatus (expected 403)" -ForegroundColor Gray
    Write-Host "mass_replace: $massStatus (expected 403)" -ForegroundColor Gray
    
    if ($deleteStatus -eq 403 -and $updateStatus -eq 403 -and $massStatus -eq 403) {
        Write-Host "`n[SUCCESS] G5 PASS: All forbidden operations blocked (403)" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "`n[FAIL] G5 FAIL: One or more forbidden operations did not return 403" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "`n[ERROR] G5 ERROR: $_" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor DarkGray
    exit 1
}

