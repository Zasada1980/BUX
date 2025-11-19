# TelegramOllama Work Ledger

> **Система учёта рабочего времени и расходов для малого бизнеса с Telegram-ботом и AI-агентом**

<!-- CI-15 trigger: Test langsmith fix after workflow syntax correction -->

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-required-blue.svg)](https://www.docker.com/)

Local-first система управления сменами, задачами, расходами и зарплатами с интеграцией Telegram бота и локального LLM (Ollama). Все данные хранятся локально в SQLite, без зависимости от внешних облачных сервисов.

## ✨ Возможности

### 📱 Telegram Bot
- **Управление сменами**: Начало/окончание смены (`/in`, `/out`)
- **Задачи и расходы**: Добавление задач с pricing rules (`/task`), учёт расходов (`/expense`)
- **Inbox модерации**: Утверждение pending changes с bulk operations
- **Админ-панель**: Управление пользователями, заказчиками, расписанием
- **Зарплаты**: Импорт из Excel (TSV), сопоставление работников
- **Отчёты**: Месячные отчёты в CSV формате
- **RBAC**: 3 роли (Admin/Foreman/Worker) с custom меню для каждой роли

### 💻 Web UI (React SPA)
- **Dashboard**: Обзор активных смен, статистика, уведомления
- **Inbox**: Модерация pending задач/расходов с bulk approve/reject
- **Users**: Управление пользователями (CRUD, роли, дневные ставки)
- **Expenses**: Просмотр и фильтрация расходов с CSV export
- **Invoices**: Генерация счетов с preview и версионированием
- **Shifts**: Просмотр истории смен с фильтрами
- **Profile**: Смена пароля, управление настройками профиля
- **Settings**: Конфигурация системы, резервное копирование
- **Bot Menu**: Управление командами Telegram бота через веб-интерфейс
- **JWT Auth**: Безопасная аутентификация с token-based доступом

### 🚀 FastAPI Backend
- **RESTful API**: Shift management, tasks, expenses, invoices
- **Idempotency**: G4 gate с `Idempotency-Key` для bulk операций (≤100ms repeat detection)
- **Money formatting**: Φ0-P1/P2 gates с Decimal-only политикой (NO float)
- **OCR Policy**: Обязательные фото для расходов > threshold
- **Invoice System**: Preview tokens (one-time SHA256), versioning, AI-powered diff
- **Alembic migrations**: Управление схемой БД с версионированием

### 🤖 AI Agent (Ollama)
- **RAG**: Skeptic mode с null corpus abstention (AI-eval CP-1)
- **Expense categorization**: AI-based категоризация расходов (CP-2)
- **Pricing explanations**: YAML rule breakdown (CP-3)
- **Invoice diff**: Version comparison с рекомендациями (CP-4)

### 📊 Reporting & Analytics
- **JSONL Metrics**: Daily rotation (7 days), kinds: shift.start/end, expense.add, mod.approve/reject
- **CSV Export**: Месячные отчёты по работникам (часы, задачи, расходы, зарплаты)
- **Audit Log**: Полная трассировка действий с payload_hash

## 🏗️ Архитектура

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│  Telegram   │ ────▶│  FastAPI     │ ────▶│   SQLite    │
│    Bot      │      │ (DEMO: 8188) │      │  Database   │
│  (aiogram)  │◀──── │ (PROD: 8088) │◀──── │             │
└─────────────┘      └──────┬───────┘      └─────────────┘
                            │
                     ┌──────┴───────┐
                     │              │
                     ▼              ▼
              ┌──────────────┐ ┌──────────────┐
              │    Ollama    │ │   React SPA  │
              │(DEMO: 11444) │ │   (Vite dev: │
              │(PROD: 11434) │ │    port 3000)│
              │  LLM Agent   │ │   Web UI     │
              └──────────────┘ └──────────────┘
```

**Компоненты**:
- **bot/**: Telegram bot (aiogram) с FSM, inline UI, RBAC (Admin/Foreman/Worker), custom меню
- **api/**: FastAPI service с endpoints, models, utils, migrations, JWT auth
- **api/web/**: React 18 + Vite SPA (9 страниц: Dashboard, Inbox, Users, Expenses, Invoices, Shifts, Profile, Settings, Bot Menu)
- **agent/**: Ollama LLM integration для AI-eval и RAG (опционально)
- **db/**: SQLite database (`/app/db/shifts.db`), Alembic migrations, 20+ таблиц

## 🚀 Быстрый старт

### Требования

- **Docker** + Docker Compose
- **Python** 3.11+ (для локальной разработки)
- **Ollama** (для AI-функций, опционально)

### Установка

1. **Клонировать репозиторий**:
```bash
git clone https://github.com/Zasada1980/TelegramOllama.git
cd TelegramOllama
```

2. **Настроить переменные окружения**:
```bash
# Использовать шаблон (НЕ копировать .env напрямую!)
cp config/.env.telegramollama.template .env
```

Отредактировать `.env` (22 переменные):
```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
BOT_ADMINS=YOUR_TELEGRAM_ID
BOT_FOREMEN=FOREMAN_ID_1,FOREMAN_ID_2
BOT_WORKERS=WORKER_ID_1,WORKER_ID_2

# Database (НЕ менять путь!)
DB_PATH=/app/db/shifts.db

# API
API_PORT=8188  # DEMO: 8188, PROD: 8088
INTERNAL_ADMIN_SECRET=your-secret-here

# Ollama
OLLAMA_PORT=11444  # DEMO: 11444, PROD: 11434
OLLAMA_MODEL=llama3.1:8b
```

**⚠️ КРИТИЧНО**: Генерируйте секреты заново для каждого окружения:
```bash
openssl rand -hex 32  # Для INTERNAL_ADMIN_SECRET
```

3. **Запустить сервисы**:
```bash
docker compose up -d
```

4. **Применить миграции**:
```bash
docker compose exec api alembic upgrade head
```

5. **Заполнить тестовыми данными** (опционально):
```bash
docker compose exec api python seeds/seed_gold_ils.py
```

### Проверка работоспособности

```bash
# API health check (DEMO environment)
curl http://127.0.0.1:8188/health

# Web UI
open http://localhost:3000  # Vite dev server
# Логин: admin / admin123

# Проверка БД
docker compose exec api sqlite3 /app/db/shifts.db "SELECT telegram_id, name, role FROM users;"

# Логи сервисов
docker compose logs -f bot    # Telegram bot
docker compose logs -f api    # FastAPI backend
docker compose logs -f agent  # AI agent

# Swagger API docs
open http://127.0.0.1:8188/docs
```

## 📚 Использование

### Telegram Bot

1. **Получить бота**: [@BotFather](https://t.me/BotFather) → `/newbot`
2. **Добавить свой Telegram ID в `.env`**: `TELEGRAM_ADMIN_IDS=YOUR_ID`
3. **Запустить бота**: `/start` в Telegram
4. **Админ команды**:
   - `/admin` — Админ-панель (пользователи, заказчики, отчёты)
   - `/worker` — Рабочая панель (смены, задачи, расходы)

### API Endpoints

**Смены**:
```bash
# Начать смену
POST /api/v1/shift/start
Body: {"user_id": "john", "client_id": 1}

# Закончить смену
POST /api/v1/shift/end
Body: {"user_id": "john"}
```

**Зарплаты**:
```bash
# Импорт preview
POST /api/admin/salaries/import/preview
Body: {"raw_text": "Иван\t5000\nПётр\t4500"}

# Применить импорт
POST /api/admin/salaries/import/apply
Body: {"raw_text": "Иван\t5000", "payment_date": "2024-11-14"}
```

**Отчёты**:
```bash
# CSV экспорт
GET /api/admin/reports/monthly.csv?month=2024-11

# JSON данные
GET /api/admin/reports/monthly.json?month=2024-11
```

## 🧪 Тестирование

### Makefile Commands (PowerShell/Bash)

```bash
# API smoke tests
make smoke-api          # GET /health
make smoke-report       # GET /api/report.worker/demo
make smoke-task         # POST /api/task.add

# Backend tests
make test-report        # pytest для report endpoints

# Database migrations
make migrate            # Alembic upgrade head

# AI evaluation (опционально)
make ai-eval-all        # All checkpoints (CP-1 through CP-4)
```

### Web UI E2E Tests (Playwright)

```bash
cd api/web

# Run all E2E tests
npm run test:e2e              # Headless mode (CI)
npm run test:e2e:ui           # Interactive UI mode (debug)
npm run test:e2e:headed       # Headed browser mode

# Run specific test
npx playwright test e2e/inbox-bulk-approve.spec.ts
```

## 📖 Документация

**Architecture & Design**:
- **[architecture/ARCHITECTURE_V2.md](architecture/ARCHITECTURE_V2.md)**: Service boundaries, DB SoT, module structure
- **[architecture/UX_PLAYBOOK.md](architecture/UX_PLAYBOOK.md)**: All 9 UX scenarios (Inbox, Users, Expenses, etc.)
- **[architecture/FRONTEND_ARCHITECTURE.md](architecture/FRONTEND_ARCHITECTURE.md)**: React SPA implementation status

**Reports & Progress**:
- **[reports/F4_E2E_COVERAGE_MATRIX.md](reports/F4_E2E_COVERAGE_MATRIX.md)**: E2E test coverage (v4.0.0 — 100% PASS)
- **[reports/F6_CHAT_SESSION_REPORT_2025_11_17.md](reports/F6_CHAT_SESSION_REPORT_2025_11_17.md)**: Latest session report (problems before cloud)
- **[tech_debt/TECH_DEBT_F4_5.md](tech_debt/TECH_DEBT_F4_5.md)**: Technical debt status (F5 — all resolved)

**Roadmap & Migration**:
- **[roadmap/F6_ENV_MIGRATION_GUIDE.md](roadmap/F6_ENV_MIGRATION_GUIDE.md)**: Step-by-step cloud deployment guide
- **[roadmap/FINAL_MIGRATION_AND_DEV_OVERVIEW.md](roadmap/FINAL_MIGRATION_AND_DEV_OVERVIEW.md)**: Environment migration workflows
- **[DOCS_INDEX.md](DOCS_INDEX.md)**: Complete documentation index

**API Documentation**:
- **[Swagger UI](http://127.0.0.1:8188/docs)**: Interactive API docs (DEMO environment, после запуска)

## 🔒 Безопасность

**Критические принципы**:
- ✅ **Money NEVER float**: Φ0-P1/P2 gates, только Decimal
- ✅ **Idempotency**: G4 gate для всех bulk операций
- ✅ **Audit trail**: Полная трассировка в `audit_log` table
- ✅ **RBAC**: Role-based access (Admin/Foreman/Worker)
- ✅ **One-time tokens**: SHA256 preview tokens для invoices
- ✅ **OCR Policy**: Обязательные фото для крупных расходов

**Known Technical Debt**:
- TD-D1: `delete_item` runtime блокировка (RESOLVED, см. `api/G5_EVIDENCE.md`)

## 🛠️ Разработка

### Структура проекта

```
TelegramOllama/
├── api/                    # FastAPI backend
│   ├── endpoints_*.py      # API routes (auth, users, shifts, etc.)
│   ├── models.py           # SQLAlchemy models (Shift, Task, Expense)
│   ├── models_users.py     # User models + RBAC
│   ├── utils/              # Helpers (money, idempotency, audit)
│   ├── db.py               # Database connection
│   └── web/                # React SPA (Web UI)
│       ├── src/
│       │   ├── pages/      # React pages (Dashboard, Inbox, Users, etc.)
│       │   ├── components/ # Reusable UI components
│       │   └── lib/        # API client, auth context
│       ├── e2e/            # Playwright E2E tests (9 scenarios)
│       ├── vite.config.ts  # Vite configuration (proxy to API)
│       └── package.json    # npm dependencies
├── bot/                    # Telegram bot (aiogram)
│   ├── main.py             # Entry point, polling, menu setup
│   ├── config.py           # Bot config (RBAC, DB_PATH)
│   ├── admin_handlers/     # Admin panel (users, clients, reports)
│   ├── worker_handlers/    # Worker panel (shifts, tasks, expenses)
│   └── foreman_handlers/   # Foreman panel (moderation, stats)
├── db/                     # SQLite database
│   └── shifts.db           # Main database (runtime: /app/db/shifts.db)
├── agent/                  # Ollama AI integration
│   ├── main.py             # AI agent server
│   └── prompts/            # AI prompts (RAG, OCR, pricing)
├── seeds/                  # Database seed data
│   └── seed_e2e_minimal.py # E2E test data seeder
├── scripts/                # Utility scripts
├── docker-compose.yml      # Services definition (api, bot, agent, ollama)
├── alembic.ini             # Alembic configuration
├── Makefile                # Make commands (smoke tests, migrations)
└── .env                    # Environment variables (22 vars)
```

### Добавление миграции

```bash
# Автогенерация
docker compose exec api alembic revision --autogenerate -m "<description>"

# Применение
docker compose exec api alembic upgrade head

# Откат
docker compose exec api alembic downgrade -1
```

### Локальная разработка

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить API локально
cd api && uvicorn main:app --reload --port 8088

# Запустить бота локально
cd bot && python main.py
```

## 📊 Метрики и мониторинг

**JSONL Metrics** (`logs/metrics/api.jsonl`):
```json
{"ts": "2025-11-14T13:30:00Z", "kind": "shift.start", "payload": {"user_id": "john"}}
{"ts": "2025-11-14T18:00:00Z", "kind": "shift.end", "payload": {"user_id": "john", "duration_s": 16200}}
```

**Daily rotation**: `logs/metrics/YYYY-MM-DD/api.jsonl` (retention: 7 days)

**Kinds**:
- `shift.start`, `shift.end`
- `expense.add`, `task.add`
- `mod.approve`, `mod.reject`
- `bot.ui.debounce.hit/miss`

## 🧪 E2E Tests (Playwright)

**Web SPA E2E Coverage** (v4.0.0 — F5 COMPLETE):

```bash
cd api/web
npm run test:e2e              # Headless mode
npm run test:e2e:ui           # Interactive UI mode
```

**Статус тестов** (F5 — 100% PASS ✨):
- ✅ **PASS: 9 / 9** — Все UX сценарии реализованы и протестированы
  - inbox-bulk-approve.spec.ts (5.6s)
  - user-management.spec.ts (3.7s)
  - expenses-filter-csv.spec.ts (4.2s)
  - invoices-review-csv.spec.ts (5.1s)
  - shift-review.spec.ts (2.5s)
  - bot-menu-config.spec.ts (7.7s)
  - dashboard-overview.spec.ts (2.8s)
  - settings-smoke.spec.ts (1.0s)
  - profile-password-change.spec.ts (3.5s)
- ⏭️ **SKIP: 0 / 9**
- ❌ **FAIL: 0 / 9**

Все F5 сценарии проходят полностью. Подробности см. в `reports/F4_E2E_COVERAGE_MATRIX.md` (v4.0.0).

---

## v2.0.0 Complete Web UI (F5 Complete)

- [x] **9/9 UX Scenarios implemented** — 100% E2E test coverage (all PASS ✨)
- [x] **JWT/Auth** — Unified authentication across all pages
- [x] **Settings Page** — Refactored (General/Backup/System tabs)
- [x] **Shifts Page** — Full implementation (GET /api/shifts + ShiftsPage.tsx)
- [x] **Bot Menu Config** — DB tables + backend + frontend + E2E test (7.7s PASS)
- [x] **CSV Export** — Buttons present (disabled, roadmap F6+)
- [x] **RBAC** — 3 roles (Admin/Foreman/Worker) with Telegram custom menus
- [x] **Tech Debt F4.5** — All 3 items resolved (TECH_DEBT_F4_5.md CLOSED)
- [x] **Документация**:
  - `F4_E2E_COVERAGE_MATRIX.md` v4.0.0 — 100% PASS coverage
  - `F6_CHAT_SESSION_REPORT_2025_11_17.md` — Critical analysis before cloud
  - `FINAL_MIGRATION_AND_DEV_OVERVIEW.md` — Environment migration guide

**Release:** v2.0.0 (F5 Complete)  
**Date:** 17 November 2025  
**Status:** ✅ Local Ready, ⚠️ Cloud Migration Blocked (see F6_CHAT_SESSION_REPORT)

---

## 🤝 Вклад в проект

Pull requests приветствуются! Для крупных изменений создайте issue для обсуждения.

**Процесс**:
1. Fork репозитория
2. Создать feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit изменений (`git commit -m 'Add AmazingFeature'`)
4. Push в branch (`git push origin feature/AmazingFeature`)
5. Открыть Pull Request

**Критерии приёмки**:
- ✅ Skeptic validation: 11/12+ PASS (`check-skeptic.ps1`)
- ✅ AI-eval: 3/5+ PASS Phase 13, 5/5 PASS Phase 14+ (`run-ai-eval.ps1`)
- ✅ No lint errors (critical only)
- ✅ Evidence файлы для critical changes

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE)

## 👥 Авторы

**TelegramOllama Team**

## 🙏 Благодарности

- [aiogram](https://github.com/aiogram/aiogram) - Telegram Bot framework
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Ollama](https://ollama.ai/) - Local LLM runtime
- [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL toolkit
- [Alembic](https://alembic.sqlalchemy.org/) - Database migration tool

## 📞 Поддержка

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/TelegramOllama/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_USERNAME/TelegramOllama/discussions)

---

**⭐ Если проект вам помог, поставьте звезду!**
