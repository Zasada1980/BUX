# G3 Smoke Test Setup - Create test data

Write-Host "=== G3 Smoke Test Setup ===" -ForegroundColor Cyan

# Create shift
Write-Host "`nCreating test shift..." -ForegroundColor Yellow
try {
    $shiftResp = Invoke-RestMethod -Method Post `
        -Uri "http://127.0.0.1:8080/api/v1/shift/start" `
        -ContentType "application/json" `
        -Body '{"user_id":"test_worker"}' `
        -ErrorAction Stop
    $shiftId = $shiftResp.id
    Write-Host "✅ Shift created: ID=$shiftId" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to create shift: $_" -ForegroundColor Red
    exit 1
}

# Create task
Write-Host "`nCreating test task..." -ForegroundColor Yellow
try {
    $taskResp = Invoke-RestMethod -Method Post `
        -Uri "http://127.0.0.1:8080/api/task.add" `
        -ContentType "application/json" `
        -Body "{`"shift_id`":$shiftId,`"rate_code`":`"hour_electric`",`"qty`":2.0}" `
        -ErrorAction Stop
    $taskId = $taskResp.id
    Write-Host "✅ Task created: ID=$taskId (qty=2.0, rate=hour_electric)" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to create task: $_" -ForegroundColor Red
    exit 1
}

# Create expense
Write-Host "`nCreating test expense..." -ForegroundColor Yellow
try {
    $expenseResp = Invoke-RestMethod -Method Post `
        -Uri "http://127.0.0.1:8080/api/expense.add" `
        -ContentType "application/json" `
        -Body "{`"worker_id`":`"test_worker`",`"category`":`"материалы`",`"amount`":500.50,`"currency`":`"ILS`"}" `
        -ErrorAction Stop
    $expenseId = $expenseResp.id
    Write-Host "✅ Expense created: ID=$expenseId (amount=500.50 ILS)" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to create expense: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== ✅ Setup complete ===" -ForegroundColor Green
Write-Host "  Shift ID: $shiftId" -ForegroundColor Cyan
Write-Host "  Task ID: $taskId" -ForegroundColor Cyan
Write-Host "  Expense ID: $expenseId" -ForegroundColor Cyan
Write-Host "`nNow run: .\tests\smoke_g3.ps1" -ForegroundColor Yellow
