<#
.SYNOPSIS
    Restore SQLite database from backup via Docker container
.DESCRIPTION
    Stops API, restores database atomically, restarts API
.PARAMETER DbPath
    Database path (default: from .env DB_PATH)
.PARAMETER BackupFile
    Backup file path (required, relative to container /app/)
.EXAMPLE
    .\scripts\restore.ps1 -BackupFile "backups/20250113-1200-db.sqlite3"
#>
param(
    [string]$DbPath = "",
    [Parameter(Mandatory=$true)]
    [string]$BackupFile
)

$ErrorActionPreference = "Stop"
$t0 = [Environment]::TickCount64

try {
    # Read DB_PATH from .env if not provided
    if (-not $DbPath) {
        $envLine = Get-Content .env -ErrorAction SilentlyContinue | Where-Object { $_ -match '^DB_PATH=' }
        if ($envLine) {
            $DbPath = $envLine.ToString().Split('=', 2)[1]
        } else {
            throw "DB_PATH not found in .env"
        }
    }

    # Convert Windows path to container path (/app is mounted from api/)
    $containerPath = $BackupFile -replace '\\', '/'
    # Backups are in /app/backups inside container
    $containerPath = "/app/$containerPath"
    
    Write-Host "🔄 Restoring database: $BackupFile → $DbPath"
    Write-Host "  Container path: $containerPath" -ForegroundColor DarkGray
    
    # Stop API for safe restoration
    Write-Host "⏸️  Stopping API container..."
    docker compose stop api | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to stop API container"
    }

    # Execute restore via Docker (/app maps to api/ locally)
    # Use docker compose run --rm for one-shot execution
    Write-Host "🔄 Executing restore..."
    $result = docker compose run --rm -T api python scripts/backup_restore.py restore --db $DbPath --file $containerPath
    
    if ($LASTEXITCODE -ne 0) {
        throw "Restore command failed with exit code $LASTEXITCODE"
    }

    # Restart API
    Write-Host "▶️  Starting API container..."
    docker compose start api | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start API container"
    }

    # Wait for API to be ready
    Start-Sleep -Seconds 2

    $elapsed = [Environment]::TickCount64 - $t0
    Write-Host "✅ Restore complete"
    Write-Host "Время: ${elapsed}ms"
    
    # Output JSON for script chaining
    $result

} catch {
    $elapsed = [Environment]::TickCount64 - $t0
    Write-Host "❌ Restore failed: $_" -ForegroundColor Red
    Write-Host "Время: ${elapsed}ms"
    
    # Try to restart API even on failure
    Write-Host "⚠️  Attempting to restart API..."
    docker compose start api | Out-Null
    
    exit 1
}
