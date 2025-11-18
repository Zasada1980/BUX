# G2 Gold ILS Orchestrator
# One-button script: seed → generate → schema-lint → 3× pin → SHA manifest
# Usage: .\run-g2-gold.ps1 [-NoSeed]

Param(
    [switch]$NoSeed
)

$ErrorActionPreference = 'Stop'
$LogDir = "logs"

# Ensure logs directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

Write-Host "`n════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  G2 Gold ILS - Deterministic Dataset Generator" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════════════════════`n" -ForegroundColor Cyan

# Timing wrapper (Guardian Protocol compliance)
$t0 = [Environment]::TickCount64

# Pre-flight check: API server availability
Write-Host "[Preflight] Checking API server availability..." -ForegroundColor Yellow
$tCheck = [Environment]::TickCount64
try {
    $null = Invoke-RestMethod -Uri "http://127.0.0.1:8088/docs" -Method Get -TimeoutSec 3 -ErrorAction Stop
    $tCheckEnd = [Environment]::TickCount64 - $tCheck
    Write-Host "✅ API server online (${tCheckEnd}ms)`n" -ForegroundColor Green
} catch {
    $tCheckEnd = [Environment]::TickCount64 - $tCheck
    Write-Host "❌ API server not reachable (${tCheckEnd}ms)" -ForegroundColor Red
    Write-Host "   Start server: python -m uvicorn main:app --host 127.0.0.1 --port 8088" -ForegroundColor Yellow
    exit 1
}

# Step 1: Seed data (unless -NoSeed)
if (-not $NoSeed) {
    Write-Host "[Step 1/4] Seeding deterministic test data..." -ForegroundColor Yellow
    $tSeed = [Environment]::TickCount64
    try {
        .\seeds\seed_gold_ils.ps1
        $tSeedEnd = [Environment]::TickCount64 - $tSeed
        Write-Host "✅ Seed: COMPLETE (${tSeedEnd}ms)`n" -ForegroundColor Green
    } catch {
        $tSeedEnd = [Environment]::TickCount64 - $tSeed
        Write-Host "❌ Seed failed (${tSeedEnd}ms): $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[Step 1/4] Skipping seed (NoSeed flag)" -ForegroundColor Yellow
}

# Step 2: Generate expected.jsonl with schema-lint
Write-Host "[Step 2/4] Generating expected.jsonl (schema-lint)..." -ForegroundColor Yellow
$tGen = [Environment]::TickCount64
try {
    $genOutput = python ai_eval\gold_ils\gen_gold_ils.py 2>&1
    $tGenEnd = [Environment]::TickCount64 - $tGen
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Generation failed (${tGenEnd}ms)" -ForegroundColor Red
        Write-Host $genOutput -ForegroundColor Red
        exit 1
    }
    Write-Host $genOutput
    Write-Host "✅ Generation: COMPLETE (${tGenEnd}ms)`n" -ForegroundColor Green
} catch {
    $tGenEnd = [Environment]::TickCount64 - $tGen
    Write-Host "❌ Generation failed (${tGenEnd}ms): $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 3: Run 3× pin check (determinism)
Write-Host "[Step 3/4] Running 3× pin check (determinism)..." -ForegroundColor Yellow
$tPin = [Environment]::TickCount64
try {
    $pinOutput = python ai_eval\gold_ils\pin_run.py 2>&1
    $tPinEnd = [Environment]::TickCount64 - $tPin
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Pin check failed (${tPinEnd}ms)" -ForegroundColor Red
        Write-Host $pinOutput -ForegroundColor Red
        exit 1
    }
    Write-Host $pinOutput
    Write-Host "✅ Pin check: COMPLETE (${tPinEnd}ms)`n" -ForegroundColor Green
} catch {
    $tPinEnd = [Environment]::TickCount64 - $tPin
    Write-Host "❌ Pin check failed (${tPinEnd}ms): $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Step 4: Generate SHA256 manifest
Write-Host "[Step 4/4] Generating SHA256 manifest..." -ForegroundColor Yellow
$tManifest = [Environment]::TickCount64
$files = @(
    "ai_eval\gold_ils\schema.item_details.json",
    "ai_eval\gold_ils\cases.jsonl",
    "ai_eval\gold_ils\expected.jsonl",
    "ai_eval\gold_ils\gen_gold_ils.py",
    "ai_eval\gold_ils\pin_run.py",
    "logs\g2_expected_sha.txt",
    "logs\g2_pin_summary.txt"
)

$manifest = @()
foreach ($f in $files) {
    if (Test-Path $f) {
        $hash = (Get-FileHash -Algorithm SHA256 $f).Hash
        $name = Split-Path $f -Leaf
        $manifest += "$hash  $name"
    } else {
        Write-Host "  ⚠️  Missing file: $f" -ForegroundColor Yellow
    }
}

$manifestPath = "$LogDir\g2_sha_manifest.txt"
$manifest | Out-File -FilePath $manifestPath -Encoding utf8
$tManifestEnd = [Environment]::TickCount64 - $tManifest

Write-Host "✅ SHA256 manifest: $manifestPath (${tManifestEnd}ms)`n" -ForegroundColor Green

# Write completion marker
"OK" | Out-File -FilePath "$LogDir\g2_done.txt" -Encoding utf8

# Timing
$t1 = [Environment]::TickCount64 - $t0

Write-Host "`n════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  ✅ G2 Gold ILS: COMPLETE ($t1 ms)" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════`n" -ForegroundColor Cyan

Write-Host "📦 Artifacts:" -ForegroundColor Cyan
Write-Host "   expected.jsonl:     ai_eval\gold_ils\expected.jsonl" -ForegroundColor White
Write-Host "   SHA12 hash:         $LogDir\g2_expected_sha.txt" -ForegroundColor White
Write-Host "   Pin summary (3×):   $LogDir\g2_pin_summary.txt" -ForegroundColor White
Write-Host "   SHA256 manifest:    $LogDir\g2_sha_manifest.txt" -ForegroundColor White
Write-Host "`n"
