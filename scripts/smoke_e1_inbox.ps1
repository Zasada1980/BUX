# smoke_e1_inbox.ps1 — S35 gate (Inbox page + HTMX validation)
param(
  [string]$Base = "http://127.0.0.1:8088",
  [switch]$OpenBrowser  # опционально открыть в браузере
)
$ErrorActionPreference = "Stop"
$OutDir = "logs"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Fail($msg){ 
    $msg | Set-Content "$OutDir\e1_inbox_FAIL.txt"
    Write-Error $msg
    exit 1 
}

function Ok($msg){  
    $msg | Set-Content "$OutDir\e1_inbox_OK.txt"
    Write-Host $msg -ForegroundColor Green
    exit 0 
}

Write-Host "[S35] Testing /admin/inbox (page + HTMX)..." -ForegroundColor Cyan

# ═══════════════════════════════════════════════════════════════════════════
# 1) Главная страница инбокса
# ═══════════════════════════════════════════════════════════════════════════
$inboxPath = Join-Path $OutDir "e1_inbox.html"

try {
    $resp = Invoke-WebRequest "$Base/admin/inbox" -UseBasicParsing
    $resp.Content | Set-Content $inboxPath -Encoding utf8
} catch {
    Fail "Inbox page request failed: $($_.Exception.Message)"
}

# Минимальная валидация: skeleton + локальная статика HTMX
# Note: <div id="inbox"> создаётся динамически через hx-target, проверяем hx-get и static
$must = @('hx-get="/admin/pending"','/static/htmx.min.js','hx-target="#inbox"')
foreach($m in $must){
    if(-not (Select-String -Path $inboxPath -SimpleMatch -Pattern $m)){ 
        Fail "Inbox marker not found: $m" 
    }
}

Write-Host "  ✓ Inbox page HTML valid" -ForegroundColor Green

# ═══════════════════════════════════════════════════════════════════════════
# 2) Имитация hx-get для таблицы (headless)
# ═══════════════════════════════════════════════════════════════════════════
$tblPath = Join-Path $OutDir "e1_inbox_table.html"

try {
    $resp2 = Invoke-WebRequest -Method GET -Uri "$Base/admin/pending" `
        -Headers @{ "HX-Request"="true"; "Accept"="text/html" }
    $resp2.Content | Set-Content $tblPath -Encoding utf8
} catch {
    Fail "Table partial request failed: $($_.Exception.Message)"
}

if(-not (Select-String -Path $tblPath -SimpleMatch -Pattern '<table class="grid">')){ 
    Fail "Grid table not rendered" 
}

Write-Host "  ✓ HTMX table partial valid" -ForegroundColor Green

# ═══════════════════════════════════════════════════════════════════════════
# 3) SHA артефактов
# ═══════════════════════════════════════════════════════════════════════════
"$((Get-FileHash $inboxPath).Hash)  $(Split-Path $inboxPath -Leaf)" | 
    Set-Content (Join-Path $OutDir "e1_inbox_html.sha256")
"$((Get-FileHash $tblPath).Hash)    $(Split-Path $tblPath   -Leaf)" | 
    Set-Content (Join-Path $OutDir "e1_inbox_table.sha256")

Write-Host "  ✓ Artifacts SHA256 saved" -ForegroundColor Green

# ═══════════════════════════════════════════════════════════════════════════
# 4) Опционально открыть в браузере
# ═══════════════════════════════════════════════════════════════════════════
if($OpenBrowser){ 
    Write-Host "  → Opening in browser..." -ForegroundColor Yellow
    Start-Process "$Base/admin/inbox" | Out-Null 
}

Ok "[S35 PASS] /admin/inbox page + table validated"
