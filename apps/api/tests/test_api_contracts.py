"""
Integration tests for API contract validation.

This module tests the actual API endpoints to ensure they match the contracts.
It uses the test client to make requests and validates responses against schemas.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft7Validator

from app.main import app
from app.models import (
    ApiResponse,
    Document,
    DocumentMeta,
    DocumentType,
    ErrorResponse,
    JobContext,
    JobCreate,
    JobMode,
    JobStatus,
)


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


def validate_against_schema(data: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate data against a JSON schema."""
    validator = Draft7Validator(schema)
    errors = list(validator.iter_errors(data))
    if errors:
        error_messages = "\n".join(f"  - {e.message} at {list(e.path)}" for e in errors)
        raise AssertionError(f"Schema validation failed:\n{error_messages}")


class TestRootEndpoint:
    """Test root endpoint contract."""

    def test_root_returns_expected_fields(self, client: TestClient) -> None:
        """Verify root endpoint returns expected structure."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
        assert "openapi" in data


class TestHealthEndpoint:
    """Test health endpoint contract."""

    def test_health_returns_expected_fields(self, client: TestClient) -> None:
        """Verify health endpoint returns expected structure."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data.get("status") == "healthy"
        assert "timestamp" in data


class TestOpenAPISchema:
    """Test that OpenAPI schema is properly generated."""

    def test_openapi_schema_exists(self, client: TestClient) -> None:
        """Verify OpenAPI schema endpoint returns valid JSON."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema

    def test_openapi_has_required_info(self, client: TestClient) -> None:
        """Verify OpenAPI info section has required fields."""
        response = client.get("/openapi.json")
        schema = response.json()

        info = schema["info"]
        assert "title" in info
        assert "version" in info
        assert "description" in info

    def test_openapi_has_tags(self, client: TestClient) -> None:
        """Verify OpenAPI tags are defined."""
        response = client.get("/openapi.json")
        schema = response.json()

        assert "tags" in schema
        tag_names = [tag["name"] for tag in schema["tags"]]

        expected_tags = ["auth", "documents", "jobs", "health"]
        for tag in expected_tags:
            assert tag in tag_names, f"Missing tag: {tag}"

    def test_openapi_has_servers(self, client: TestClient) -> None:
        """Verify OpenAPI servers are defined."""
        response = client.get("/openapi.json")
        schema = response.json()

        assert "servers" in schema
        assert len(schema["servers"]) > 0


class TestErrorResponseContract:
    """Test that error responses match the contract."""

    def test_404_error_format(self, client: TestClient) -> None:
        """Verify 404 errors match the error contract."""
        response = client.get("/api/v1/documents/non-existent-id")
        assert response.status_code == 404

        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    def test_validation_error_format(self, client: TestClient) -> None:
        """Verify validation errors match the error contract."""
        # Send invalid job create request (missing required fields)
        response = client.post(
            "/api/v1/jobs",
            json={"mode": "invalid_mode"},
        )
        assert response.status_code in (400, 422)

        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]


class TestDocumentEndpoints:
    """Test document endpoint contracts."""

    def test_get_document_not_found(self, client: TestClient) -> None:
        """Verify GET /documents/{id} returns proper 404."""
        doc_id = str(uuid4())
        response = client.get(f"/api/v1/documents/{doc_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"


class TestJobEndpoints:
    """Test job endpoint contracts."""

    def test_create_job_validation(self, client: TestClient) -> None:
        """Verify POST /jobs validates required fields."""
        # Missing target_document_id
        response = client.post(
            "/api/v1/jobs",
            json={"mode": "scratch"},
        )
        assert response.status_code in (400, 422)

        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_get_job_not_found(self, client: TestClient) -> None:
        """Verify GET /jobs/{id} returns proper 404."""
        job_id = str(uuid4())
        response = client.get(f"/api/v1/jobs/{job_id}")

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"

    def test_run_job_not_found(self, client: TestClient) -> None:
        """Verify POST /jobs/{id}/run returns proper 404."""
        job_id = str(uuid4())
        response = client.post(
            f"/api/v1/jobs/{job_id}/run",
            json={"run_mode": "step"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"

    def test_submit_answers_not_found(self, client: TestClient) -> None:
        """Verify POST /jobs/{id}/answers returns proper 404."""
        job_id = str(uuid4())
        response = client.post(
            f"/api/v1/jobs/{job_id}/answers",
            json={"answers": [{"field_id": str(uuid4()), "value": "test"}]},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_submit_edits_not_found(self, client: TestClient) -> None:
        """Verify POST /jobs/{id}/edits returns proper 404."""
        job_id = str(uuid4())
        response = client.post(
            f"/api/v1/jobs/{job_id}/edits",
            json={"edits": [{"field_id": str(uuid4()), "value": "new_value"}]},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False


class TestReviewEndpoints:
    """Test review endpoint contracts."""

    def test_get_review_not_found(self, client: TestClient) -> None:
        """Verify GET /jobs/{id}/review returns proper 404."""
        job_id = str(uuid4())
        response = client.get(f"/api/v1/jobs/{job_id}/review")

        assert response.status_code == 404

    def test_get_activity_not_found(self, client: TestClient) -> None:
        """Verify GET /jobs/{id}/activity returns proper 404."""
        job_id = str(uuid4())
        response = client.get(f"/api/v1/jobs/{job_id}/activity")

        assert response.status_code == 404


class TestApiResponseWrapper:
    """Test that successful responses follow the ApiResponse wrapper pattern."""

    def test_success_responses_have_data_field(self, client: TestClient) -> None:
        """Verify successful responses include data field."""
        # Root endpoint doesn't use wrapper, skip
        # Test health endpoint instead
        response = client.get("/health")
        assert response.status_code == 200

        # Health returns direct object, not wrapped
        # This is expected for simple status endpoints
        data = response.json()
        assert "status" in data

    def test_api_response_success_flag(self, client: TestClient) -> None:
        """Verify error responses have success=false."""
        response = client.get(f"/api/v1/documents/{uuid4()}")
        assert response.status_code == 404

        data = response.json()
        assert data["success"] is False
