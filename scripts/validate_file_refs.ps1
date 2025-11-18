#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Validate file references across documentation and scripts
.DESCRIPTION
    Checks:
    - All smoke_*.ps1 references in ROADMAP_TASKS_FULL.md exist
    - All file paths in check-skeptic.ps1 exist
    - FILE_INDEX.md is synchronized with actual files
    - No duplicate filenames across directories
    - All S-gate mappings have corresponding files
.EXAMPLE
    .\validate_file_refs.ps1
    # Checks all file references and reports errors
.NOTES
    Exit code 0 = all valid, 1 = errors found
#>

$ErrorActionPreference = "Stop"
$errors = @()
$warnings = @()

Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          FILE REFERENCE VALIDATION                            ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

# ══════════════════════════════════════════════════════════════════════════
# 1. Check ROADMAP_TASKS_FULL.md references
# ══════════════════════════════════════════════════════════════════════════
Write-Host "[1/6] Checking ROADMAP_TASKS_FULL.md references..." -ForegroundColor Yellow

if (Test-Path ROADMAP_TASKS_FULL.md) {
    $roadmap = Get-Content ROADMAP_TASKS_FULL.md -Raw
    $smokeRefs = [regex]::Matches($roadmap, '`smoke_\w+\.ps1`') | ForEach-Object { $_.Value.Trim('`') } | Sort-Object -Unique
    
    foreach ($ref in $smokeRefs) {
        $path = "scripts\$ref"
        if (-not (Test-Path $path)) {
            $errors += "ROADMAP references non-existent: $ref (expected at $path)"
        } else {
            Write-Host "  ✓ $ref" -ForegroundColor Green
        }
    }
    
    Write-Host "  Found $($smokeRefs.Count) smoke script references" -ForegroundColor Gray
} else {
    $warnings += "ROADMAP_TASKS_FULL.md not found"
}

# ══════════════════════════════════════════════════════════════════════════
# 2. Check check-skeptic.ps1 file paths
# ══════════════════════════════════════════════════════════════════════════
Write-Host "`n[2/6] Checking check-skeptic.ps1 file paths..." -ForegroundColor Yellow

if (Test-Path check-skeptic.ps1) {
    $skeptic = Get-Content check-skeptic.ps1 -Raw
    $pathRefs = [regex]::Matches($skeptic, '"([^"]+\.(ps1|py|md))"') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
    
    $checked = 0
    foreach ($ref in $pathRefs) {
        # Skip environment variables and URLs
        if ($ref -match '\$|http') { continue }
        
        if (-not (Test-Path $ref)) {
            $errors += "check-skeptic.ps1 references non-existent: $ref"
        } else {
            $checked++
        }
    }
    
    Write-Host "  Verified $checked file paths" -ForegroundColor Gray
} else {
    $errors += "check-skeptic.ps1 not found"
}

# ══════════════════════════════════════════════════════════════════════════
# 3. Check for duplicate filenames (EXCLUDING ACCEPTABLE ARCHITECTURAL DUPLICATES)
# ══════════════════════════════════════════════════════════════════════════
Write-Host "`n[3/6] Checking for duplicate filenames..." -ForegroundColor Yellow

# WHITELIST: Acceptable architectural duplicates (documented in FILE_INDEX.md)
$acceptableDuplicates = @(
    '__init__.py',        # Python package markers
    'config.py',          # Separate configs for api/ and bot/
    'main.py',            # Entry points for agent/, api/, bot/
    'metrics_rollup.py',  # Shared utility
    'money.py'            # Money formatting in api/utils/ and bot/ui/
)

# Whitelist: wrappers in root are intentional for backward compatibility
$wrapperWhitelist = @('check-skeptic.ps1', 'run-ai-eval.ps1', 'full_acceptance.ps1', 'QUICK_SMOKE_TESTS.ps1')

$allFiles = Get-ChildItem -Recurse -Include *.ps1,*.py -File | 
    Where-Object { 
        $_.FullName -notmatch 'restored|__pycache__|\.venv|node_modules|\.git' 
    }

$grouped = $allFiles | Group-Object Name | Where-Object { $_.Count -gt 1 } | Where-Object {
    $name = $_.Name
    
    # EXCLUDE acceptable architectural duplicates
    if ($name -in $acceptableDuplicates) {
        Write-Host "  ✓ $name (acceptable architectural duplicate)" -ForegroundColor Gray
        return $false
    }
    
    # Exclude wrappers if one copy is in root and matches whitelist
    if ($name -in $wrapperWhitelist) {
        $paths = $_.Group.FullName
        $rootWrapper = $paths | Where-Object { $_ -match "^$([regex]::Escape((Get-Location).Path))\\$name$" }
        $utilsFile = $paths | Where-Object { $_ -match '\\utils\\' }
        # Allow if root wrapper + utils file
        return -not ($rootWrapper -and $utilsFile -and $_.Count -eq 2)
    }
    $true
}

if ($grouped) {
    foreach ($group in $grouped) {
        $paths = $group.Group | ForEach-Object { 
            $_.FullName.Replace((Get-Location).Path + "\", "")
        }
        $errors += "Duplicate filename: $($group.Name) found at:`n     " + ($paths -join "`n     ")
    }
} else {
    Write-Host "  ✓ No problematic duplicates found" -ForegroundColor Green
}

# ══════════════════════════════════════════════════════════════════════════
# 4. Check FILE_INDEX.md synchronization
# ══════════════════════════════════════════════════════════════════════════
Write-Host "`n[4/6] Checking FILE_INDEX.md synchronization..." -ForegroundColor Yellow

if (Test-Path FILE_INDEX.md) {
    $index = Get-Content FILE_INDEX.md -Raw
    
    # Extract smoke_*.ps1 references from FILE_INDEX.md
    $indexedSmokes = [regex]::Matches($index, '\*\*smoke_\w+\.ps1\*\*') | 
        ForEach-Object { $_.Value.Trim('*') } | 
        Sort-Object -Unique
    
    # Get actual smoke scripts in scripts/
    $actualSmokes = Get-ChildItem scripts\smoke_*.ps1 -File -ErrorAction SilentlyContinue | 
        ForEach-Object { $_.Name } | 
        Sort-Object
    
    # Find missing and extra
    $missing = $actualSmokes | Where-Object { $_ -notin $indexedSmokes }
    $extra = $indexedSmokes | Where-Object { $_ -notin $actualSmokes }
    
    foreach ($file in $missing) {
        $warnings += "FILE_INDEX.md missing: scripts\$file"
    }
    foreach ($file in $extra) {
        # Skip files marked as "НЕ СОЗДАН"
        if ($index -match "$file.*НЕ СОЗДАН") {
            Write-Host "  ⚠ $file (planned, not created yet)" -ForegroundColor Yellow
        } else {
            $errors += "FILE_INDEX.md references non-existent: $file"
        }
    }
    
    if ($missing.Count -eq 0 -and $extra.Count -eq 0) {
        Write-Host "  ✓ FILE_INDEX.md synchronized" -ForegroundColor Green
    }
} else {
    $errors += "FILE_INDEX.md not found"
}

# ══════════════════════════════════════════════════════════════════════════
# 5. Check S-gate to file mapping
# ══════════════════════════════════════════════════════════════════════════
Write-Host "`n[5/6] Checking S-gate to file mapping..." -ForegroundColor Yellow

$gateMap = @{
    "S27" = "smoke_e1_inbox.ps1"
    "S28" = "smoke_e2_invoices.ps1"
    "S31" = "smoke_i1_admin_auth.ps1"
    "S39" = "smoke_f2_backup_restore.ps1"
    "S40" = "smoke_e3_metrics.ps1"
    # S60-S63 marked as planned
}

foreach ($gate in $gateMap.Keys) {
    $file = $gateMap[$gate]
    $expectedPath = "scripts\$file"
    
    # Also check root for legacy locations
    $rootPath = $file
    
    if (Test-Path $expectedPath) {
        Write-Host "  ✓ $gate → $file" -ForegroundColor Green
    } elseif (Test-Path $rootPath) {
        $warnings += "$gate file in WRONG location: $rootPath (should be $expectedPath)"
    } else {
        $errors += "$gate file MISSING: expected at $expectedPath"
    }
}

# ══════════════════════════════════════════════════════════════════════════
# 6. Check directory structure compliance
# ══════════════════════════════════════════════════════════════════════════
Write-Host "`n[6/6] Checking directory structure compliance..." -ForegroundColor Yellow

# Expected structure
$expectedDirs = @{
    "scripts" = "Smoke tests and utilities"
    "tests" = "Python tests and validators"
    "api/tests" = "API-specific tests"
}

$missingDirs = @()
foreach ($dir in $expectedDirs.Keys) {
    if (-not (Test-Path $dir)) {
        $missingDirs += $dir
    } else {
        Write-Host "  ✓ $dir/" -ForegroundColor Green
    }
}

if ($missingDirs.Count -gt 0) {
    $warnings += "Missing directories: " + ($missingDirs -join ", ")
}

# Check for smoke_*.ps1 in wrong locations
$rootSmokes = Get-ChildItem .\smoke_*.ps1 -File -ErrorAction SilentlyContinue
if ($rootSmokes) {
    foreach ($file in $rootSmokes) {
        $warnings += "Smoke script in root (should be scripts/): $($file.Name)"
    }
}

# ══════════════════════════════════════════════════════════════════════════
# Report Summary
# ══════════════════════════════════════════════════════════════════════════
Write-Host "`n╔═══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                    VALIDATION SUMMARY                         ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$totalIssues = $errors.Count + $warnings.Count

if ($errors.Count -eq 0 -and $warnings.Count -eq 0) {
    Write-Host "✅ ALL FILE REFERENCES VALID" -ForegroundColor Green
    Write-Host "   No errors or warnings found.`n" -ForegroundColor Gray
    exit 0
}

if ($errors.Count -gt 0) {
    Write-Host "❌ ERRORS FOUND: $($errors.Count)" -ForegroundColor Red
    $errors | ForEach-Object { 
        Write-Host "   • $_" -ForegroundColor Red 
    }
    Write-Host ""
}

if ($warnings.Count -gt 0) {
    Write-Host "⚠️  WARNINGS: $($warnings.Count)" -ForegroundColor Yellow
    $warnings | ForEach-Object { 
        Write-Host "   • $_" -ForegroundColor Yellow 
    }
    Write-Host ""
}

Write-Host "Total issues: $totalIssues`n" -ForegroundColor Gray

if ($errors.Count -gt 0) {
    Write-Host "Fix errors before committing.`n" -ForegroundColor Red
    exit 1
} else {
    Write-Host "Warnings can be addressed later.`n" -ForegroundColor Yellow
    exit 0
}
