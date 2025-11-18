# G3 Smoke Tests - Item Details API Determinism
# Uses unit tests as smoke tests (in-memory DB, no external dependencies)

Write-Host "=== G3 Smoke Tests (via pytest) ===" -ForegroundColor Cyan

# Run unit tests with verbose output
Write-Host "`n=== Running G3 unit tests ===" -ForegroundColor Yellow
try {
    $output = python -m pytest tests/test_item_details.py -vv --tb=short 2>&1 | Out-String
    $exitCode = $LASTEXITCODE
    
    Write-Host $output
    
    if ($exitCode -eq 0) {
        Write-Host "`n✅ All tests PASSED" -ForegroundColor Green
    } else {
        Write-Host "`n❌ Tests FAILED" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Test execution failed: $_" -ForegroundColor Red
    exit 1
}

# Collect SHA256 hashes of test files
Write-Host "`n=== Collecting SHA256 hashes ===" -ForegroundColor Cyan
Get-FileHash tests\test_item_details.py,pricing.py,schemas.py,main.py |
    Format-Table -AutoSize Path,@{Label="SHA256";Expression={$_.Hash.Substring(0,12)}} |
    Out-String |
    Tee-Object -FilePath "logs\g3_test_sha_manifest.txt"

Write-Host "✅ SHA256 manifest saved to logs\g3_test_sha_manifest.txt" -ForegroundColor Green

# Verify determinism test passed
Write-Host "`n=== Verifying determinism test ===" -ForegroundColor Cyan
if ($output -match "test_task_details_deterministic") {
    Write-Host "✅ Determinism test PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ Determinism test not found" -ForegroundColor Red
    Write-Host "Output: $output" -ForegroundColor Yellow
    exit 1
}

# Verify ILS currency test passed
if ($output -match "test_expense_details_ils_currency") {
    Write-Host "✅ ILS currency test PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ ILS currency test not found" -ForegroundColor Red
    exit 1
}

# Verify rules pin test passed
if ($output -match "test_rules_pin") {
    Write-Host "✅ Rules pin test PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ Rules pin test not found" -ForegroundColor Red
    exit 1
}

# Verify 404/422 test passed
if ($output -match "test_404_422") {
    Write-Host "✅ 404/422 test PASSED" -ForegroundColor Green
} else {
    Write-Host "❌ 404/422 test not found" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== ✅ All G3 smoke tests PASSED ===" -ForegroundColor Green
Write-Host "  4/4 tests passed (determinism, ILS currency, rules pin, 404/422)" -ForegroundColor Cyan
Write-Host "  Evidence: logs\g3_test_sha_manifest.txt" -ForegroundColor Cyan
