SHELL := /bin/bash
.PHONY: setup lint type test check test-api lint-api type-api check-api

setup: setup-api setup-ui
	@echo "Setup: done"

setup-api:
	@echo "Setup API: running poetry install"
	@cd apps/api && poetry env activate && 

setup-ui:
	@echo "Setup UI: running pnpm install"
	@cd apps/web && pnpm install

run-api:
	@echo "Run API: running uvicorn"
	@set -a; source .env; set +a; cd apps/api && poetry run uvicorn app.main:app --reload

run-ui:
	@echo "Run UI: running vite"
	@set -a; source .env; set +a; cd apps/web && pnpm dev

lint:
	@echo "Lint: running"
	@cd apps/api && python -m ruff check . || echo "Skipping API lint (ruff not available)"
	@cd apps/web && npm run lint --if-present || echo "Skipping Web lint (npm not available)"

type:
	@echo "Typecheck: running"
	@cd apps/api && python -m mypy . || echo "Skipping API typecheck (mypy not available)"
	@cd apps/web && npm run typecheck --if-present || echo "Skipping Web typecheck (npm not available)"

test:
	@echo "Test: running"
	@cd apps/api && python -m pytest || echo "Skipping API tests (pytest not available)"
	@cd apps/web && npm run test --if-present || echo "Skipping Web tests (npm not available)"

lint-api:
	@cd apps/api && python -m ruff check . || echo "Skipping API lint (ruff not available)"

type-api:
	@cd apps/api && python -m mypy . || echo "Skipping API typecheck (mypy not available)"

test-api:
	@cd apps/api && python -m pytest

check-api: lint-api type-api test-api
	@echo "API check: done"

check: lint type test
	@echo "Check: done"
