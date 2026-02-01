# Daru PDF Contracts

Contract definitions (OpenAPI, JSON Schema, examples) for daru-pdf services.

## Overview

This package provides the single source of truth for all service contracts in the Daru PDF system. It includes:

- **OpenAPI 3.1 Specification** - HTTP API contracts
- **JSON Schema (draft-07)** - Data model definitions
- **Examples** - Request/response samples for testing and documentation
- **Code Generation** - Scripts to generate Pydantic models

## Directory Structure

```
contracts/
├── openapi/
│   └── api.yaml           # OpenAPI 3.1 specification for Public API
├── schemas/
│   ├── common.json        # Shared types (BBox, Confidence, PageRef, etc.)
│   ├── document.json      # Document model
│   ├── field.json         # Field model
│   ├── mapping.json       # Mapping model
│   ├── extraction.json    # Extraction model
│   ├── evidence.json      # Evidence model
│   ├── activity.json      # Activity model
│   ├── issue.json         # Issue model
│   └── job_context.json   # JobContext model (aggregates all models)
├── examples/
│   ├── documents/         # Document upload/get examples
│   └── jobs/              # Job CRUD operation examples
├── tests/
│   ├── test_schema_validation.py
│   └── test_openapi_validation.py
├── scripts/
│   └── generate_pydantic.py
├── pyproject.toml
└── README.md
```

## Key Models

### Document
Represents an uploaded PDF or image file.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| ref | string | Reference path or filename |
| meta.page_count | integer | Number of pages |
| meta.size_bytes | integer | File size in bytes |
| meta.mime_type | string | MIME type (e.g., application/pdf) |
| meta.created_at | datetime | Upload timestamp |

### Field
Represents a data field extracted from or to be filled in a document.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| name | string | Human-readable field name |
| type | enum | text, number, date, checkbox, signature, image |
| value | any | Field value |
| confidence | number (0-1) | Confidence score |
| bbox | BBox | Bounding box location |
| source | enum | extracted, manual, default |

### JobContext
Complete state of a document processing job.

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique identifier |
| status | enum | pending, running, blocked, done, failed |
| mode | enum | transfer (copy from source), scratch (fill from scratch) |
| documents | array | Associated documents |
| fields | array | All fields in the job |
| mappings | array | Field mappings (for transfer mode) |
| extractions | array | Extracted values |
| issues | array | Detected issues |
| activities | array | Activity log entries |

## Installation

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Or using uv
uv pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all contract tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=tests --cov-report=html

# Run specific test classes
pytest tests/test_schema_validation.py -v
pytest tests/test_openapi_validation.py -v
```

## Code Generation

### Pydantic Models from JSON Schemas

```bash
# Generate individual model files
python scripts/generate_pydantic.py

# Generate to specific directory
python scripts/generate_pydantic.py --output-dir ../api/app/models/generated

# Generate combined single file
python scripts/generate_pydantic.py --combined
```

### TypeScript Types from OpenAPI

```bash
# Generate TypeScript types from OpenAPI YAML
python scripts/generate_typescript.py

# Generate from FastAPI app directly
python scripts/generate_typescript.py --source fastapi

# Custom output location
python scripts/generate_typescript.py --output ../../web/src/lib/api-types.ts
```

### Export OpenAPI from FastAPI

```bash
# Export FastAPI-generated OpenAPI to JSON
python scripts/export_openapi.py

# Custom output location
python scripts/export_openapi.py --output openapi/openapi.json

# From API directory (recommended)
cd apps/api && python -m app.scripts.export_openapi --output ../contracts/openapi.json

# Validate schema completeness
python -m app.scripts.export_openapi --validate

# Check for drift (CI mode)
python -m app.scripts.export_openapi --check
```

### Check Contract Drift (CI)

```bash
# Check all contracts are in sync with implementation
python scripts/check_contracts.py

# Automatically fix any drift
python scripts/check_contracts.py --fix

# Verbose output
python scripts/check_contracts.py --verbose
```

## Versioning and Compatibility

Contracts follow [Semantic Versioning](https://semver.org/):

- **MAJOR** - Breaking changes (field removal, type changes)
- **MINOR** - Backward-compatible additions
- **PATCH** - Documentation and non-functional changes

### Compatibility Rules

1. **Breaking changes** require major version bump
2. **New optional fields** are allowed in minor versions
3. **Deprecated fields** must have a deprecation period before removal
4. **Enum additions** are backward-compatible (minor version)

## Contract Testing

All examples are validated against their schemas:

1. **JSON Schema validation** - Examples must pass schema validation
2. **OpenAPI validation** - API spec must be valid OpenAPI 3.1
3. **Consistency checks** - Cross-schema references must resolve
4. **Pact-style consumer tests** - Expected API interactions are documented

Example files include a `$schema` reference for validation:

```json
{
  "$schema": "../../schemas/document.json#/definitions/Document",
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "ref": "uploads/invoice.pdf",
  "meta": { ... }
}
```

### Contract Test Types

| Test Type | Location | Purpose |
|-----------|----------|---------|
| Schema Validation | `tests/test_schema_validation.py` | Validates examples against JSON schemas |
| OpenAPI Validation | `tests/test_openapi_validation.py` | Validates OpenAPI spec format |
| Contract Validation | `tests/test_contract_validation.py` | Request/response round-trip tests |
| Pact Contracts | `tests/test_pact_contracts.py` | Consumer-driven contract tests |

### Running Contract Tests

```bash
# Run all contract tests
make test-contracts

# Run specific test suites
pytest tests/test_contract_validation.py -v  # Contract validation
pytest tests/test_pact_contracts.py -v       # Pact-style tests

# Check for contract drift
make check-contract-drift

# Fix drifted contracts
make fix-contracts

# Full CI pipeline
make contract-ci
```

## API Endpoints Summary

| Method | Path | Description |
|--------|------|-------------|
| POST | /documents | Upload a document |
| GET | /documents/{id} | Get document by ID |
| GET | /documents/{id}/pages/{page}/preview | Get page preview |
| POST | /jobs | Create a new job |
| GET | /jobs/{id} | Get job context |
| POST | /jobs/{id}/run | Execute job processing |
| POST | /jobs/{id}/answers | Provide answers to questions |
| POST | /jobs/{id}/edits | Submit manual edits |
| GET | /jobs/{id}/review | Get review data |
| GET | /jobs/{id}/activity | Get activity log |
| GET | /jobs/{id}/evidence | Get evidence for extractions |
| GET | /jobs/{id}/output.pdf | Download completed PDF |
| GET | /jobs/{id}/export.json | Export job data as JSON |
| GET | /jobs/{id}/events | SSE stream for real-time updates |

## Usage in Services

### Importing Schemas

Services can reference schemas using JSON Schema `$ref`:

```json
{
  "$ref": "https://daru-pdf.io/schemas/field.json#/definitions/Field"
}
```

### Generated Pydantic Models

After running the generation script, import models:

```python
from contracts.generated import (
    Document,
    Field,
    JobContext,
    BBox,
    Confidence,
)
```

## Contributing

1. Update schema files in `schemas/`
2. Add/update examples in `examples/`
3. Run tests to validate changes
4. Update README if adding new models

## License

MIT
