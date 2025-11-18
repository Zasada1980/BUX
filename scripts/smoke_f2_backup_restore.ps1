<#
.SYNOPSIS
    F2 Smoke Test: Backup → Drop DB → Restore → Validate
.DESCRIPTION
    Tests backup/restore cycle with data integrity validation
    S39 Gate validation for F2 feature
.PARAMETER Base
    API base URL (default: http://127.0.0.1:8088)
.PARAMETER Secret
    Admin secret from .env (auto-detected)
.EXAMPLE
    .\scripts\smoke_f2_backup_restore.ps1
    .\scripts\smoke_f2_backup_restore.ps1 -Base "http://localhost:8088"
#>
param(
    [string]$Base = "http://127.0.0.1:8088",
    [string]$Secret = ""
)

$ErrorActionPreference = "Stop"
$t0 = [Environment]::TickCount64
$logFile = "logs\smoke_f2_backup_restore.txt"

function Write-Log {
    param([string]$msg)
    $msg | Tee-Object -FilePath $logFile -Append
}

try {
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "🧪 F2 Smoke Test: Backup/Restore Cycle" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""

    # Read admin secret from .env if not provided
    if (-not $Secret) {
        $secretLine = Get-Content .env -ErrorAction SilentlyContinue | Where-Object { $_ -match '^INTERNAL_ADMIN_SECRET=' }
        if ($secretLine) {
            $Secret = $secretLine.ToString().Split('=', 2)[1]
        } else {
            throw "INTERNAL_ADMIN_SECRET not found in .env"
        }
    }

    # Read DB_PATH from .env
    $dbPathLine = Get-Content .env -ErrorAction SilentlyContinue | Where-Object { $_ -match '^DB_PATH=' }
    if (-not $dbPathLine) {
        throw "DB_PATH not found in .env"
    }
    $dbPath = $dbPathLine.ToString().Split('=', 2)[1]

    Write-Host "📊 Config:"
    Write-Host "  API: $Base"
    Write-Host "  DB: $dbPath"
    Write-Host ""

    # Test 1: Health check before backup
    Write-Host "Test 1: Pre-backup health check..." -NoNewline
    try {
        $health = Invoke-RestMethod -Uri "$Base/health" -Method Get -TimeoutSec 5
        Write-Host " ✓" -ForegroundColor Green
        Write-Log "Test 1: Health check PASS"
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        throw "Health check failed: $_"
    }

    # Test 2: Count records before backup (using sqlite3 in container)
    Write-Host "Test 2: Count records before backup..." -NoNewline
    try {
        $countBefore = docker compose exec -T api sqlite3 $dbPath "SELECT COUNT(*) FROM shifts;" 2>$null
        if ($LASTEXITCODE -ne 0) {
            # Try invoices table if shifts doesn't exist
            $countBefore = docker compose exec -T api sqlite3 $dbPath "SELECT COUNT(*) FROM invoices;" 2>$null
            $table = "invoices"
        } else {
            $table = "shifts"
        }
        $countBefore = $countBefore.Trim()
        Write-Host " ✓ ($table`: $countBefore records)" -ForegroundColor Green
        Write-Log "Test 2: Before count=$countBefore table=$table"
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        throw "Count query failed: $_"
    }

    # Test 3: Create backup
    Write-Host "Test 3: Create backup..." -NoNewline
    try {
        # Capture only stdout (JSON), ignore stderr (progress messages)
        $backupJson = .\scripts\backup.ps1 2>&1 | Where-Object { $_ -match '^\{.*"ok".*\}$' } | Select-Object -Last 1
        if (-not $backupJson) {
            throw "No JSON output from backup.ps1"
        }
        $backup = $backupJson | ConvertFrom-Json
        if (-not $backup.ok) {
            throw "Backup failed"
        }
        $backupFile = $backup.file
        Write-Host " ✓" -ForegroundColor Green
        Write-Host "  📁 Backup: $backupFile" -ForegroundColor DarkGray
        Write-Log "Test 3: Backup created at $backupFile"
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        throw "Backup creation failed: $_"
    }

    # Test 4: Verify backup file exists
    Write-Host "Test 4: Verify backup file..." -NoNewline
    try {
        if (-not (Test-Path $backupFile)) {
            throw "Backup file not found: $backupFile"
        }
        $size = (Get-Item $backupFile).Length
        Write-Host " ✓ (${size} bytes)" -ForegroundColor Green
        Write-Log "Test 4: Backup file verified, size=$size"
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        throw $_
    }

    # Test 5: Delete database (simulate disaster)
    Write-Host "Test 5: Simulate disaster (delete DB)..." -NoNewline
    try {
        # Delete via container
        docker compose exec -T api rm -f $dbPath 2>&1 | Out-Null
        Write-Host " ✓" -ForegroundColor Green
        Write-Log "Test 5: Database deleted (disaster simulation)"
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        throw "DB deletion failed: $_"
    }

    # Test 6: Restore from backup
    Write-Host "Test 6: Restore from backup..." -NoNewline
    try {
        $restoreResult = .\scripts\restore.ps1 -BackupFile $backupFile 2>&1 | Out-String
        # Check if restore script succeeded (exit code already checked in script)
        Write-Host " ✓" -ForegroundColor Green
        Write-Log "Test 6: Restore completed"
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        throw "Restore failed: $_"
    }

    # Test 7: Health check after restore
    Write-Host "Test 7: Post-restore health check..." -NoNewline
    try {
        Start-Sleep -Seconds 2  # Wait for API to be ready
        $healthAfter = Invoke-RestMethod -Uri "$Base/health" -Method Get -TimeoutSec 5
        Write-Host " ✓" -ForegroundColor Green
        Write-Log "Test 7: Post-restore health check PASS"
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        throw "Post-restore health check failed: $_"
    }

    # Test 8: Verify record count matches
    Write-Host "Test 8: Verify data integrity..." -NoNewline
    try {
        $countAfter = docker compose exec -T api sqlite3 $dbPath "SELECT COUNT(*) FROM $table;" 2>$null
        $countAfter = $countAfter.Trim()
        if ($countBefore -ne $countAfter) {
            throw "Count mismatch: before=$countBefore after=$countAfter"
        }
        Write-Host " ✓ ($table`: $countAfter records)" -ForegroundColor Green
        Write-Log "Test 8: Data integrity verified, count=$countAfter"
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        throw $_
    }

    # Test 9: Verify manifest.jsonl
    Write-Host "Test 9: Verify backup manifest..." -NoNewline
    try {
        $manifestPath = "backups\manifest.jsonl"
        if (-not (Test-Path $manifestPath)) {
            throw "Manifest not found: $manifestPath"
        }
        $lastEntry = Get-Content $manifestPath | Select-Object -Last 1 | ConvertFrom-Json
        if (-not $lastEntry.sha256) {
            throw "Manifest entry missing SHA256"
        }
        Write-Host " ✓ (SHA256: $($lastEntry.sha256.Substring(0,16))...)" -ForegroundColor Green
        Write-Log "Test 9: Manifest verified, sha256=$($lastEntry.sha256)"
    } catch {
        Write-Host " ✗" -ForegroundColor Red
        throw "Manifest verification failed: $_"
    }

    $elapsed = [Environment]::TickCount64 - $t0
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "✅ S39 PASS: Backup/Restore" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "Время: ${elapsed}ms"
    Write-Host "Артефакт: $logFile"
    Write-Log "`n✅ S39 PASS | Время: ${elapsed}ms"

    exit 0

} catch {
    $elapsed = [Environment]::TickCount64 - $t0
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host "❌ S39 FAIL: $_" -ForegroundColor Red
    Write-Host "═══════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host "Время: ${elapsed}ms"
    Write-Log "`n❌ S39 FAIL: $_ | Время: ${elapsed}ms"
    
    exit 1
}
