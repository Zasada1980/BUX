# smoke_e1_pending.ps1 — S34 gate (JSON + HTML validation)
param(
  [string]$Base = "http://127.0.0.1:8088",
  [string]$OutDir = "logs"
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Fail($msg){ 
    $msg | Set-Content "$OutDir\e1_pending_FAIL.txt"
    Write-Error $msg
    exit 1 
}

function Ok($msg){  
    $msg | Set-Content "$OutDir\e1_pending_OK.txt"
    Write-Host $msg -ForegroundColor Green
    exit 0 
}

Write-Host "[S34] Testing /admin/pending (JSON + HTML)..." -ForegroundColor Cyan

# ═══════════════════════════════════════════════════════════════════════════
# 1) JSON список с пагинацией
# ═══════════════════════════════════════════════════════════════════════════
$jsonPath = Join-Path $OutDir "e1_pending.json"

try {
    $json = Invoke-RestMethod "$Base/admin/pending?page=1&limit=20"
    $json | ConvertTo-Json -Depth 6 | Set-Content $jsonPath -Encoding utf8
} catch {
    Fail "JSON request failed: $($_.Exception.Message)"
}

# Валидация структуры
$required = "items","total","page","limit","has_next"
foreach($k in $required){ 
    if(-not ($json.PSObject.Properties.Name -contains $k)){ 
        Fail "Missing key: $k" 
    } 
}

if(-not ($json.items -is [System.Array])){ 
    Fail "items is not array" 
}

Write-Host "  ✓ JSON structure valid" -ForegroundColor Green

# ═══════════════════════════════════════════════════════════════════════════
# 2) HTML-таблица (HTMX partial)
# ═══════════════════════════════════════════════════════════════════════════
$htmlPath = Join-Path $OutDir "e1_pending_table.html"

try {
    $resp = Invoke-WebRequest -Method GET -Uri "$Base/admin/pending" `
        -Headers @{ "HX-Request"="true"; "Accept"="text/html" }
    $resp.Content | Set-Content $htmlPath -Encoding utf8
} catch {
    Fail "HTML request failed: $($_.Exception.Message)"
}

# Валидация HTML-маркеров
$must = @('<table class="grid">','hx-post="/admin/pending/','id="inbox"')
foreach($m in $must){
    if(-not (Select-String -Path $htmlPath -SimpleMatch -Pattern $m)){ 
        Fail "HTML marker not found: $m" 
    }
}

Write-Host "  ✓ HTML table markers present" -ForegroundColor Green

# ═══════════════════════════════════════════════════════════════════════════
# 3) SHA артефактов
# ═══════════════════════════════════════════════════════════════════════════
"$((Get-FileHash $jsonPath).Hash)  $(Split-Path $jsonPath -Leaf)" | 
    Set-Content (Join-Path $OutDir "e1_pending_json.sha256")
"$((Get-FileHash $htmlPath).Hash)  $(Split-Path $htmlPath -Leaf)" | 
    Set-Content (Join-Path $OutDir "e1_pending_table.sha256")

Write-Host "  ✓ Artifacts SHA256 saved" -ForegroundColor Green

Ok "[S34 PASS] JSON+HTML validated"
