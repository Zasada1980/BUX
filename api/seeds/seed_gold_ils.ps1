# seed_gold_ils.ps1 — deterministic ILS seed for ≥24 events (p95 threshold)
# Generates tasks, expenses, invoice workflow → logs/invoice_*.{html,json}

$ErrorActionPreference = 'Stop'
$BASE = "http://127.0.0.1:8088"
$TOKEN = $null

function Post($path, $obj) {
    $headers = @{ 'Content-Type' = 'application/json' }
    if ($TOKEN) { $headers['Authorization'] = "Bearer $TOKEN" }
    return Invoke-RestMethod -Method Post -Uri "$BASE$path" -Headers $headers -Body ($obj | ConvertTo-Json -Depth 6) -ErrorAction Stop
}

Write-Host "[G2 Seed] Creating deterministic test data..." -ForegroundColor Cyan

# ═══════════════════════════════════════════════════════════════════════════
# 0) Login and get token
# ═══════════════════════════════════════════════════════════════════════════
try {
    $loginResp = Invoke-RestMethod -Method Post -Uri "$BASE/api/auth/login" -ContentType 'application/json' -Body '{"username":"admin","password":"admin123"}'
    $TOKEN = $loginResp.access_token
    Write-Host "  + Logged in as admin, token: $($TOKEN.Substring(0,20))..." -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Login failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ═══════════════════════════════════════════════════════════════════════════
# 1) Start shift
# ═══════════════════════════════════════════════════════════════════════════
try {
    $shift = Post "/api/v1/shift/start" @{ user_id = "seed_user"; location = "seed_location" }
    $shiftId = $shift.id
    Write-Host "  + Shift started: id=$shiftId" -ForegroundColor Green
} catch {
    Write-Host "  [WARNING] Shift start failed: $($_.Exception.Message), using fallback shift_id=1" -ForegroundColor Yellow
    $shiftId = 1
}

# ═══════════════════════════════════════════════════════════════════════════
# 2) Create 12 tasks (deterministic)
# ═══════════════════════════════════════════════════════════════════════════
$taskIds = @()
for ($i = 1; $i -le 12; $i++) {
    try {
        $task = Post "/api/task.add" @{
            shift_id = $shiftId
            rate_code = "piece_demo"
            qty = 1
            note = "seed-task-$i"
        }
        $taskIds += $task.id
    } catch {
        Write-Host "  [WARNING] Task $i creation failed" -ForegroundColor Yellow
    }
}
Write-Host "  + Created $($taskIds.Count) tasks" -ForegroundColor Green

# ═══════════════════════════════════════════════════════════════════════════
# 3) Create 12 expenses (with photo stub)
# ═══════════════════════════════════════════════════════════════════════════
$expenseIds = @()
for ($i = 1; $i -le 12; $i++) {
    try {
        $expense = Post "/api/expense.add" @{
            worker_id = "seed_worker"
            shift_id = $shiftId
            category = "транспорт"
            amount = 12.34
            currency = "ILS"
            photo_ref = "stub.jpg"
        }
        $expenseIds += $expense.id
    } catch {
        Write-Host "  [WARNING] Expense $i creation failed" -ForegroundColor Yellow
    }
}
Write-Host "  + Created $($expenseIds.Count) expenses" -ForegroundColor Green

# ═══════════════════════════════════════════════════════════════════════════
# 4) Invoice workflow: build → preview → suggest → apply → diff
# ═══════════════════════════════════════════════════════════════════════════

# Build invoice
try {
    $inv = Post "/api/invoice.build" @{
        client_id = "seed_client"
        period_from = "2000-01-01"
        period_to = "2100-01-01"
        currency = "ILS"
    }
    $invId = $inv.id
    Write-Host "  + Invoice built: id=$invId" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] Invoice build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Preview + save HTML
try {
    $previewResp = Invoke-RestMethod -Method Post -Uri "$BASE/api/invoice.preview/$invId/issue"
    $token = $previewResp.token
    
    New-Item -Force -ItemType Directory -Path "api\logs" | Out-Null
    Invoke-WebRequest -UseBasicParsing "$BASE/api/invoice.preview/$invId?token=$token" | 
        Select-Object -ExpandProperty Content | 
        Set-Content "api\logs\invoice_preview.html" -Encoding utf8
    
    Write-Host "  + Invoice preview saved: api\logs\invoice_preview.html" -ForegroundColor Green
} catch {
    Write-Host "  [WARNING] Preview failed: $($_.Exception.Message)" -ForegroundColor Yellow
    $token = "fallback_token"
}

# Suggest change (add extra item)
try {
    $sug = Post "/api/invoice.suggest_change" @{
        invoice_id = $invId
        token = $token
        kind = "add_item"
        payload = @{
            item = @{
                task = "extra_seed_task"
                qty = 1
                unit = "unit"
                amount = 123.45
                worker = "seed_worker"
                site = "seed_site"
                date = "2025-11-11"
            }
        }
    }
    $sugId = $sug.id
    Write-Host "  + Suggestion created: id=$sugId" -ForegroundColor Green
    
    # Try to approve pending (if moderation enabled)
    try {
        Invoke-RestMethod -Method Post -Uri "$BASE/api/admin/pending/$($sug.pending_id)/approve" -Body (@{by='seed'} | ConvertTo-Json) -ContentType 'application/json' | Out-Null
    } catch {
        # Moderation might be disabled
    }
} catch {
    Write-Host "  [WARNING] Suggestion failed: $($_.Exception.Message)" -ForegroundColor Yellow
    $sugId = $null
}

# Apply suggestions
if ($sugId) {
    try {
        $applied = Post "/api/invoice.apply_suggestions" @{
            invoice_id = $invId
            suggestion_ids = @($sugId)
        }
        $applied | ConvertTo-Json -Depth 4 | Set-Content "api\logs\invoice_apply.json" -Encoding utf8
        Write-Host "  + Suggestions applied: api\logs\invoice_apply.json" -ForegroundColor Green
        
        # Get diff
        $newVersion = $applied.new_version
        $diff = Invoke-RestMethod "$BASE/api/invoice/$invId/diff?from=v1&to=v$newVersion"
        $diff | ConvertTo-Json -Depth 6 | Set-Content "api\logs\invoice_diff.json" -Encoding utf8
        Write-Host "  + Invoice diff saved: api\logs\invoice_diff.json" -ForegroundColor Green
    } catch {
        Write-Host "  [WARNING] Apply/diff failed: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "[G2 Seed] Summary:" -ForegroundColor Green
Write-Host "  Shift: $shiftId" -ForegroundColor Gray
Write-Host "  Tasks: $($taskIds.Count)" -ForegroundColor Gray
Write-Host "  Expenses: $($expenseIds.Count)" -ForegroundColor Gray
Write-Host "  Invoice: $invId" -ForegroundColor Gray
Write-Host "  Total events: ~$(($taskIds.Count + $expenseIds.Count + 5))" -ForegroundColor Cyan
Write-Host ""

exit 0
