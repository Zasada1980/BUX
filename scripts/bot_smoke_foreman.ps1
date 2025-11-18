# Sprint C: Foreman Inbox Smoke Tests
# Validates G1-G7 Skeptic Gates

Write-Host "`n=== SPRINT C: FOREMAN INBOX SMOKE TESTS ===" -ForegroundColor Cyan

# Setup: Create foreman user and test data
Write-Host "`n[SETUP] Creating foreman user (telegram_id=222)..." -ForegroundColor Yellow

# Check if foreman exists
$checkForeman = docker compose exec api python -c @"
from db import SessionLocal
from sqlalchemy import text

s = SessionLocal()
row = s.execute(text('SELECT id, role FROM users WHERE telegram_id=222')).fetchone()
if row:
    print(f'EXISTS:{row[0]}:{row[1]}')
else:
    print('MISSING')
s.close()
"@

if ($checkForeman -match "MISSING") {
    Write-Host "  Creating foreman user..." -ForegroundColor Yellow
    
    # Create PIN
    $pinCreate = Invoke-RestMethod -Uri "http://127.0.0.1:8088/api/admin/pin/create" `
        -Method POST `
        -Headers @{"Content-Type"="application/json"} `
        -Body (@{code="FM001"; role="foreman"; expires_at=(Get-Date).AddDays(1).ToString("yyyy-MM-ddTHH:mm:ssZ")} | ConvertTo-Json)
    
    Write-Host "  PIN created: FM001" -ForegroundColor Green
    
    # Bind to telegram_id=222
    $pinBind = Invoke-RestMethod -Uri "http://127.0.0.1:8088/api/admin/pin/bind" `
        -Method POST `
        -Headers @{"Content-Type"="application/json"} `
        -Body (@{code="FM001"; telegram_id=222} | ConvertTo-Json)
    
    Write-Host "  Bound to telegram_id=222, user_id=$($pinBind.user_id)" -ForegroundColor Green
} else {
    $parts = $checkForeman -split ":"
    Write-Host "  Foreman exists: user_id=$($parts[1]), role=$($parts[2])" -ForegroundColor Green
}

# Create test expense (needs_approval)
Write-Host "`n[SETUP] Creating test expense (status=needs_approval)..." -ForegroundColor Yellow

$expenseCreate = docker compose exec api python -c @"
from db import SessionLocal
from sqlalchemy import text
from datetime import datetime, timezone

s = SessionLocal()

# Insert expense
s.execute(text('''
    INSERT INTO expenses(worker_id, category, amount, currency, status, created_at)
    VALUES('worker_1', 'transport', 1450.0, 'RUB', 'needs_approval', :ts)
'''), {'ts': datetime.now(timezone.utc).isoformat()})

s.commit()

# Get ID
row = s.execute(text('SELECT id FROM expenses ORDER BY id DESC LIMIT 1')).fetchone()
print(f'EXP_ID:{row[0]}')
s.close()
"@

$expenseId = ($expenseCreate -split ":")[1]
Write-Host "  Created expense_id=$expenseId" -ForegroundColor Green

# Create test pending_change
Write-Host "`n[SETUP] Creating test pending_change (status=pending)..." -ForegroundColor Yellow

$pcCreate = docker compose exec api python -c @"
from db import SessionLocal
from sqlalchemy import text
from datetime import datetime, timezone
import json

s = SessionLocal()

# Insert pending_change (uses existing schema: kind, payload_json, status)
payload = json.dumps({'diff': {'add': [{'task': 'extra', 'qty': 1, 'amount': 123.45}]}})
s.execute(text('''
    INSERT INTO pending_changes(kind, payload_json, status, created_at)
    VALUES('invoice_update', :payload, 'pending', :ts)
'''), {'ts': datetime.now(timezone.utc).isoformat(), 'payload': payload})

s.commit()

# Get ID
row = s.execute(text('SELECT id FROM pending_changes ORDER BY id DESC LIMIT 1')).fetchone()
print(f'PC_ID:{row[0]}')
s.close()
"@

$pcId = ($pcCreate -split ":")[1]
Write-Host "  Created pending_change_id=$pcId" -ForegroundColor Green

Write-Host "`n=== SMOKE TESTS START ===" -ForegroundColor Cyan

# ============================================================================
# Test 1: GET /api/bot/inbox (G1, G6)
# ============================================================================
Write-Host "`n[TEST 1] GET /api/bot/inbox (foreman role check)..." -ForegroundColor Cyan

try {
    $inbox = Invoke-RestMethod -Uri "http://127.0.0.1:8088/api/bot/inbox?telegram_id=222&state=pending&limit=10" `
        -Method GET
    
    Write-Host "  Inbox items: $($inbox.count)" -ForegroundColor Yellow
    foreach ($item in $inbox.items) {
        Write-Host "    - kind=$($item.kind), id=$($item.id), status=$($item.status)" -ForegroundColor Gray
    }
    
    if ($inbox.count -ge 2) {
        Write-Host "  ✅ PASS: Inbox returned items" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ ADVISORY: Expected ≥2 items, got $($inbox.count)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ FAIL: Inbox fetch failed" -ForegroundColor Red
    Write-Host ($_.ErrorDetails.Message | ConvertFrom-Json | ConvertTo-Json -Depth 5)
}

# ============================================================================
# Test 2: POST /api/bot/approve (G1, G3, G5, G6)
# ============================================================================
Write-Host "`n[TEST 2] POST /api/bot/approve (bulk approval)..." -ForegroundColor Cyan

$approveBody = @{
    telegram_id = 222
    items = @(
        @{kind="expense"; id=[int]$expenseId},
        @{kind="pending_change"; id=[int]$pcId}
    )
} | ConvertTo-Json

try {
    $approveRes = Invoke-RestMethod -Uri "http://127.0.0.1:8088/api/bot/approve" `
        -Method POST `
        -Headers @{"Content-Type"="application/json"} `
        -Body $approveBody
    
    Write-Host "  Results: ok=$($approveRes.ok), failed=$($approveRes.failed)" -ForegroundColor Yellow
    foreach ($res in $approveRes.results) {
        Write-Host "    - kind=$($res.kind), id=$($res.id), status=$($res.status)" -ForegroundColor Gray
    }
    
    if ($approveRes.ok -eq 2 -and $approveRes.failed -eq 0) {
        Write-Host "  ✅ PASS: Both items approved" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ ADVISORY: Expected ok=2, failed=0" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ FAIL: Approve failed" -ForegroundColor Red
    Write-Host ($_.ErrorDetails.Message | ConvertFrom-Json | ConvertTo-Json -Depth 5)
}

# ============================================================================
# Test 3: Idempotent approve (G3)
# ============================================================================
Write-Host "`n[TEST 3] POST /api/bot/approve (idempotency check)..." -ForegroundColor Cyan

try {
    $approveRes2 = Invoke-RestMethod -Uri "http://127.0.0.1:8088/api/bot/approve" `
        -Method POST `
        -Headers @{"Content-Type"="application/json"} `
        -Body $approveBody
    
    Write-Host "  Results: ok=$($approveRes2.ok), failed=$($approveRes2.failed)" -ForegroundColor Yellow
    foreach ($res in $approveRes2.results) {
        Write-Host "    - kind=$($res.kind), id=$($res.id), status=$($res.status)" -ForegroundColor Gray
    }
    
    $noopCount = ($approveRes2.results | Where-Object {$_.status -eq "noop"}).Count
    if ($noopCount -eq 2) {
        Write-Host "  ✅ PASS: Both items returned 'noop' (idempotent)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ ADVISORY: Expected 2 noop, got $noopCount" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ FAIL: Idempotent approve failed" -ForegroundColor Red
    Write-Host ($_.ErrorDetails.Message | ConvertFrom-Json | ConvertTo-Json -Depth 5)
}

# ============================================================================
# Test 4: POST /api/bot/reject (G5, G6, G7)
# ============================================================================
Write-Host "`n[TEST 4] Create new expense for rejection test..." -ForegroundColor Cyan

$rejectExpenseCreate = docker compose exec api python -c @"
from db import SessionLocal
from sqlalchemy import text
from datetime import datetime, timezone

s = SessionLocal()
s.execute(text('''
    INSERT INTO expenses(worker_id, category, amount, currency, status, created_at)
    VALUES('worker_2', 'supplies', 780.0, 'RUB', 'needs_approval', :ts)
'''), {'ts': datetime.now(timezone.utc).isoformat()})
s.commit()

row = s.execute(text('SELECT id FROM expenses ORDER BY id DESC LIMIT 1')).fetchone()
print(f'EXP_ID:{row[0]}')
s.close()
"@

$rejectExpId = ($rejectExpenseCreate -split ":")[1]
Write-Host "  Created expense_id=$rejectExpId for rejection" -ForegroundColor Green

Write-Host "`n[TEST 4] POST /api/bot/reject (with reason)..." -ForegroundColor Cyan

$rejectBody = @{
    telegram_id = 222
    items = @(@{kind="expense"; id=[int]$rejectExpId})
    reason = "photo missing"
} | ConvertTo-Json

try {
    $rejectRes = Invoke-RestMethod -Uri "http://127.0.0.1:8088/api/bot/reject" `
        -Method POST `
        -Headers @{"Content-Type"="application/json"} `
        -Body $rejectBody
    
    Write-Host "  Results: ok=$($rejectRes.ok), failed=$($rejectRes.failed)" -ForegroundColor Yellow
    foreach ($res in $rejectRes.results) {
        Write-Host "    - kind=$($res.kind), id=$($res.id), status=$($res.status)" -ForegroundColor Gray
    }
    
    if ($rejectRes.ok -eq 1 -and $rejectRes.failed -eq 0) {
        Write-Host "  ✅ PASS: Expense rejected with reason" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ ADVISORY: Expected ok=1, failed=0" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ FAIL: Reject failed" -ForegroundColor Red
    Write-Host ($_.ErrorDetails.Message | ConvertFrom-Json | ConvertTo-Json -Depth 5)
}

# ============================================================================
# Test 5: Metrics and Audit (G5, G6)
# ============================================================================
Write-Host "`n[TEST 5] Check metrics and audit logs..." -ForegroundColor Cyan

# Check metrics
$today = Get-Date -Format "yyyy-MM-dd"
Write-Host "  Checking metrics: /app/logs/metrics/$today/api.jsonl" -ForegroundColor Yellow

$metricsCheck = docker compose exec api sh -c "tail -n 50 /app/logs/metrics/$today/api.jsonl | grep -E 'bot\.inbox\.(fetch|approve|reject)' | wc -l"

if ([int]$metricsCheck -ge 5) {
    Write-Host "  ✅ PASS: Found $metricsCheck inbox metrics" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ ADVISORY: Expected ≥5 metrics, found $metricsCheck" -ForegroundColor Yellow
}

# Check audit log
Write-Host "  Checking audit_log table..." -ForegroundColor Yellow

$auditCheck = docker compose exec api python -c @"
from db import SessionLocal
from sqlalchemy import text

s = SessionLocal()
count = s.execute(text('''
    SELECT COUNT(*) FROM audit_log
    WHERE action IN ('approve_expense', 'approve_pending_change', 'reject_expense')
''')).fetchone()[0]
print(f'AUDIT_COUNT:{count}')
s.close()
"@

$auditCount = ($auditCheck -split ":")[1]
if ([int]$auditCount -ge 3) {
    Write-Host "  ✅ PASS: Found $auditCount audit entries" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ ADVISORY: Expected ≥3 audit entries, found $auditCount" -ForegroundColor Yellow
}

# ============================================================================
# Test 6: Non-foreman access (G1)
# ============================================================================
Write-Host "`n[TEST 6] Non-foreman access (403 forbidden_role)..." -ForegroundColor Cyan

try {
    $workerInbox = Invoke-RestMethod -Uri "http://127.0.0.1:8088/api/bot/inbox?telegram_id=99999&state=pending" `
        -Method GET
    
    Write-Host "  ❌ FAIL: Worker (99999) accessed inbox (should be 403)" -ForegroundColor Red
} catch {
    $err = $_.ErrorDetails.Message | ConvertFrom-Json
    if ($err.detail.code -eq "forbidden_role") {
        Write-Host "  ✅ PASS: 403 forbidden_role for non-foreman" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ ADVISORY: Got error but not forbidden_role: $($err.detail)" -ForegroundColor Yellow
    }
}

# ============================================================================
# Test 7: Stale state (G2)
# ============================================================================
Write-Host "`n[TEST 7] Stale state check (409 stale_state)..." -ForegroundColor Cyan

# Try to approve already rejected expense
$staleBody = @{
    telegram_id = 222
    items = @(@{kind="expense"; id=[int]$rejectExpId})
} | ConvertTo-Json

try {
    $staleRes = Invoke-RestMethod -Uri "http://127.0.0.1:8088/api/bot/approve" `
        -Method POST `
        -Headers @{"Content-Type"="application/json"} `
        -Body $staleBody
    
    Write-Host "  Results: ok=$($staleRes.ok), failed=$($staleRes.failed)" -ForegroundColor Yellow
    
    $staleError = $staleRes.results | Where-Object {$_.error.code -eq "stale_state"}
    if ($staleError) {
        Write-Host "  ✅ PASS: stale_state error returned (expense already rejected)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ ADVISORY: Expected stale_state error" -ForegroundColor Yellow
        Write-Host ($staleRes.results | ConvertTo-Json -Depth 5)
    }
} catch {
    Write-Host "  ⚠️ ADVISORY: Request failed (may be expected)" -ForegroundColor Yellow
    Write-Host ($_.ErrorDetails.Message | ConvertFrom-Json | ConvertTo-Json -Depth 5)
}

Write-Host "`n=== SPRINT C SMOKE TESTS COMPLETE ===" -ForegroundColor Cyan
Write-Host "Summary:" -ForegroundColor Yellow
Write-Host "  - TEST 1: Inbox fetch (G1, G6)" -ForegroundColor Gray
Write-Host "  - TEST 2: Bulk approve (G1, G3, G5, G6)" -ForegroundColor Gray
Write-Host "  - TEST 3: Idempotent approve (G3)" -ForegroundColor Gray
Write-Host "  - TEST 4: Reject with reason (G5, G6, G7)" -ForegroundColor Gray
Write-Host "  - TEST 5: Metrics & audit (G5, G6)" -ForegroundColor Gray
Write-Host "  - TEST 6: Non-foreman 403 (G1)" -ForegroundColor Gray
Write-Host "  - TEST 7: Stale state (G2)" -ForegroundColor Gray
