<#
.SYNOPSIS
    Create SQLite backup via Docker container
.DESCRIPTION
    Wraps api.scripts.backup_restore backup command, reads DB_PATH from .env
.PARAMETER DbPath
    Database path (default: from .env DB_PATH)
.PARAMETER OutDir
    Output directory for backups (default: backups)
.EXAMPLE
    .\scripts\backup.ps1
    .\scripts\backup.ps1 -DbPath "data/shifts.db" -OutDir "backups"
#>
param(
    [string]$DbPath = "",
    [string]$OutDir = "backups"
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

    Write-Host "🔄 Creating backup: DB=$DbPath → $OutDir" -ForegroundColor Cyan
    
    # Execute backup via Docker (/app maps to api/ locally)
    $result = docker compose exec -T api python scripts/backup_restore.py backup --db $DbPath --out $OutDir 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        throw "Backup command failed with exit code $LASTEXITCODE"
    }

    $elapsed = [Environment]::TickCount64 - $t0
    Write-Host "✅ Backup complete (${elapsed}ms)" -ForegroundColor Green
    
    # Output ONLY JSON to stdout for script chaining
    Write-Output $result

} catch {
    $elapsed = [Environment]::TickCount64 - $t0
    Write-Host "❌ Backup failed: $_" -ForegroundColor Red
    Write-Host "Время: ${elapsed}ms"
    exit 1
}
