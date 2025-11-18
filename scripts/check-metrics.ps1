# check-metrics.ps1
# Проверка метрик: события, виды, p50/p95
# Usage: .\check-metrics.ps1

$ErrorActionPreference = "Stop"

Write-Host "`n=== Metrics Check Script ===`n" -ForegroundColor Cyan

# 1. Проверка Docker контейнера
Write-Host "[1/5] Checking Docker container..." -ForegroundColor Yellow
try {
    $containerStatus = docker compose ps api --format json 2>&1 | ConvertFrom-Json
    if ($containerStatus.State -ne "running") {
        Write-Host "  ❌ API container not running. State: $($containerStatus.State)" -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✅ API container running" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Failed to check container: $_" -ForegroundColor Red
    exit 1
}

# 2. Проверка файла метрик
Write-Host "`n[2/5] Checking metrics file..." -ForegroundColor Yellow
$metricsDate = Get-Date -Format "yyyy-MM-dd"
$metricsPath = "/app/logs/metrics/$metricsDate/api.jsonl"

try {
    $lineCount = docker compose exec api sh -c "wc -l $metricsPath 2>/dev/null | awk '{print `$1}'" 2>&1
    if (-not $lineCount -or $lineCount -eq "0") {
        Write-Host "  ⚠️  Metrics file not found or empty: $metricsPath" -ForegroundColor Yellow
        Write-Host "  Creating sample events..." -ForegroundColor Yellow
        
        # Генерация тестовых событий через health endpoint
        $base = "http://127.0.0.1:8088"
        1..5 | ForEach-Object { 
            Invoke-RestMethod -Uri "$base/health" -ErrorAction SilentlyContinue | Out-Null
            Start-Sleep -Milliseconds 100
        }
        
        $lineCount = docker compose exec api sh -c "wc -l $metricsPath 2>/dev/null | awk '{print `$1}'" 2>&1
    }
    
    Write-Host "  ✅ Metrics file: $lineCount events" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Failed to check metrics file: $_" -ForegroundColor Red
    exit 1
}

# 3. Подсчёт событий и видов
Write-Host "`n[3/5] Counting events and kinds..." -ForegroundColor Yellow
try {
    $pythonScript = @"
import json
from collections import Counter

try:
    with open('$metricsPath', 'r') as f:
        kinds = [json.loads(line)['kind'] for line in f]
    
    c = Counter(kinds)
    total = sum(c.values())
    unique = len(c)
    
    print(f'TOTAL={total}')
    print(f'KINDS={unique}')
    
    for kind, count in c.most_common():
        print(f'KIND|{kind}|{count}')
except FileNotFoundError:
    print('TOTAL=0')
    print('KINDS=0')
except Exception as e:
    print(f'ERROR={e}')
"@

    $output = docker compose exec api python3 -c $pythonScript 2>&1
    
    $total = 0
    $kinds = 0
    $kindList = @()
    
    foreach ($line in $output) {
        if ($line -match "TOTAL=(\d+)") { $total = [int]$matches[1] }
        if ($line -match "KINDS=(\d+)") { $kinds = [int]$matches[1] }
        if ($line -match "KIND\|([^|]+)\|(\d+)") {
            $kindList += [PSCustomObject]@{
                Kind = $matches[1]
                Count = [int]$matches[2]
            }
        }
        if ($line -match "ERROR=(.+)") {
            Write-Host "  ❌ Python error: $($matches[1])" -ForegroundColor Red
            exit 1
        }
    }
    
    Write-Host "  Total events: $total" -ForegroundColor White
    Write-Host "  Unique kinds: $kinds" -ForegroundColor White
    
    if ($total -eq 0) {
        Write-Host "  ❌ No events found" -ForegroundColor Red
        exit 1
    }
    
    if ($kinds -lt 5) {
        Write-Host "  ⚠️  Only $kinds kinds (minimum 5 required)" -ForegroundColor Yellow
    } else {
        Write-Host "  ✅ Sufficient kinds: $kinds" -ForegroundColor Green
    }
    
    Write-Host "`n  Event distribution:" -ForegroundColor Cyan
    foreach ($item in $kindList) {
        $pct = [math]::Round(($item.Count / $total) * 100, 1)
        Write-Host "    $($item.Kind): $($item.Count) ($pct%)" -ForegroundColor Gray
    }
    
} catch {
    Write-Host "  ❌ Failed to count events: $_" -ForegroundColor Red
    exit 1
}

# 4. Вычисление p50/p95
Write-Host "`n[4/5] Calculating p50/p95 latencies..." -ForegroundColor Yellow
try {
    $latencyScript = @"
import json
from statistics import median, quantiles

try:
    with open('$metricsPath', 'r') as f:
        latencies = [json.loads(line).get('latency_ms', 0) for line in f]
    
    lat_sorted = sorted([l for l in latencies if l > 0])
    
    if lat_sorted:
        p50 = median(lat_sorted)
        p95 = quantiles(lat_sorted, n=20)[18] if len(lat_sorted) >= 20 else max(lat_sorted)
        print(f'P50={p50:.2f}')
        print(f'P95={p95:.2f}')
        print(f'COUNT={len(lat_sorted)}')
    else:
        print('P50=0.00')
        print('P95=0.00')
        print('COUNT=0')
except Exception as e:
    print(f'ERROR={e}')
"@

    $latOutput = docker compose exec api python3 -c $latencyScript 2>&1
    
    $p50 = 0.0
    $p95 = 0.0
    $latCount = 0
    
    foreach ($line in $latOutput) {
        if ($line -match "P50=([\d.]+)") { $p50 = [double]$matches[1] }
        if ($line -match "P95=([\d.]+)") { $p95 = [double]$matches[1] }
        if ($line -match "COUNT=(\d+)") { $latCount = [int]$matches[1] }
    }
    
    Write-Host "  p50: $p50 ms" -ForegroundColor White
    Write-Host "  p95: $p95 ms" -ForegroundColor White
    Write-Host "  Latency samples: $latCount" -ForegroundColor Gray
    
    if ($latCount -eq 0) {
        Write-Host "  ⚠️  No latency data (events may not record latency_ms)" -ForegroundColor Yellow
    } else {
        Write-Host "  ✅ Latency data available" -ForegroundColor Green
    }
    
} catch {
    Write-Host "  ❌ Failed to calculate latencies: $_" -ForegroundColor Red
    # Non-fatal, continue
}

# 5. Генерация итогового отчёта
Write-Host "`n[5/5] Summary Report" -ForegroundColor Yellow
Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

$pass = $true
$warnings = @()

# Check 1: Total events ≥24
if ($total -ge 24) {
    Write-Host "  ✅ Total events: $total (≥24)" -ForegroundColor Green
} else {
    Write-Host "  ❌ Total events: $total (<24)" -ForegroundColor Red
    $pass = $false
}

# Check 2: Unique kinds ≥5
if ($kinds -ge 5) {
    Write-Host "  ✅ Unique kinds: $kinds (≥5)" -ForegroundColor Green
} else {
    Write-Host "  ❌ Unique kinds: $kinds (<5)" -ForegroundColor Red
    $pass = $false
}

# Check 3: Latency data (warning only)
if ($latCount -gt 0) {
    Write-Host "  ✅ Latency data: $latCount samples" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  Latency data: 0 samples (no p50/p95)" -ForegroundColor Yellow
    $warnings += "No latency data available"
}

Write-Host "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# Final verdict
if ($pass) {
    Write-Host "`n✅ METRICS CHECK PASSED" -ForegroundColor Green
    if ($warnings.Count -gt 0) {
        Write-Host "Warnings:" -ForegroundColor Yellow
        $warnings | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    }
    exit 0
} else {
    Write-Host "`n❌ METRICS CHECK FAILED" -ForegroundColor Red
    Write-Host "Fix the issues above and re-run." -ForegroundColor Red
    exit 1
}
