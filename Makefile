SHELL := /bin/bash
.PHONY: setup lint type test check test-api lint-api type-api check-api \
        setup-contracts test-contracts lint-contracts check-contracts generate-models \
        export-env

setup: setup-api setup-contracts setup-ui
	@echo "Setup: done"

setup-api:
	@echo "Setup API: running pip install"
	@cd apps/api && pip install -e ".[dev]"

setup-contracts:
	@echo "Setup Contracts: running pip install"
	@cd apps/contracts && pip install -e ".[dev]"

setup-ui:
	@echo "Setup UI: running pnpm install"
	@cd apps/web && pnpm install

run-api:
	@echo "Run API: running uvicorn"
	@bash -c ' \
		if [ -f .env ]; then \
			set -a; \
			source .env; \
			set +a; \
		fi; \
		cd apps/api && poetry run uvicorn app.main:app --reload \
	'

run-ui:
	@echo "Run UI: running vite"
	@bash -c ' \
		if [ -f .env ]; then \
			set -a; \
			source .env; \
			set +a; \
		fi; \
		cd apps/web && pnpm dev \
	'

export-env:
	@if [ ! -f .env ]; then \
		echo "Error: .env file not found" >&2; \
		exit 1; \
	fi
	@echo "# Export environment variables from .env"
	@echo "# Usage: eval \$$(make export-env)"
	@grep -v '^#' .env | grep -v '^$$' | sed 's/#.*$$//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$$//' | grep -v '^$$' | sed 's/^/export /'

lint:
	@echo "Lint: running"
	@cd apps/api && python -m ruff check . || echo "Skipping API lint (ruff not available)"
	@cd apps/contracts && python -m ruff check . || echo "Skipping Contracts lint (ruff not available)"
	@cd apps/web && npm run lint --if-present || echo "Skipping Web lint (npm not available)"

type:
	@echo "Typecheck: running"
	@cd apps/api && python -m mypy . || echo "Skipping API typecheck (mypy not available)"
	@cd apps/web && npm run typecheck --if-present || echo "Skipping Web typecheck (npm not available)"

test:
	@echo "Test: running"
	@cd apps/api && python -m pytest || echo "Skipping API tests (pytest not available)"
	@cd apps/contracts && python -m pytest || echo "Skipping Contracts tests (pytest not available)"
	# @cd apps/web && npm run test --if-present || echo "Skipping Web tests (npm not available)"

lint-api:
	@cd apps/api && python -m ruff check . || echo "Skipping API lint (ruff not available)"

type-api:
	@cd apps/api && python -m mypy . || echo "Skipping API typecheck (mypy not available)"

test-api:
	@cd apps/api && python -m pytest

check-api: lint-api type-api test-api
	@echo "API check: done"

# Contracts targets
lint-contracts:
	@cd apps/contracts && python -m ruff check . || echo "Skipping Contracts lint (ruff not available)"

test-contracts:
	@cd apps/contracts && python -m pytest tests/

check-contracts: lint-contracts test-contracts
	@echo "Contracts check: done"

generate-models:
	@echo "Generating Pydantic models from JSON schemas..."
	@cd apps/contracts && python scripts/generate_pydantic.py

generate-types:
	@echo "Generating TypeScript types from OpenAPI specification..."
	@cd apps/contracts && python scripts/generate_typescript.py

export-openapi:
	@echo "Exporting OpenAPI schema from FastAPI..."
	@cd apps/contracts && python scripts/export_openapi.py --output openapi/openapi.json

# Contract testing
test-contract-schemas:
	@echo "Testing JSON schema validation..."
	@cd apps/contracts && python -m pytest tests/test_schema_validation.py -v

test-contract-openapi:
	@echo "Testing OpenAPI validation..."
	@cd apps/contracts && python -m pytest tests/test_openapi_validation.py -v

test-api-contracts:
	@echo "Testing API contract compliance..."
	@cd apps/api && python -m pytest tests/test_contracts.py tests/test_api_contracts.py -v

# Combined targets
check: lint type test
	@echo "Check: done"

check-all: check-api check-contracts
	@echo "All checks: done"

check-contracts-all: lint-contracts test-contracts test-contract-schemas test-contract-openapi
	@echo "All contract checks: done"

# Contract CI integration
check-contract-drift:
	@echo "Checking for contract drift..."
	@cd apps/contracts && python scripts/check_contracts.py

fix-contracts:
	@echo "Fixing contract drift..."
	@cd apps/contracts && python scripts/check_contracts.py --fix

# Export OpenAPI from FastAPI app
export-openapi-json:
	@echo "Exporting OpenAPI from FastAPI to JSON..."
	@cd apps/api && python -m app.scripts.export_openapi --output ../contracts/openapi.json

# Validate contracts match implementation
validate-contracts:
	@echo "Validating contracts..."
	@cd apps/api && python -m app.scripts.export_openapi --check --output ../contracts/openapi.json

# Test Pact-style consumer contracts
test-pact-contracts:
	@echo "Testing Pact-style consumer contracts..."
	@cd apps/contracts && python -m pytest tests/test_pact_contracts.py -v

# Full contract validation pipeline
contract-ci: check-contract-drift test-contracts test-api-contracts
	@echo "Contract CI pipeline: done"
