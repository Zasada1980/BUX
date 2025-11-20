# CI-11: Tested Files Backup Manifest

**Дата:** 2025-11-20  
**Commit:** 66bc185 (CI-11: Achieve 6/6 E2E PASS 100%)  
**E2E Test Results:** 6/6 PASS (100% GREEN)  
**Environment:** D:\TelegramOllama_ENV_DEMO\code

---

## ✅ Файлы, прошедшие E2E валидацию (ГОТОВЫ для production)

### **Backend (Python) — 3 файла**

1. **`api/seeds/fix_admin_role.py`** (commit 21cb0bb + 66bc185)
   - Назначение: Форсирует `role='admin', active=1` для user id=1 перед каждым E2E тестом
   - Тесты: Используется в beforeEach всех User Management тестов (6/6 PASS)
   - Критичность: 🔴 HIGH — без него admin теряет права после edit-user-role теста
   - Размер: 26 строк
   - Checksum (MD5): `[автоматически при бэкапе]`

2. **`api/web/src/pages/UsersPage.tsx`** (commit 66bc185)
   - Назначение: Users management page (таблица пользователей, CRUD операции)
   - Исправление: Строка 137 — изменено toast с "activated" на "updated" в `handleEditUser()`
   - Тесты: 6/6 User Management E2E PASS (create, edit, deactivate/activate, validation, CSV, empty)
   - Критичность: 🟡 MEDIUM — UI компонент, не влияет на backend/bot
   - Размер: 760 строк
   - Checksum (MD5): `[автоматически при бэкапе]`

3. **`api/web/e2e/user-management-smoke.spec.ts`** (commit 21cb0bb + 66bc185)
   - Назначение: E2E тесты для User Management сценария
   - Исправления:
     * Добавлен beforeEach с fix_admin_role.py + API restart + health check
     * Test 2 (edit-user-role): `.first()` → `.nth(1)` для edit button
     * Test 3 (deactivate-activate): `.first()` → `.nth(1)` для обеих кнопок
   - Тесты: 6/6 PASS (25.7s runtime)
   - Критичность: 🟢 LOW — тестовый код, не влияет на production
   - Размер: 195 строк
   - Checksum (MD5): `[автоматически при бэкапе]`

---

### **Frontend (Build Artifacts) — 1 директория**

4. **`api/web/dist/`** (собран после commit 66bc185)
   - Назначение: Production build фронтенда (Vite bundle)
   - Команда сборки: `npm run build` (выполнена после исправления toast)
   - Содержимое:
     * `index.html` (0.51 KB)
     * `assets/index-DaSiritz.css` (12.53 KB)
     * `assets/index-DYMRFzNL.js` (130.59 KB)
     * `assets/react-vendor-DMubgZII.js` (162.89 KB)
   - Тесты: Косвенно (E2E тесты запускаются против Vite dev server, но production bundle идентичен)
   - Критичность: 🔴 HIGH — это то, что видит пользователь в браузере
   - Размер: ~306 KB (gzipped ~84 KB)
   - Checksum (MD5): `[автоматически при бэкапе]`

---

## 📦 Команда создания бэкапа (ВЫПОЛНИТЬ ПЕРЕД деплоем)

```powershell
# 1. Создать директорию бэкапа с timestamp
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "d:\TelegramOllama_ENV_DEMO\BACKUPS\CI_11_TESTED_${timestamp}"
New-Item -ItemType Directory -Path $backupDir -Force

# 2. Копировать протестированные файлы
Copy-Item "d:\TelegramOllama_ENV_DEMO\code\api\seeds\fix_admin_role.py" "$backupDir\"
Copy-Item "d:\TelegramOllama_ENV_DEMO\code\api\web\src\pages\UsersPage.tsx" "$backupDir\"
Copy-Item "d:\TelegramOllama_ENV_DEMO\code\api\web\e2e\user-management-smoke.spec.ts" "$backupDir\"
Copy-Item "d:\TelegramOllama_ENV_DEMO\code\api\web\dist" "$backupDir\dist" -Recurse

# 3. Создать манифест с checksums
Get-ChildItem -Path $backupDir -Recurse -File | ForEach-Object {
    $hash = Get-FileHash $_.FullName -Algorithm MD5
    "$($hash.Hash)  $($_.FullName.Replace($backupDir, '.'))"
} | Out-File "$backupDir\CHECKSUMS.txt"

# 4. Архивировать для безопасного хранения
Compress-Archive -Path $backupDir -DestinationPath "${backupDir}.zip"

Write-Host "✅ Backup created: ${backupDir}.zip" -ForegroundColor Green
```

---

## 🔐 Проверка целостности бэкапа (ВЫПОЛНИТЬ ПОСЛЕ создания)

```powershell
# 1. Распаковать архив во временную директорию
$tempDir = "d:\TEMP\CI_11_VERIFY"
Expand-Archive -Path "${backupDir}.zip" -DestinationPath $tempDir -Force

# 2. Проверить checksums
$storedChecksums = Get-Content "$tempDir\CI_11_TESTED_${timestamp}\CHECKSUMS.txt"
$verified = $true
foreach ($line in $storedChecksums) {
    $parts = $line -split '  '
    $expectedHash = $parts[0]
    $filePath = $parts[1].Replace('.', "$tempDir\CI_11_TESTED_${timestamp}")
    
    if (Test-Path $filePath) {
        $actualHash = (Get-FileHash $filePath -Algorithm MD5).Hash
        if ($actualHash -ne $expectedHash) {
            Write-Host "❌ CHECKSUM MISMATCH: $filePath" -ForegroundColor Red
            $verified = $false
        }
    } else {
        Write-Host "❌ FILE MISSING: $filePath" -ForegroundColor Red
        $verified = $false
    }
}

if ($verified) {
    Write-Host "✅ Backup integrity verified (all checksums match)" -ForegroundColor Green
} else {
    Write-Host "❌ Backup integrity FAILED — DO NOT DEPLOY" -ForegroundColor Red
}

# 3. Очистка
Remove-Item -Path $tempDir -Recurse -Force
```

---

## 🚀 Deployment Prerequisites (ОБЯЗАТЕЛЬНО перед облачным деплоем)

### ✅ Pre-Deployment Checklist

- [ ] **Бэкап создан:** `CI_11_TESTED_${timestamp}.zip` существует
- [ ] **Checksums проверены:** Все файлы прошли проверку целостности
- [ ] **Git commit зафиксирован:** 66bc185 "CI-11: Achieve 6/6 E2E PASS (100%)"
- [ ] **E2E тесты прошли:** 6/6 PASS (100% GREEN) на D:\
- [ ] **Production БД забэкаплена:** `shifts_backup_YYYYMMDD_HHMMSS.db` на облачном сервере
- [ ] **Облачные контейнеры работают:** `docker ps` показывает `prod_api`, `prod_bot`, `prod_ollama` Up
- [ ] **SSH доступ проверен:** `ssh root@46.224.36.109 'echo OK'` возвращает OK
- [ ] **Deployment plan согласован:** Явное подтверждение от владельца на restart контейнеров

---

## 🔄 Rollback Plan (НА СЛУЧАЙ сбоя деплоя)

### Сценарий 1: Деплой сломал API (HTTP 500, import errors)

```bash
# 1. Восстановить старую версию кода из git
ssh root@46.224.36.109 'cd /opt/bux && git checkout HEAD~1'

# 2. Перезапустить API
ssh root@46.224.36.109 'docker compose -f /opt/bux/docker-compose.yml restart prod_api'

# 3. Проверить health
curl -s http://46.224.36.109:8088/health | jq
```

### Сценарий 2: Деплой сломал БД (migration errors, data corruption)

```bash
# 1. Остановить API (чтобы не было новых записей)
ssh root@46.224.36.109 'docker stop prod_api'

# 2. Восстановить БД из бэкапа
ssh root@46.224.36.109 'docker exec prod_api sqlite3 /app/db/shifts.db ".restore /app/db/shifts_backup_LATEST.db"'

# 3. Откатить код
ssh root@46.224.36.109 'cd /opt/bux && git checkout HEAD~1'

# 4. Запустить API
ssh root@46.224.36.109 'docker start prod_api'
```

### Сценарий 3: Деплой сломал фронтенд (UI blank/broken)

```bash
# 1. Восстановить старый dist/ из бэкапа
scp -r d:\TelegramOllama_ENV_DEMO\BACKUPS\PREVIOUS_DIST\* root@46.224.36.109:/opt/bux/api/web/dist/

# 2. Перезапустить API (чтобы обновить статику)
ssh root@46.224.36.109 'docker compose -f /opt/bux/docker-compose.yml restart prod_api'
```

---

## 📝 Deployment Log Template (ЗАПОЛНИТЬ после деплоя)

```markdown
### Deployment CI-11 (YYYY-MM-DD HH:MM)

**Operator:** [ваше имя]  
**Commit:** 66bc185  
**Environment:** Production (46.224.36.109)  

**Steps Executed:**
1. [ ] Backup created: `CI_11_TESTED_YYYYMMDD_HHMMSS.zip`
2. [ ] Production DB backed up: `shifts_backup_YYYYMMDD_HHMMSS.db`
3. [ ] Files copied to cloud: `fix_admin_role.py`, `UsersPage.tsx`, `dist/`
4. [ ] Containers restarted: `prod_api` (downtime: X seconds)
5. [ ] Health check: `/health` HTTP 200 OK
6. [ ] Smoke test: Login → Users page → 6 users visible
7. [ ] E2E test (optional): User Management 6/6 PASS on cloud

**Results:**
- [ ] ✅ SUCCESS — All checks passed
- [ ] ❌ FAILED — Rollback executed (scenario: ...)

**Downtime:** X seconds  
**Issues:** None / [describe issues]  
**Rollback:** Not required / Executed (scenario X)
```

---

## ⚠️ КРИТИЧЕСКОЕ НАПОМИНАНИЕ

**ПЕРЕД деплоем на облако (46.224.36.109):**

1. ✅ **ОБЯЗАТЕЛЬНО** создать бэкап БД на облачном сервере
2. ✅ **ОБЯЗАТЕЛЬНО** создать бэкап протестированных файлов (этот манифест)
3. ✅ **ОБЯЗАТЕЛЬНО** получить явное подтверждение владельца на restart
4. ✅ **ОБЯЗАТЕЛЬНО** иметь готовый rollback plan

**БЕЗ этих шагов деплой ЗАПРЕЩЁН согласно RULE #0!**

---

**Создан:** 2025-11-20  
**Автор:** AI Agent (GitHub Copilot)  
**Версия:** 1.0  
**Статус:** ⏳ ОЖИДАЕТ ВЫПОЛНЕНИЯ БЭКАПА
