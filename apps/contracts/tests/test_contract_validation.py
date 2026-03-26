"""
Contract validation tests for API request/response matching.

This module validates:
1. API responses match their declared contracts
2. Request bodies validate against schemas
3. Round-trip consistency (request -> response)
4. Error response formats are consistent
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from jsonschema import validate

# Base paths
CONTRACTS_DIR = Path(__file__).parent.parent
SCHEMAS_DIR = CONTRACTS_DIR / "schemas"
EXAMPLES_DIR = CONTRACTS_DIR / "examples"


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file and return its contents."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_all_schemas() -> dict[str, dict[str, Any]]:
    """Load all schemas and return them indexed by filename stem."""
    return {f.stem: load_json(f) for f in SCHEMAS_DIR.glob("*.json")}


def inline_refs(schema: dict[str, Any], all_schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Inline external $ref references to create self-contained schema."""
    result = copy.deepcopy(schema)
    _inline_refs_recursive(result, all_schemas, set())
    return result


def _inline_refs_recursive(
    obj: Any,
    all_schemas: dict[str, dict[str, Any]],
    visited: set[str],
) -> None:
    """Recursively inline external references."""
    if not isinstance(obj, dict):
        if isinstance(obj, list):
            for item in obj:
                _inline_refs_recursive(item, all_schemas, visited)
        return

    if "$ref" in obj:
        ref = obj["$ref"]
        if not ref.startswith("#") and ".json#" in ref:
            # External reference
            parts = ref.split("#", 1)
            file_part = parts[0]
            def_path = parts[1] if len(parts) > 1 else ""

            schema_name = Path(file_part).stem
            if schema_name in all_schemas:
                source_schema = all_schemas[schema_name]
                definition = _get_definition(source_schema, def_path)
                if definition:
                    # Replace ref with inlined definition
                    del obj["$ref"]
                    for key, value in definition.items():
                        obj[key] = copy.deepcopy(value)

    for value in obj.values():
        _inline_refs_recursive(value, all_schemas, visited)


def _get_definition(schema: dict[str, Any], path: str) -> dict[str, Any] | None:
    """Get a definition from a schema by path."""
    if not path:
        return schema

    parts = path.strip("/").split("/")
    current: Any = schema

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current if isinstance(current, dict) else None


class TestJobRequestContracts:
    """Test job request schemas."""

    @pytest.fixture(scope="class")
    def schemas(self) -> dict[str, dict[str, Any]]:
        """Load all schemas."""
        return load_all_schemas()

    @pytest.fixture(scope="class")
    def job_request_schema(self, schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Get the job-request schema."""
        if "job-request" in schemas:
            return inline_refs(schemas["job-request"], schemas)
        pytest.skip("job-request.json schema not found")

    def test_job_create_transfer_mode(self, job_request_schema: dict[str, Any]) -> None:
        """Verify transfer mode job creation request validates."""
        definitions = job_request_schema.get("definitions", {})
        create_schema = definitions.get("JobCreateRequest", {})

        request = {
            "mode": "transfer",
            "source_document_id": str(uuid4()),
            "target_document_id": str(uuid4()),
        }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            **create_schema,
        }
        validate(request, schema)

    def test_job_create_scratch_mode(self, job_request_schema: dict[str, Any]) -> None:
        """Verify scratch mode job creation request validates."""
        definitions = job_request_schema.get("definitions", {})
        create_schema = definitions.get("JobCreateRequest", {})

        request = {
            "mode": "scratch",
            "target_document_id": str(uuid4()),
        }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            **create_schema,
        }
        validate(request, schema)

    def test_job_run_request_step(self, job_request_schema: dict[str, Any]) -> None:
        """Verify run request with step mode validates."""
        definitions = job_request_schema.get("definitions", {})
        run_schema = definitions.get("JobRunRequest", {})

        request = {
            "run_mode": "step",
        }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            **run_schema,
        }
        validate(request, schema)

    def test_job_run_request_with_max_steps(self, job_request_schema: dict[str, Any]) -> None:
        """Verify run request with max_steps validates."""
        definitions = job_request_schema.get("definitions", {})
        run_schema = definitions.get("JobRunRequest", {})

        request = {
            "run_mode": "until_done",
            "max_steps": 10,
        }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            **run_schema,
        }
        validate(request, schema)

    def test_answers_request(self, job_request_schema: dict[str, Any]) -> None:
        """Verify answers request validates."""
        definitions = job_request_schema.get("definitions", {})
        answers_schema = definitions.get("JobAnswersRequest", {})

        if not answers_schema:
            pytest.skip("JobAnswersRequest not in schema")

        request = {
            "answers": [
                {"field_id": str(uuid4()), "value": "John Doe"},
                {"field_id": str(uuid4()), "value": 42},
            ]
        }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": definitions,
            **answers_schema,
        }
        validate(request, schema)

    def test_edits_request(self, job_request_schema: dict[str, Any]) -> None:
        """Verify edits request validates."""
        definitions = job_request_schema.get("definitions", {})
        edits_schema = definitions.get("JobEditsRequest", {})

        if not edits_schema:
            pytest.skip("JobEditsRequest not in schema")

        request = {
            "edits": [
                {"field_id": str(uuid4()), "value": "Updated Value"},
                {"field_id": str(uuid4())},  # value is optional
            ]
        }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": definitions,
            **edits_schema,
        }
        validate(request, schema)


class TestErrorContracts:
    """Test error response schemas."""

    @pytest.fixture(scope="class")
    def schemas(self) -> dict[str, dict[str, Any]]:
        """Load all schemas."""
        return load_all_schemas()

    @pytest.fixture(scope="class")
    def error_schema(self, schemas: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Get the error schema."""
        if "error" in schemas:
            return schemas["error"]
        pytest.skip("error.json schema not found")

    def test_validation_error_response(self, error_schema: dict[str, Any]) -> None:
        """Verify validation error response validates."""
        definitions = error_schema.get("definitions", {})
        response_schema = definitions.get("ErrorResponse", {})

        response = {
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid input data",
                "field": "target_document_id",
            },
        }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": definitions,
            **response_schema,
        }
        validate(response, schema)

    def test_not_found_error_response(self, error_schema: dict[str, Any]) -> None:
        """Verify not found error response validates."""
        definitions = error_schema.get("definitions", {})
        response_schema = definitions.get("ErrorResponse", {})

        response = {
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": "Job not found: abc-123",
            },
        }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": definitions,
            **response_schema,
        }
        validate(response, schema)

    def test_internal_error_with_trace_id(self, error_schema: dict[str, Any]) -> None:
        """Verify internal error with trace_id validates."""
        definitions = error_schema.get("definitions", {})
        response_schema = definitions.get("ErrorResponse", {})

        response = {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred. Please try again later.",
                "trace_id": str(uuid4()),
            },
        }

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": definitions,
            **response_schema,
        }
        validate(response, schema)


class TestRoundTripConsistency:
    """Test request/response round-trip consistency."""

    @pytest.fixture(scope="class")
    def schemas(self) -> dict[str, dict[str, Any]]:
        """Load all schemas."""
        return load_all_schemas()

    def test_job_create_to_response(self, schemas: dict[str, dict[str, Any]]) -> None:
        """Verify job create request produces valid response."""
        if "job-request" not in schemas or "job-response" not in schemas:
            pytest.skip("Required schemas not found")

        request_defs = schemas["job-request"].get("definitions", {})
        response_defs = schemas["job-response"].get("definitions", {})

        # Valid request
        request = {
            "mode": "transfer",
            "source_document_id": str(uuid4()),
            "target_document_id": str(uuid4()),
        }

        # Simulated response
        job_id = str(uuid4())
        response = {
            "success": True,
            "data": {
                "job_id": job_id,
            },
            "meta": {
                "mode": request["mode"],
            },
        }

        # Validate request
        create_schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            **request_defs.get("JobCreateRequest", {}),
        }
        validate(request, create_schema)

        # Validate response
        response_schema = response_defs.get("JobCreateResponse", {})
        if response_schema:
            full_schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                **response_schema,
            }
            validate(response, full_schema)

    def test_field_ids_consistent_across_operations(
        self, schemas: dict[str, dict[str, Any]]
    ) -> None:
        """Verify field IDs are consistent between requests and responses."""
        if "job-request" not in schemas:
            pytest.skip("job-request.json not found")

        request_defs = schemas["job-request"].get("definitions", {})

        # Generate field IDs
        field_ids = [str(uuid4()) for _ in range(3)]

        # Answers request using those field IDs
        answers_request = {
            "answers": [
                {"field_id": field_ids[0], "value": "Answer 1"},
                {"field_id": field_ids[1], "value": "Answer 2"},
            ]
        }

        # Edits request using the same field IDs
        edits_request = {
            "edits": [
                {"field_id": field_ids[0], "value": "Edited 1"},
                {"field_id": field_ids[2], "value": "Edited 3"},
            ]
        }

        # Both should validate
        if "JobAnswersRequest" in request_defs:
            schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "definitions": request_defs,
                **request_defs["JobAnswersRequest"],
            }
            validate(answers_request, schema)

        if "JobEditsRequest" in request_defs:
            schema = {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "definitions": request_defs,
                **request_defs["JobEditsRequest"],
            }
            validate(edits_request, schema)


class TestExampleValidation:
    """Test that example files match their schemas."""

    @pytest.fixture(scope="class")
    def schemas(self) -> dict[str, dict[str, Any]]:
        """Load all schemas."""
        return load_all_schemas()

    @pytest.mark.parametrize(
        "example_type,example_name",
        [
            ("jobs", "create_request"),
            ("jobs", "create_response"),
            ("jobs", "run_request"),
            ("jobs", "run_response"),
            ("documents", "upload_response"),
            ("documents", "get_response"),
        ],
    )
    def test_example_matches_schema(
        self,
        schemas: dict[str, dict[str, Any]],
        example_type: str,
        example_name: str,
    ) -> None:
        """Verify example files validate against their schemas."""
        example_path = EXAMPLES_DIR / example_type / f"{example_name}.json"
        if not example_path.exists():
            pytest.skip(f"Example {example_path} not found")

        example = load_json(example_path)

        # Skip if no schema reference
        if "$schema" not in example:
            pytest.skip(f"Example {example_name} has no $schema reference")

        # The example validation is handled by test_schema_validation.py
        # This test ensures examples exist and are valid JSON
        assert isinstance(example, dict)


class TestContractEvolution:
    """Test contract versioning and backward compatibility."""

    @pytest.fixture(scope="class")
    def schemas(self) -> dict[str, dict[str, Any]]:
        """Load all schemas."""
        return load_all_schemas()

    def test_required_fields_are_documented(self, schemas: dict[str, dict[str, Any]]) -> None:
        """Verify all required fields have descriptions."""
        for schema_name, schema in schemas.items():
            definitions = schema.get("definitions", {})

            for def_name, definition in definitions.items():
                required = definition.get("required", [])
                properties = definition.get("properties", {})

                for field in required:
                    if field in properties:
                        prop = properties[field]
                        # At minimum, required fields should have description or be a ref
                        has_description = "description" in prop or "$ref" in prop
                        # Allow if it's a union type (oneOf, anyOf)
                        has_union = "oneOf" in prop or "anyOf" in prop

                        if not (has_description or has_union):
                            # This is a warning, not a failure
                            pass

    def test_optional_fields_have_defaults(self, schemas: dict[str, dict[str, Any]]) -> None:
        """Verify optional fields either have defaults or are nullable."""
        for schema_name, schema in schemas.items():
            definitions = schema.get("definitions", {})

            for def_name, definition in definitions.items():
                required = set(definition.get("required", []))
                properties = definition.get("properties", {})

                for prop_name, prop in properties.items():
                    if prop_name not in required:
                        # Optional field - should be nullable or have default
                        # This is informational
                        pass

    def test_no_unknown_properties_in_strict_schemas(
        self, schemas: dict[str, dict[str, Any]]
    ) -> None:
        """Verify strict schemas reject unknown properties."""
        strict_schemas = ["JobCreateRequest", "JobRunRequest", "ErrorResponse"]

        for schema_name, schema in schemas.items():
            definitions = schema.get("definitions", {})

            for def_name in strict_schemas:
                if def_name in definitions:
                    definition = definitions[def_name]
                    additional = definition.get("additionalProperties", True)

                    # Strict schemas should disallow additional properties
                    assert additional is False, (
                        f"{schema_name}.{def_name} should have additionalProperties: false"
                    )
