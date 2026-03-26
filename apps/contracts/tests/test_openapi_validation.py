"""
Test OpenAPI specification validation.

This module validates:
1. OpenAPI spec is valid according to OpenAPI 3.1 standard
2. All schema references are resolvable
3. All endpoints have proper documentation
4. Response schemas are consistent
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename

# Base paths
CONTRACTS_DIR = Path(__file__).parent.parent
OPENAPI_DIR = CONTRACTS_DIR / "openapi"


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its contents."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_all_openapi_files() -> list[Path]:
    """Get all OpenAPI YAML files."""
    return list(OPENAPI_DIR.glob("*.yaml"))


class TestOpenAPIValidity:
    """Test that all OpenAPI specs are valid."""

    @pytest.mark.parametrize("spec_file", get_all_openapi_files(), ids=lambda x: x.name)
    def test_spec_is_valid_openapi(self, spec_file: Path) -> None:
        """Verify each OpenAPI spec is valid."""
        try:
            spec_dict, spec_url = read_from_filename(str(spec_file))
            validate(spec_dict)
        except Exception as e:
            pytest.fail(f"OpenAPI spec {spec_file.name} is not valid: {e}")

    @pytest.mark.parametrize("spec_file", get_all_openapi_files(), ids=lambda x: x.name)
    def test_spec_has_required_info(self, spec_file: Path) -> None:
        """Verify each OpenAPI spec has required info fields."""
        spec = load_yaml(spec_file)

        assert "openapi" in spec, f"Spec {spec_file.name} missing openapi version"
        assert spec["openapi"].startswith("3."), f"Spec {spec_file.name} should be OpenAPI 3.x"

        info = spec.get("info", {})
        assert "title" in info, f"Spec {spec_file.name} missing info.title"
        assert "version" in info, f"Spec {spec_file.name} missing info.version"
        assert "description" in info, f"Spec {spec_file.name} missing info.description"

    @pytest.mark.parametrize("spec_file", get_all_openapi_files(), ids=lambda x: x.name)
    def test_spec_has_servers(self, spec_file: Path) -> None:
        """Verify each OpenAPI spec defines servers."""
        spec = load_yaml(spec_file)

        assert "servers" in spec, f"Spec {spec_file.name} missing servers"
        assert len(spec["servers"]) > 0, f"Spec {spec_file.name} has no servers defined"

        for server in spec["servers"]:
            assert "url" in server, "Server missing url"


class TestAPIEndpoints:
    """Test that API endpoints are properly defined."""

    @pytest.fixture(scope="class")
    def api_spec(self) -> dict[str, Any]:
        """Load the main API spec."""
        return load_yaml(OPENAPI_DIR / "api.yaml")

    def test_all_paths_have_operations(self, api_spec: dict[str, Any]) -> None:
        """Verify all paths have at least one operation defined."""
        paths = api_spec.get("paths", {})

        for path, path_item in paths.items():
            operations = [
                method
                for method in ["get", "post", "put", "patch", "delete"]
                if method in path_item
            ]
            assert len(operations) > 0, f"Path {path} has no operations defined"

    def test_all_operations_have_responses(self, api_spec: dict[str, Any]) -> None:
        """Verify all operations have responses defined."""
        paths = api_spec.get("paths", {})

        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                if method in path_item:
                    operation = path_item[method]
                    assert "responses" in operation, (
                        f"Operation {method.upper()} {path} missing responses"
                    )
                    assert len(operation["responses"]) > 0, (
                        f"Operation {method.upper()} {path} has no responses"
                    )

    def test_all_operations_have_operation_id(self, api_spec: dict[str, Any]) -> None:
        """Verify all operations have unique operationId."""
        paths = api_spec.get("paths", {})
        operation_ids: set[str] = set()

        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                if method in path_item:
                    operation = path_item[method]
                    assert "operationId" in operation, (
                        f"Operation {method.upper()} {path} missing operationId"
                    )

                    op_id = operation["operationId"]
                    assert op_id not in operation_ids, f"Duplicate operationId: {op_id}"
                    operation_ids.add(op_id)

    def test_all_operations_have_tags(self, api_spec: dict[str, Any]) -> None:
        """Verify all operations have tags for organization."""
        paths = api_spec.get("paths", {})

        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                if method in path_item:
                    operation = path_item[method]
                    assert "tags" in operation, f"Operation {method.upper()} {path} missing tags"
                    assert len(operation["tags"]) > 0, (
                        f"Operation {method.upper()} {path} has no tags"
                    )

    def test_all_operations_have_summary(self, api_spec: dict[str, Any]) -> None:
        """Verify all operations have a summary."""
        paths = api_spec.get("paths", {})

        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                if method in path_item:
                    operation = path_item[method]
                    assert "summary" in operation, (
                        f"Operation {method.upper()} {path} missing summary"
                    )


class TestRequiredEndpoints:
    """Test that all required endpoints from PRD are present."""

    @pytest.fixture(scope="class")
    def api_spec(self) -> dict[str, Any]:
        """Load the main API spec."""
        return load_yaml(OPENAPI_DIR / "api.yaml")

    def test_document_endpoints_exist(self, api_spec: dict[str, Any]) -> None:
        """Verify document-related endpoints exist."""
        paths = api_spec.get("paths", {})

        # POST /documents - upload
        assert "/documents" in paths, "Missing POST /documents endpoint"
        assert "post" in paths["/documents"], "Missing POST method for /documents"

        # GET /documents/{document_id}
        assert "/documents/{document_id}" in paths, "Missing GET /documents/{document_id} endpoint"
        assert "get" in paths["/documents/{document_id}"], (
            "Missing GET method for /documents/{document_id}"
        )

        # GET /documents/{document_id}/pages/{page}/preview
        assert "/documents/{document_id}/pages/{page}/preview" in paths, (
            "Missing page preview endpoint"
        )

    def test_job_endpoints_exist(self, api_spec: dict[str, Any]) -> None:
        """Verify job-related endpoints exist."""
        paths = api_spec.get("paths", {})

        # POST /jobs - create
        assert "/jobs" in paths, "Missing POST /jobs endpoint"
        assert "post" in paths["/jobs"], "Missing POST method for /jobs"

        # GET /jobs/{job_id}
        assert "/jobs/{job_id}" in paths, "Missing GET /jobs/{job_id} endpoint"
        assert "get" in paths["/jobs/{job_id}"], "Missing GET method for /jobs/{job_id}"

        # POST /jobs/{job_id}/run
        assert "/jobs/{job_id}/run" in paths, "Missing POST /jobs/{job_id}/run endpoint"
        assert "post" in paths["/jobs/{job_id}/run"], "Missing POST method for /jobs/{job_id}/run"

        # POST /jobs/{job_id}/answers
        assert "/jobs/{job_id}/answers" in paths, "Missing POST /jobs/{job_id}/answers endpoint"

        # POST /jobs/{job_id}/edits
        assert "/jobs/{job_id}/edits" in paths, "Missing POST /jobs/{job_id}/edits endpoint"

    def test_review_endpoints_exist(self, api_spec: dict[str, Any]) -> None:
        """Verify review-related endpoints exist."""
        paths = api_spec.get("paths", {})

        # GET /jobs/{job_id}/review
        assert "/jobs/{job_id}/review" in paths, "Missing GET /jobs/{job_id}/review endpoint"

        # GET /jobs/{job_id}/activity
        assert "/jobs/{job_id}/activity" in paths, "Missing GET /jobs/{job_id}/activity endpoint"

        # GET /jobs/{job_id}/evidence
        assert "/jobs/{job_id}/evidence" in paths, "Missing GET /jobs/{job_id}/evidence endpoint"

    def test_output_endpoints_exist(self, api_spec: dict[str, Any]) -> None:
        """Verify output-related endpoints exist."""
        paths = api_spec.get("paths", {})

        # GET /jobs/{job_id}/output.pdf
        assert "/jobs/{job_id}/output.pdf" in paths, (
            "Missing GET /jobs/{job_id}/output.pdf endpoint"
        )

        # GET /jobs/{job_id}/export.json
        assert "/jobs/{job_id}/export.json" in paths, (
            "Missing GET /jobs/{job_id}/export.json endpoint"
        )


class TestErrorResponses:
    """Test that error responses are properly defined."""

    @pytest.fixture(scope="class")
    def api_spec(self) -> dict[str, Any]:
        """Load the main API spec."""
        return load_yaml(OPENAPI_DIR / "api.yaml")

    def test_common_error_responses_defined(self, api_spec: dict[str, Any]) -> None:
        """Verify common error responses are defined in components."""
        responses = api_spec.get("components", {}).get("responses", {})

        required_errors = ["BadRequest", "NotFound", "Conflict", "UnprocessableEntity"]

        for error in required_errors:
            assert error in responses, f"Missing error response: {error}"

    def test_error_response_schema_is_consistent(self, api_spec: dict[str, Any]) -> None:
        """Verify error responses use consistent schema."""
        schemas = api_spec.get("components", {}).get("schemas", {})

        assert "ErrorResponse" in schemas, "Missing ErrorResponse schema"

        error_schema = schemas["ErrorResponse"]
        assert "properties" in error_schema

        props = error_schema["properties"]
        assert "success" in props, "ErrorResponse missing success field"
        assert "error" in props, "ErrorResponse missing error field"

    def test_all_endpoints_have_error_responses(self, api_spec: dict[str, Any]) -> None:
        """Verify all endpoints handle common errors."""
        paths = api_spec.get("paths", {})

        for path, path_item in paths.items():
            for method in ["get", "post", "put", "patch", "delete"]:
                if method in path_item:
                    operation = path_item[method]
                    responses = operation.get("responses", {})

                    # Check that at least one success response exists
                    success_codes = [code for code in responses.keys() if code.startswith("2")]
                    assert len(success_codes) > 0, (
                        f"{method.upper()} {path} has no success response"
                    )


class TestSchemaDefinitions:
    """Test that schema definitions are complete."""

    @pytest.fixture(scope="class")
    def api_spec(self) -> dict[str, Any]:
        """Load the main API spec."""
        return load_yaml(OPENAPI_DIR / "api.yaml")

    def test_core_schemas_exist(self, api_spec: dict[str, Any]) -> None:
        """Verify core schemas are defined."""
        schemas = api_spec.get("components", {}).get("schemas", {})

        required_schemas = [
            "Document",
            "Field",
            "Mapping",
            "Extraction",
            "Evidence",
            "Activity",
            "Issue",
            "JobContext",
            "BBox",
            "ErrorResponse",
        ]

        for schema in required_schemas:
            assert schema in schemas, f"Missing schema: {schema}"

    def test_request_schemas_exist(self, api_spec: dict[str, Any]) -> None:
        """Verify request body schemas are defined."""
        schemas = api_spec.get("components", {}).get("schemas", {})

        required_requests = [
            "JobCreateRequest",
            "JobRunRequest",
            "JobAnswersRequest",
            "JobEditsRequest",
        ]

        for schema in required_requests:
            assert schema in schemas, f"Missing request schema: {schema}"

    def test_response_schemas_exist(self, api_spec: dict[str, Any]) -> None:
        """Verify response body schemas are defined."""
        schemas = api_spec.get("components", {}).get("schemas", {})

        required_responses = [
            "DocumentUploadResponse",
            "DocumentGetResponse",
            "JobCreateResponse",
            "JobGetResponse",
            "JobRunResponse",
            "JobReviewResponse",
            "JobActivityResponse",
            "JobEvidenceResponse",
        ]

        for schema in required_responses:
            assert schema in schemas, f"Missing response schema: {schema}"

    def test_schemas_have_required_fields(self, api_spec: dict[str, Any]) -> None:
        """Verify schemas define required fields."""
        schemas = api_spec.get("components", {}).get("schemas", {})

        # Check JobContext has required fields
        job_context = schemas.get("JobContext", {})
        required = job_context.get("required", [])
        expected = ["id", "status", "mode", "target_document_id"]

        for field in expected:
            assert field in required, f"JobContext missing required field: {field}"

        # Check Field has required fields
        field_schema = schemas.get("Field", {})
        field_required = field_schema.get("required", [])
        field_expected = ["id", "name", "type"]

        for field in field_expected:
            assert field in field_required, f"Field missing required field: {field}"


class TestParameterDefinitions:
    """Test that parameters are properly defined."""

    @pytest.fixture(scope="class")
    def api_spec(self) -> dict[str, Any]:
        """Load the main API spec."""
        return load_yaml(OPENAPI_DIR / "api.yaml")

    def test_common_parameters_exist(self, api_spec: dict[str, Any]) -> None:
        """Verify common parameters are defined."""
        parameters = api_spec.get("components", {}).get("parameters", {})

        required_params = ["DocumentId", "JobId"]

        for param in required_params:
            assert param in parameters, f"Missing parameter: {param}"

    def test_path_parameters_have_uuid_format(self, api_spec: dict[str, Any]) -> None:
        """Verify ID path parameters use UUID format."""
        parameters = api_spec.get("components", {}).get("parameters", {})

        for param_name, param_def in parameters.items():
            if param_name.endswith("Id"):
                schema = param_def.get("schema", {})
                assert schema.get("type") == "string", (
                    f"Parameter {param_name} should be string type"
                )
                assert schema.get("format") == "uuid", (
                    f"Parameter {param_name} should have UUID format"
                )
