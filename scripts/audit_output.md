# CI-9 ORM/Alembic Schema Audit

## ORM-only tables (models.py, нет миграций):
- auth_credentials
- channel_messages
- clients
- employees
- idempotency_keys
- invoices
- refresh_tokens
- salaries
- schedules
- shifts
- telegram_users
- worker_expenses
- worker_tasks

## Alembic-only tables (миграции, нет ORM):

## Итог:
Для каждого объекта требуется объяснение или задача в TECH_DEBT/CI-9.x.
