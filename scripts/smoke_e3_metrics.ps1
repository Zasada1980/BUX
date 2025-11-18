#!/usr/bin/env pwsh
<#
.SYNOPSIS
    E3 Admin Metrics Dashboard Smoke Test
.DESCRIPTION
    Validates:
    - 401 without X-Admin-Secret
    - 403 with wrong secret
    - 200 with correct secret
    - Table fragment contains <table id="tbl">
    - JSON rollup (optional)
#>

$ErrorActionPreference = "Stop"
$start = [Environment]::TickCount64

$base = "http://127.0.0.1:8088"
$correctSecret = "change-me"
$wrongSecret = "wrong-secret"

$script:results = @()

function Test-Case($name, $condition, $details) {
    $status = if ($condition) { "PASS" } else { "FAIL" }
    $script:results += [PSCustomObject]@{ Test = $name; Status = $status; Details = $details }
    
    $icon = if ($condition) { "✓" } else { "✗" }
    $color = if ($condition) { "Green" } else { "Red" }
    Write-Host "[$icon] $name" -ForegroundColor $color
    if ($details) { Write-Host "    $details" -ForegroundColor Gray }
}

Write-Host "`n=== E3 Admin Metrics Dashboard Smoke Test ===" -ForegroundColor Cyan

# Test 1: 401 without X-Admin-Secret
Write-Host "`n[Test 1] 401 without X-Admin-Secret" -ForegroundColor Yellow
try {
    $resp = Invoke-WebRequest -Uri "$base/admin/metrics" -Method Get -SkipHttpErrorCheck
    $is401 = $resp.StatusCode -eq 401
    Test-Case "T1: 401 without secret" $is401 "Status: $($resp.StatusCode)"
} catch {
    Test-Case "T1: 401 without secret" $false "Error: $_"
}

# Test 2: 403 with wrong secret
Write-Host "`n[Test 2] 403 with wrong X-Admin-Secret" -ForegroundColor Yellow
try {
    $headers = @{ "X-Admin-Secret" = $wrongSecret }
    $resp = Invoke-WebRequest -Uri "$base/admin/metrics" -Headers $headers -Method Get -SkipHttpErrorCheck
    $is403 = $resp.StatusCode -eq 403
    Test-Case "T2: 403 with wrong secret" $is403 "Status: $($resp.StatusCode)"
} catch {
    Test-Case "T2: 403 with wrong secret" $false "Error: $_"
}

# Test 3: 200 with correct secret + validate "Admin Metrics" header
Write-Host "`n[Test 3] 200 with correct secret + validate header" -ForegroundColor Yellow
try {
    $headers = @{ "X-Admin-Secret" = $correctSecret }
    $resp = Invoke-WebRequest -Uri "$base/admin/metrics" -Headers $headers -Method Get
    $is200 = $resp.StatusCode -eq 200
    $hasHeader = $resp.Content -match "Admin Metrics Dashboard"
    Test-Case "T3: 200 with correct secret" $is200 "Status: $($resp.StatusCode)"
    Test-Case "T3: Header contains 'Admin Metrics Dashboard'" $hasHeader ""
} catch {
    Test-Case "T3: 200 with correct secret" $false "Error: $_"
    Test-Case "T3: Header validation" $false "Failed to fetch"
}

# Test 4: Table fragment validation
Write-Host "`n[Test 4] Table fragment contains <table id=`"tbl`">" -ForegroundColor Yellow
try {
    $headers = @{ "X-Admin-Secret" = $correctSecret }
    $resp = Invoke-WebRequest -Uri "$base/admin/metrics/table?window=1h" -Headers $headers -Method Get
    $hasTable = $resp.Content -match '<table id="tbl">'
    $hasColumns = $resp.Content -match '<th>Kind</th>' -and 
                  $resp.Content -match '<th class="numeric">Count</th>' -and
                  $resp.Content -match '<th class="numeric">p95 \(ms\)</th>'
    Test-Case "T4: Fragment contains <table id='tbl'>" $hasTable ""
    Test-Case "T4: Fragment has required columns" $hasColumns "Kind, Count, p95"
} catch {
    Test-Case "T4: Fragment validation" $false "Error: $_"
}

# Test 5: JSON rollup validation (optional)
Write-Host "`n[Test 5] JSON rollup validation (optional)" -ForegroundColor Yellow
try {
    $headers = @{ "X-Admin-Secret" = $correctSecret }
    $resp = Invoke-RestMethod -Uri "$base/api/admin/metrics.rollup?window=24h" -Headers $headers -Method Get
    $hasWindow = $null -ne $resp.window
    $hasRows = $null -ne $resp.rows
    Test-Case "T5: JSON has 'window' field" $hasWindow ""
    Test-Case "T5: JSON has 'rows' array" $hasRows "Count: $($resp.rows.Count)"
} catch {
    Test-Case "T5: JSON validation (optional)" $false "Error: $_"
}

# Summary
$elapsed = [Environment]::TickCount64 - $start
$passed = ($script:results | Where-Object { $_.Status -eq "PASS" }).Count
$total = $script:results.Count

Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "Passed: $passed / $total" -ForegroundColor $(if ($passed -eq $total) { "Green" } else { "Yellow" })
Write-Host "Time: ${elapsed}ms`n" -ForegroundColor Gray

# Save artifact
$artifactDir = "logs"
if (-not (Test-Path $artifactDir)) { New-Item -ItemType Directory -Path $artifactDir | Out-Null }

$artifact = @"
=== E3 Admin Metrics Dashboard Smoke Test ===
Date: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Duration: ${elapsed}ms
Results: $passed / $total PASS

Tests:
$($script:results | ForEach-Object { "[$($_.Status)] $($_.Test) - $($_.Details)" } | Out-String)
"@

$artifactPath = Join-Path $artifactDir "smoke_e3_metrics.txt"
$artifact | Out-File -FilePath $artifactPath -Encoding utf8
Write-Host "Artifact: $artifactPath" -ForegroundColor Cyan

# Exit code
exit $(if ($passed -eq $total) { 0 } else { 1 })
