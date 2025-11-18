#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Smoke test for HTMX invoice admin views (E2 gate S37).
.DESCRIPTION
    Tests three HTMX endpoints:
    - /admin/invoices/{id} - Main page
    - /admin/invoices/{id}/preview - Preview fragment
    - /admin/invoices/{id}/diff - Diff fragment
    Saves artifacts to logs/ for validation.
.PARAMETER Base
    API base URL (default: http://127.0.0.1:8088)
.PARAMETER Id
    Invoice ID to test (default: 1)
#>
param(
    [string]$Base = "http://127.0.0.1:8088",
    [int]$Id = 1
)

$ErrorActionPreference = "Stop"

try {
    $t0 = [Environment]::TickCount64
    
    Write-Host "`n=== HTMX Invoice Admin Smoke Test (S37) ===" -ForegroundColor Cyan
    Write-Host "Target: $Base/admin/invoices/$Id" -ForegroundColor Gray
    
    # Ensure logs directory exists
    $logDir = "logs"
    if (-not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir | Out-Null
    }
    
    # Test 1: Main invoice page
    Write-Host "`n[1/3] Fetching main invoice page..." -ForegroundColor Yellow
    $rootResponse = Invoke-WebRequest -Uri "$Base/admin/invoices/$Id" -UseBasicParsing -TimeoutSec 10
    
    if ($rootResponse.StatusCode -ne 200) {
        throw "Main page request failed: HTTP $($rootResponse.StatusCode)"
    }
    
    $rootPath = Join-Path $logDir "e2_invoice_page.html"
    $rootResponse.Content | Set-Content -Path $rootPath -Encoding UTF8
    Write-Host "   ✅ Main page saved: $rootPath" -ForegroundColor Green
    
    # Validate main page contains HTMX
    if ($rootResponse.Content -notmatch "htmx.org") {
        throw "Main page missing HTMX script tag"
    }
    
    # Test 2: Preview fragment
    Write-Host "`n[2/3] Fetching invoice preview fragment..." -ForegroundColor Yellow
    $previewResponse = Invoke-WebRequest -Uri "$Base/admin/invoices/$Id/preview" -UseBasicParsing -TimeoutSec 10
    
    if ($previewResponse.StatusCode -ne 200) {
        throw "Preview request failed: HTTP $($previewResponse.StatusCode)"
    }
    
    $previewPath = Join-Path $logDir "e2_invoice_preview.html"
    $previewResponse.Content | Set-Content -Path $previewPath -Encoding UTF8
    Write-Host "   ✅ Preview fragment saved: $previewPath" -ForegroundColor Green
    
    # Test 3: Diff fragment
    Write-Host "`n[3/3] Fetching invoice diff fragment..." -ForegroundColor Yellow
    $diffResponse = Invoke-WebRequest -Uri "$Base/admin/invoices/$Id/diff?from=v1&to=v2" -UseBasicParsing -TimeoutSec 10
    
    if ($diffResponse.StatusCode -ne 200) {
        throw "Diff request failed: HTTP $($diffResponse.StatusCode)"
    }
    
    $diffPath = Join-Path $logDir "e2_invoice_diff.html"
    $diffResponse.Content | Set-Content -Path $diffPath -Encoding UTF8
    Write-Host "   ✅ Diff fragment saved: $diffPath" -ForegroundColor Green
    
    # Validate diff contains table
    if ($diffResponse.Content -notmatch "<table>") {
        Write-Host "   ⚠️  Warning: Diff does not contain <table> (might be 'no changes' message)" -ForegroundColor Yellow
    }
    
    # Generate artifact hashes
    Write-Host "`n📊 Artifact hashes:" -ForegroundColor Cyan
    $artifacts = @($rootPath, $previewPath, $diffPath)
    $hashes = $artifacts | Get-FileHash -Algorithm SHA256
    
    foreach ($hash in $hashes) {
        $fileName = Split-Path $hash.Path -Leaf
        $shortHash = $hash.Hash.Substring(0, 16)
        Write-Host "   $shortHash  $fileName" -ForegroundColor Gray
    }
    
    $elapsed = [Environment]::TickCount64 - $t0
    
    Write-Host "`n✅ S37 PASS: HTMX invoice view+diff" -ForegroundColor Green
    Write-Host "   Endpoints tested: 3/3" -ForegroundColor White
    Write-Host "   Artifacts: $($artifacts.Count)" -ForegroundColor White
    Write-Host "`nВремя: ${elapsed}ms" -ForegroundColor Gray
    
    exit 0
}
catch {
    Write-Host "`n❌ S37 FAIL: $_" -ForegroundColor Red
    exit 1
}
