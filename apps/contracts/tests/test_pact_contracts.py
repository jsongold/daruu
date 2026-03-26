"""
Pact-style consumer contract tests.

This module defines expected API interactions from the consumer (frontend)
perspective and validates that the provider (backend) meets these expectations.

These tests document the exact shape of API interactions the frontend relies on.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest


class Interaction:
    """Represents an expected API interaction."""

    def __init__(
        self,
        description: str,
        given: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ):
        self.description = description
        self.given = given
        self.request = request
        self.response = response

    def __repr__(self) -> str:
        return f"Interaction({self.description})"


class ContractMatcher:
    """Matcher for flexible contract validation."""

    @staticmethod
    def like(example: Any) -> dict[str, Any]:
        """Match any value of the same type."""
        return {"pact:matcher:type": "type", "value": example}

    @staticmethod
    def each_like(example: Any, min_count: int = 1) -> dict[str, Any]:
        """Match an array where each element is like the example."""
        return {
            "pact:matcher:type": "type",
            "value": [example] * min_count,
            "min": min_count,
        }

    @staticmethod
    def regex(pattern: str, example: str) -> dict[str, Any]:
        """Match a value by regex pattern."""
        return {
            "pact:matcher:type": "regex",
            "regex": pattern,
            "value": example,
        }

    @staticmethod
    def uuid() -> dict[str, Any]:
        """Match a UUID string."""
        return ContractMatcher.regex(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            str(uuid4()),
        )

    @staticmethod
    def iso_datetime() -> dict[str, Any]:
        """Match an ISO 8601 datetime string."""
        return ContractMatcher.regex(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
            datetime.now(timezone.utc).isoformat(),
        )


def strip_matchers(obj: Any) -> Any:
    """Remove Pact matchers and return just the example values."""
    if isinstance(obj, dict):
        if "pact:matcher:type" in obj:
            return strip_matchers(obj.get("value"))
        return {k: strip_matchers(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_matchers(item) for item in obj]
    return obj


class TestDocumentInteractions:
    """Consumer expectations for document endpoints."""

    @pytest.fixture
    def document_id(self) -> str:
        return str(uuid4())

    def test_upload_document_interaction(self, document_id: str) -> None:
        """Consumer expects document upload to return document with metadata."""
        interaction = Interaction(
            description="a request to upload a document",
            given="the API is available",
            request={
                "method": "POST",
                "path": "/api/v1/documents",
                "headers": {
                    "Content-Type": "multipart/form-data",
                },
                "body": {
                    "file": "(binary data)",
                    "role": "source",
                },
            },
            response={
                "status": 201,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": {
                    "success": True,
                    "data": {
                        "document_id": ContractMatcher.uuid(),
                        "document_ref": ContractMatcher.like("uploads/test.pdf"),
                        "meta": {
                            "page_count": ContractMatcher.like(1),
                            "file_size": ContractMatcher.like(1024),
                            "mime_type": ContractMatcher.like("application/pdf"),
                            "filename": ContractMatcher.like("test.pdf"),
                        },
                    },
                },
            },
        )

        # Validate the response structure
        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True
        assert "data" in response_body
        assert "document_id" in response_body["data"]
        assert "meta" in response_body["data"]

    def test_get_document_interaction(self, document_id: str) -> None:
        """Consumer expects to retrieve document by ID."""
        interaction = Interaction(
            description="a request to get a document",
            given=f"document {document_id} exists",
            request={
                "method": "GET",
                "path": f"/api/v1/documents/{document_id}",
            },
            response={
                "status": 200,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": {
                    "success": True,
                    "data": {
                        "id": ContractMatcher.uuid(),
                        "ref": ContractMatcher.like("uploads/test.pdf"),
                        "document_type": ContractMatcher.regex("^(source|target)$", "source"),
                        "meta": {
                            "page_count": ContractMatcher.like(1),
                            "file_size": ContractMatcher.like(1024),
                            "mime_type": ContractMatcher.like("application/pdf"),
                            "filename": ContractMatcher.like("test.pdf"),
                        },
                        "created_at": ContractMatcher.iso_datetime(),
                    },
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True
        assert "data" in response_body
        assert "id" in response_body["data"]


class TestJobInteractions:
    """Consumer expectations for job endpoints."""

    @pytest.fixture
    def job_id(self) -> str:
        return str(uuid4())

    @pytest.fixture
    def document_ids(self) -> tuple[str, str]:
        return str(uuid4()), str(uuid4())

    def test_create_transfer_job_interaction(self, document_ids: tuple[str, str]) -> None:
        """Consumer expects to create a transfer mode job."""
        source_id, target_id = document_ids

        interaction = Interaction(
            description="a request to create a transfer job",
            given=f"documents {source_id} and {target_id} exist",
            request={
                "method": "POST",
                "path": "/api/v1/jobs",
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": {
                    "mode": "transfer",
                    "source_document_id": source_id,
                    "target_document_id": target_id,
                },
            },
            response={
                "status": 201,
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": {
                    "success": True,
                    "data": {
                        "job_id": ContractMatcher.uuid(),
                    },
                    "meta": {
                        "mode": "transfer",
                    },
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True
        assert "job_id" in response_body["data"]
        assert response_body["meta"]["mode"] == "transfer"

    def test_create_scratch_job_interaction(self, document_ids: tuple[str, str]) -> None:
        """Consumer expects to create a scratch mode job."""
        _, target_id = document_ids

        interaction = Interaction(
            description="a request to create a scratch job",
            given=f"document {target_id} exists",
            request={
                "method": "POST",
                "path": "/api/v1/jobs",
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": {
                    "mode": "scratch",
                    "target_document_id": target_id,
                },
            },
            response={
                "status": 201,
                "body": {
                    "success": True,
                    "data": {
                        "job_id": ContractMatcher.uuid(),
                    },
                    "meta": {
                        "mode": "scratch",
                    },
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True
        assert response_body["meta"]["mode"] == "scratch"

    def test_get_job_context_interaction(self, job_id: str) -> None:
        """Consumer expects to retrieve full job context."""
        interaction = Interaction(
            description="a request to get job context",
            given=f"job {job_id} exists",
            request={
                "method": "GET",
                "path": f"/api/v1/jobs/{job_id}",
            },
            response={
                "status": 200,
                "body": {
                    "success": True,
                    "data": {
                        "id": ContractMatcher.uuid(),
                        "mode": ContractMatcher.regex("^(transfer|scratch)$", "transfer"),
                        "status": ContractMatcher.regex(
                            "^(created|running|blocked|awaiting_input|done|failed)$",
                            "created",
                        ),
                        "target_document": ContractMatcher.like({}),
                        "fields": ContractMatcher.each_like({}, min_count=0),
                        "mappings": ContractMatcher.each_like({}, min_count=0),
                        "extractions": ContractMatcher.each_like({}, min_count=0),
                        "issues": ContractMatcher.each_like({}, min_count=0),
                        "activities": ContractMatcher.each_like({}, min_count=0),
                        "created_at": ContractMatcher.iso_datetime(),
                        "updated_at": ContractMatcher.iso_datetime(),
                        "progress": ContractMatcher.like(0.0),
                    },
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True
        assert "id" in response_body["data"]
        assert "status" in response_body["data"]

    def test_run_job_interaction(self, job_id: str) -> None:
        """Consumer expects to run a job and receive updated context."""
        interaction = Interaction(
            description="a request to run a job",
            given=f"job {job_id} exists and is in created state",
            request={
                "method": "POST",
                "path": f"/api/v1/jobs/{job_id}/run",
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": {
                    "run_mode": "step",
                },
            },
            response={
                "status": 200,
                "body": {
                    "success": True,
                    "data": {
                        "status": ContractMatcher.regex(
                            "^(created|running|blocked|awaiting_input|done|failed)$",
                            "running",
                        ),
                        "job_context": ContractMatcher.like({}),
                        "next_actions": ContractMatcher.each_like("", min_count=0),
                    },
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True
        assert "status" in response_body["data"]
        assert "job_context" in response_body["data"]

    def test_submit_answers_interaction(self, job_id: str) -> None:
        """Consumer expects to submit answers for blocked fields."""
        field_id = str(uuid4())

        interaction = Interaction(
            description="a request to submit answers",
            given=f"job {job_id} is blocked waiting for input",
            request={
                "method": "POST",
                "path": f"/api/v1/jobs/{job_id}/answers",
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": {
                    "answers": [
                        {
                            "field_id": field_id,
                            "value": "John Doe",
                        }
                    ],
                },
            },
            response={
                "status": 200,
                "body": {
                    "success": True,
                    "data": ContractMatcher.like({}),
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True

    def test_submit_edits_interaction(self, job_id: str) -> None:
        """Consumer expects to submit manual edits."""
        field_id = str(uuid4())

        interaction = Interaction(
            description="a request to submit edits",
            given=f"job {job_id} has fields to edit",
            request={
                "method": "POST",
                "path": f"/api/v1/jobs/{job_id}/edits",
                "headers": {
                    "Content-Type": "application/json",
                },
                "body": {
                    "edits": [
                        {
                            "field_id": field_id,
                            "value": "Corrected Value",
                            "bbox": {
                                "x": 100,
                                "y": 200,
                                "width": 150,
                                "height": 25,
                                "page": 1,
                            },
                        }
                    ],
                },
            },
            response={
                "status": 200,
                "body": {
                    "success": True,
                    "data": ContractMatcher.like({}),
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True


class TestReviewInteractions:
    """Consumer expectations for review endpoints."""

    @pytest.fixture
    def job_id(self) -> str:
        return str(uuid4())

    def test_get_review_interaction(self, job_id: str) -> None:
        """Consumer expects to retrieve review data."""
        interaction = Interaction(
            description="a request to get review data",
            given=f"job {job_id} exists",
            request={
                "method": "GET",
                "path": f"/api/v1/jobs/{job_id}/review",
            },
            response={
                "status": 200,
                "body": {
                    "success": True,
                    "data": {
                        "issues": ContractMatcher.each_like({}, min_count=0),
                        "fields": ContractMatcher.each_like({}, min_count=0),
                        "confidence_summary": {
                            "total_fields": ContractMatcher.like(0),
                            "high_confidence": ContractMatcher.like(0),
                            "medium_confidence": ContractMatcher.like(0),
                            "low_confidence": ContractMatcher.like(0),
                            "no_value": ContractMatcher.like(0),
                            "average_confidence": ContractMatcher.like(0.0),
                        },
                        "previews": ContractMatcher.each_like({}, min_count=0),
                    },
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True
        assert "issues" in response_body["data"]
        assert "fields" in response_body["data"]
        assert "confidence_summary" in response_body["data"]

    def test_get_activity_interaction(self, job_id: str) -> None:
        """Consumer expects to retrieve activity log."""
        interaction = Interaction(
            description="a request to get activity log",
            given=f"job {job_id} exists",
            request={
                "method": "GET",
                "path": f"/api/v1/jobs/{job_id}/activity",
            },
            response={
                "status": 200,
                "body": {
                    "success": True,
                    "data": ContractMatcher.each_like(
                        {
                            "id": ContractMatcher.uuid(),
                            "timestamp": ContractMatcher.iso_datetime(),
                            "action": ContractMatcher.like("job_created"),
                            "details": ContractMatcher.like({}),
                        },
                        min_count=0,
                    ),
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True

    def test_get_evidence_interaction(self, job_id: str) -> None:
        """Consumer expects to retrieve evidence for a field."""
        field_id = str(uuid4())

        interaction = Interaction(
            description="a request to get field evidence",
            given=f"job {job_id} has evidence for field {field_id}",
            request={
                "method": "GET",
                "path": f"/api/v1/jobs/{job_id}/evidence",
                "query": {
                    "field_id": field_id,
                },
            },
            response={
                "status": 200,
                "body": {
                    "success": True,
                    "data": {
                        "field_id": field_id,
                        "evidence": ContractMatcher.each_like({}, min_count=0),
                    },
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is True
        assert "evidence" in response_body["data"]


class TestErrorInteractions:
    """Consumer expectations for error responses."""

    def test_not_found_error(self) -> None:
        """Consumer expects consistent 404 error format."""
        job_id = str(uuid4())

        interaction = Interaction(
            description="a request for non-existent job",
            given=f"job {job_id} does not exist",
            request={
                "method": "GET",
                "path": f"/api/v1/jobs/{job_id}",
            },
            response={
                "status": 404,
                "body": {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": ContractMatcher.like("Job not found"),
                    },
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is False
        assert response_body["error"]["code"] == "NOT_FOUND"

    def test_validation_error(self) -> None:
        """Consumer expects consistent validation error format."""
        interaction = Interaction(
            description="a request with invalid data",
            given="invalid request body",
            request={
                "method": "POST",
                "path": "/api/v1/jobs",
                "body": {
                    "mode": "invalid",
                },
            },
            response={
                "status": 400,
                "body": {
                    "success": False,
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": ContractMatcher.like("Invalid input"),
                        "field": ContractMatcher.like("mode"),
                    },
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is False
        assert response_body["error"]["code"] == "VALIDATION_ERROR"

    def test_conflict_error(self) -> None:
        """Consumer expects consistent conflict error format."""
        job_id = str(uuid4())

        interaction = Interaction(
            description="a request to run already-running job",
            given=f"job {job_id} is already running",
            request={
                "method": "POST",
                "path": f"/api/v1/jobs/{job_id}/run",
                "body": {
                    "run_mode": "step",
                },
            },
            response={
                "status": 409,
                "body": {
                    "success": False,
                    "error": {
                        "code": "CONFLICT",
                        "message": ContractMatcher.like("Job is already running"),
                    },
                },
            },
        )

        response_body = strip_matchers(interaction.response["body"])
        assert response_body["success"] is False
        assert response_body["error"]["code"] == "CONFLICT"
