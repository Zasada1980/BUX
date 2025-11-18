#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Smoke test for OCR Docker integration (F1 gate S36).
.DESCRIPTION
    Verifies tesseract installation in API container via /api/ocr.health endpoint.
    Checks for version presence and eng+rus language packs.
.PARAMETER Base
    API base URL (default: http://127.0.0.1:8088)
#>
param(
    [string]$Base = "http://127.0.0.1:8088"
)

$ErrorActionPreference = "Stop"

try {
    $t0 = [Environment]::TickCount64
    
    Write-Host "`n=== OCR Docker Smoke Test (S36) ===" -ForegroundColor Cyan
    Write-Host "Target: $Base/api/ocr.health" -ForegroundColor Gray
    
    # Call health endpoint
    $response = Invoke-RestMethod -Uri "$Base/api/ocr.health" -Method Get -TimeoutSec 5
    
    # Validate response structure
    if (-not $response.tesseract) {
        throw "OCR health FAIL: tesseract version missing"
    }
    
    if (-not $response.langs) {
        throw "OCR health FAIL: langs array missing"
    }
    
    # Check for required languages
    $hasEng = $response.langs -contains "eng"
    $hasRus = $response.langs -contains "rus"
    
    if (-not $hasEng) {
        throw "OCR health FAIL: eng language pack missing (found: $($response.langs -join ', '))"
    }
    
    if (-not $hasRus) {
        throw "OCR health FAIL: rus language pack missing (found: $($response.langs -join ', '))"
    }
    
    # Check status field
    if ($response.status -ne "ok") {
        throw "OCR health FAIL: status=$($response.status), expected 'ok'"
    }
    
    # Success - write artifact
    $logDir = "logs"
    if (-not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir | Out-Null
    }
    
    $artifactPath = Join-Path $logDir "smoke_ocr_docker.txt"
    $summary = "OK OCR: $($response.tesseract) :: $($response.langs -join ',')"
    $summary | Set-Content -Path $artifactPath -Encoding UTF8
    
    $elapsed = [Environment]::TickCount64 - $t0
    
    Write-Host "`n✅ S36 PASS: OCR Docker integration" -ForegroundColor Green
    Write-Host "   Tesseract: $($response.tesseract)" -ForegroundColor White
    Write-Host "   Languages: $($response.langs -join ', ')" -ForegroundColor White
    Write-Host "   Artifact: $artifactPath" -ForegroundColor Gray
    Write-Host "`nВремя: ${elapsed}ms" -ForegroundColor Gray
    
    exit 0
}
catch {
    Write-Host "`n❌ S36 FAIL: $_" -ForegroundColor Red
    exit 1
}
