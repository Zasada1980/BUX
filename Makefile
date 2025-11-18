.PHONY: venv lint test compose-up compose-down clean help run-api run-agent smoke migrate seed smoke-api shift-start run-bot test-report smoke-report smoke-task smoke-invoice

help:
	@echo "TelegramOllama - Local Development Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  venv         - Create Python virtual environment"
	@echo "  install      - Install dependencies (requires venv)"
	@echo "  lint         - Run linters (ruff, mypy)"
	@echo "  test         - Run tests with pytest"
	@echo "  run-api      - Run API service locally (127.0.0.1:8088)"
	@echo "  run-agent    - Run Agent service locally (127.0.0.1:8080)"
	@echo "  smoke        - Run smoke tests (check /health endpoints)"
	@echo "  migrate      - Apply database migrations in api container"
	@echo "  seed         - Create test shift via API"
	@echo "  smoke-api    - Smoke test /health API endpoint"
	@echo "  shift-start  - Smoke test /api/v1/shift/start endpoint"
	@echo "  run-bot      - Run Telegram bot locally (requires TELEGRAM_BOT_TOKEN)"
	@echo "  test-report  - Run report endpoint tests"
	@echo "  smoke-report - Smoke test /api/report.worker endpoint"
	@echo ""
	@echo "AI-Eval targets (Anti-Hallucination Checkpoints):"
	@echo "  ai-eval-expense      - CP-2: Expense OCR categorization (accuracy ≥0.75)"
	@echo "  ai-eval-pricing      - CP-3: Pricing formula explanation (coverage=1.0)"
	@echo "  ai-eval-rag-null     - CP-1: RAG null corpus test (unknown_rate ≥0.95)"
	@echo "  ai-eval-rag-needle   - CP-1: RAG needle haystack (top1_hit ≥0.85)"
	@echo "  ai-eval-invoice-diff - CP-4: Invoice diff validation (exact_match ≥0.95)"
	@echo "  ai-eval-all          - Run all AI-Eval checkpoints"
	@echo "  smoke-task   - Smoke test /api/task.add endpoint"
	@echo "  smoke-invoice- Smoke test /api/invoice.build endpoint"
	@echo "  smoke-invoice-preview    - Smoke test invoice preview issue+view"
	@echo "  smoke-invoice-suggest-apply - Smoke test suggestion + apply flow"
	@echo "  compose-up   - Start Docker Compose services"
	@echo "  compose-down - Stop Docker Compose services"
	@echo "  clean        - Remove generated files and caches"

venv:
	python -m venv .venv
	@echo "Virtual environment created. Activate with:"
	@echo "  Windows: .venv\\Scripts\\activate"
	@echo "  Linux/Mac: source .venv/bin/activate"

install:
	pip install -e ".[dev]"

lint:
	ruff check . --fix || true
	ruff format . || true
	mypy src/ || true

test:
	pytest -v --cov=src --cov-report=html --cov-report=term

run-api:
	python -m uvicorn api.main:app --host 127.0.0.1 --port 8088

run-agent:
	python -m uvicorn agent.main:app --host 127.0.0.1 --port 8080

smoke:
	powershell -Command "Invoke-RestMethod http://127.0.0.1:8080/health | ConvertTo-Json | Out-File -Encoding utf8 logs/health_agent.json"
	powershell -Command "Invoke-RestMethod http://127.0.0.1:8088/health | ConvertTo-Json | Out-File -Encoding utf8 logs/health_api.json"
	@echo "Smoke tests completed. Results saved to logs/health_*.json"

migrate:
	docker compose exec api alembic upgrade head

seed:
	powershell -Command "$$b = @{ user_id = 'seed' } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8088/api/v1/shift/start -Body $$b -ContentType 'application/json'"

smoke-api:
	powershell -Command "Invoke-RestMethod http://127.0.0.1:8088/health | ConvertTo-Json | Out-File -Encoding utf8 logs/health_api.json"

shift-start:
	powershell -Command "$$body = @{ user_id = 'smoke'; meta = @{ source = 'makefile' } } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8088/api/v1/shift/start -Body $$body -ContentType 'application/json' | ConvertTo-Json | Out-File -Encoding utf8 logs/shift_start_smoke.json"
	@echo "Shift start smoke test completed. Result saved to logs/shift_start_smoke.json"

run-bot:
	python bot/main.py

test-report:
	pytest -q tests/test_report_worker.py

smoke-report:
	@mkdir -p logs
	powershell -Command "$$from = (Get-Date).AddDays(-1).ToString('s'); $$to = (Get-Date).AddDays(1).ToString('s'); $$uri = 'http://127.0.0.1:8088/api/report.worker/demo?from=' + $$from + '&to=' + $$to; Invoke-RestMethod -Uri $$uri | ConvertTo-Json | Out-File -Encoding utf8 logs/report_worker_demo.json"
	@echo "Report smoke test completed. Result saved to logs/report_worker_demo.json"

smoke-task:
	@mkdir -p logs
	powershell -Command "$$h = @{ 'Idempotency-Key' = 'task-smoke-1' }; $$b = @{ shift_id=1; rate_code='piece_demo'; qty=2 } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/task.add' -Headers $$h -Body $$b -ContentType 'application/json' | ConvertTo-Json | Out-File -Encoding utf8 logs/task_add_smoke.json"
	@echo "Task smoke test completed. Result saved to logs/task_add_smoke.json"

smoke-expense:
	@mkdir -p logs
	powershell -Command "$$h = @{ 'Idempotency-Key' = 'exp-smoke-1' }; $$b = @{ worker_id='demo'; category='питание'; amount=350; currency='RUB' } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/expense.add' -Headers $$h -Body $$b -ContentType 'application/json' | ConvertTo-Json | Out-File -Encoding utf8 logs/expense_add_smoke.json"
	@echo "Expense smoke test completed. Result saved to logs/expense_add_smoke.json"

smoke-shift-end:
	@mkdir -p logs
	powershell -Command "$$b = @{ user_id='demo' } | ConvertTo-Json; $$sid = (Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/v1/shift/start' -Body $$b -ContentType 'application/json').id; $$b2 = @{ shift_id=$$sid; rate_code='piece_demo'; qty=2 } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/task.add' -Body $$b2 -ContentType 'application/json' | Out-Null; $$b3 = @{ shift_id=$$sid } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/v1/shift/end' -Body $$b3 -ContentType 'application/json' | ConvertTo-Json | Out-File -Encoding utf8 logs/shift_end_smoke.json"
	@echo "Shift end smoke test completed. Result saved to logs/shift_end_smoke.json"

smoke-invoice:
	@mkdir -p logs
	powershell -Command "$$b = @{ client_id='demo'; period_from='2000-01-01'; period_to='2100-01-01'; currency='RUB' } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/invoice.build' -Body $$b -ContentType 'application/json' | ConvertTo-Json | Out-File -Encoding utf8 logs/invoice_build_smoke.json"
	@echo "Invoice build smoke test completed. Result saved to logs/invoice_build_smoke.json"

# AI Evaluation targets (Anti-Hallucination Checkpoints)
ai-eval-expense:
	@echo "=== CP-2: Expense OCR Categorization Test ==="
	python ai_eval/expense/run_expense_eval.py | tee logs/ai_eval_expense.json

ai-eval-pricing:
	@echo "=== CP-3: Pricing Formula Explanation Test ==="
	python ai_eval/pricing/run_pricing_eval.py | tee logs/ai_eval_pricing.json

ai-eval-rag-null:
	@echo "=== CP-1: RAG Null Corpus Test ==="
	python ai_eval/rag/run_rag_eval.py --mode null --corpus ai_eval/rag/nullset | tee logs/ai_eval_rag_null.json

ai-eval-rag-needle:
	@echo "=== CP-1: RAG Needle in Haystack Test ==="
	python ai_eval/rag/run_rag_eval.py --mode needle --corpus ai_eval/rag/needle | tee logs/ai_eval_rag_needle.json

ai-eval-invoice-diff:
	@echo "=== CP-4: Invoice Suggestions Diff Test ==="
	python ai_eval/invoice/run_invoice_diff_eval.py | tee logs/ai_eval_invoice_diff.json

ai-eval-all: ai-eval-expense ai-eval-pricing ai-eval-rag-null ai-eval-rag-needle ai-eval-invoice-diff
	@echo "=== All AI-Eval Checkpoints Complete ==="
	@echo "Results saved to logs/ai_eval_*.json"

# OCR smoke tests (Phase 13 Task 4)
smoke-ocr:
	@mkdir -p logs
	powershell -Command "$$b = @{ worker_id='1'; shift_id=1; category='transport'; amount=1200; currency='RUB'; photo_ref='samples/receipt1.jpg' } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/expense.add' -Body $$b -ContentType 'application/json' -Headers @{'Idempotency-Key'='ocr-smoke-1'} | ConvertTo-Json | Out-File -Encoding utf8 logs/expense_ocr_smoke.json; Get-Content api/logs/metrics/api.jsonl | Select-String '\"kind\": \"ocr.run\"' | Select-Object -Last 1"
	@echo "OCR smoke test completed. Result saved to logs/expense_ocr_smoke.json"

ocr-on:
	powershell -Command "if (Test-Path .env) { (Get-Content .env) -replace 'OCR_ENABLED=.*','OCR_ENABLED=true' | Set-Content .env } else { 'OCR_ENABLED=true' | Out-File .env -Encoding utf8 }"
	@echo "OCR enabled in .env"

ocr-off:
	powershell -Command "if (Test-Path .env) { (Get-Content .env) -replace 'OCR_ENABLED=.*','OCR_ENABLED=false' | Set-Content .env } else { 'OCR_ENABLED=false' | Out-File .env -Encoding utf8 }"
	@echo "OCR disabled in .env"

smoke-invoice-preview:
	@mkdir -p logs
	powershell -Command "$$b = @{ client_id='smokeprev'; period_from='2000-01-01'; period_to='2100-01-01'; currency='RUB' } | ConvertTo-Json; $$inv = (Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/invoice.build' -Body $$b -ContentType 'application/json').id; $$iss = Invoke-RestMethod -Method Post -Uri ('http://127.0.0.1:8088/api/invoice.preview/' + $$inv + '/issue'); $$tok = $$iss.token; Invoke-RestMethod -Uri ('http://127.0.0.1:8088/api/invoice.preview/' + $$inv + '?token=' + $$tok) | Out-File -Encoding utf8 logs/invoice_preview.html"
	@echo "Invoice preview smoke test completed. HTML saved to logs/invoice_preview.html"

smoke-invoice-suggest-apply:
	@mkdir -p logs
	powershell -Command "$$b = @{ client_id='smokesugg'; period_from='2000-01-01'; period_to='2100-01-01'; currency='RUB' } | ConvertTo-Json; $$inv = (Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/invoice.build' -Body $$b -ContentType 'application/json').id; $$tok = (Invoke-RestMethod -Method Post -Uri ('http://127.0.0.1:8088/api/invoice.preview/' + $$inv + '/issue')).token; $$sugBody = @{ invoice_id = $$inv; token = $$tok; kind='add_item'; payload = @{ item = @{ task='extra'; qty=1; unit='unit'; amount=123.45; worker='w'; site='s' } } } | ConvertTo-Json -Depth 6; $$sug = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/invoice.suggest_change' -Body $$sugBody -ContentType 'application/json'; $$applyBody = @{ invoice_id=$$inv; suggestion_ids=@($$sug.id) } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8088/api/invoice.apply_suggestions' -Body $$applyBody -ContentType 'application/json' | ConvertTo-Json | Out-File -Encoding utf8 logs/invoice_apply.json"
	@echo "Invoice suggestion+apply smoke test completed. Result saved to logs/invoice_apply.json"



compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

clean:
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + || true
	find . -type f -name "*.pyc" -delete || true
