"""
Contract tests for API responses.

This module validates:
1. API responses match their declared schemas
2. Request validation works correctly
3. Error response formats are consistent
4. Pydantic models can generate valid JSON schemas

Uses pydantic's model_json_schema() for schema generation and validation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from jsonschema import Draft7Validator, ValidationError

from app.models import (
    Activity,
    ActivityAction,
    ApiResponse,
    BBox,
    ConfidenceSummary,
    Document,
    DocumentMeta,
    DocumentResponse,
    DocumentType,
    ErrorDetail,
    ErrorResponse,
    Evidence,
    EvidenceResponse,
    Extraction,
    FieldAnswer,
    FieldEdit,
    FieldModel,
    FieldType,
    Issue,
    IssueSeverity,
    IssueType,
    JobContext,
    JobCreate,
    JobMode,
    JobResponse,
    JobStatus,
    Mapping,
    PagePreview,
    ReviewResponse,
    RunMode,
    RunRequest,
    RunResponse,
)


def generate_json_schema(model_class: type) -> dict[str, Any]:
    """Generate JSON schema from Pydantic model."""
    return model_class.model_json_schema()


def validate_data_against_schema(data: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate data against a JSON schema."""
    validator = Draft7Validator(schema)
    errors = list(validator.iter_errors(data))
    if errors:
        error_messages = "\n".join(f"  - {e.message} at {list(e.path)}" for e in errors)
        raise AssertionError(f"Schema validation failed:\n{error_messages}")


class TestSchemaGeneration:
    """Test that Pydantic models generate valid JSON schemas."""

    @pytest.mark.parametrize(
        "model_class",
        [
            BBox,
            DocumentMeta,
            Document,
            DocumentResponse,
            FieldModel,
            Mapping,
            FieldAnswer,
            FieldEdit,
            Evidence,
            EvidenceResponse,
            Activity,
            Issue,
            Extraction,
            ConfidenceSummary,
            PagePreview,
            JobCreate,
            JobResponse,
            JobContext,
            RunRequest,
            RunResponse,
            ReviewResponse,
            ErrorDetail,
            ErrorResponse,
        ],
    )
    def test_model_generates_valid_schema(self, model_class: type) -> None:
        """Verify each Pydantic model generates a valid JSON schema."""
        schema = generate_json_schema(model_class)

        # Schema should have a title
        assert "title" in schema, f"{model_class.__name__} schema missing title"

        # Schema should have properties or $defs
        has_structure = "properties" in schema or "$defs" in schema
        assert has_structure, f"{model_class.__name__} schema has no structure"

        # Validate schema is itself valid
        try:
            Draft7Validator.check_schema(schema)
        except Exception as e:
            pytest.fail(f"{model_class.__name__} generated invalid schema: {e}")


class TestJobModels:
    """Test Job-related models and their contracts."""

    def test_job_create_schema(self) -> None:
        """Verify JobCreate schema matches expected format."""
        schema = generate_json_schema(JobCreate)

        # Required fields
        assert "mode" in schema.get("properties", {})
        assert "target_document_id" in schema.get("properties", {})

    def test_job_create_valid_data(self) -> None:
        """Verify valid JobCreate data passes schema validation."""
        job_create = JobCreate(
            mode=JobMode.TRANSFER,
            source_document_id=str(uuid4()),
            target_document_id=str(uuid4()),
        )
        schema = generate_json_schema(JobCreate)
        data = json.loads(job_create.model_dump_json())

        validate_data_against_schema(data, schema)

    def test_job_create_scratch_mode_no_source(self) -> None:
        """Verify scratch mode works without source document."""
        job_create = JobCreate(
            mode=JobMode.SCRATCH,
            target_document_id=str(uuid4()),
        )
        schema = generate_json_schema(JobCreate)
        data = json.loads(job_create.model_dump_json())

        validate_data_against_schema(data, schema)

    def test_job_response_schema(self) -> None:
        """Verify JobResponse schema matches expected format."""
        schema = generate_json_schema(JobResponse)
        assert "job_id" in schema.get("properties", {})

    def test_job_response_valid_data(self) -> None:
        """Verify valid JobResponse data passes schema validation."""
        job_response = JobResponse(job_id=str(uuid4()))
        schema = generate_json_schema(JobResponse)
        data = json.loads(job_response.model_dump_json())

        validate_data_against_schema(data, schema)

    def test_run_request_schema(self) -> None:
        """Verify RunRequest schema matches expected format."""
        schema = generate_json_schema(RunRequest)
        assert "run_mode" in schema.get("properties", {})

    def test_run_request_valid_data(self) -> None:
        """Verify valid RunRequest data passes schema validation."""
        for mode in RunMode:
            run_request = RunRequest(run_mode=mode, max_steps=10)
            schema = generate_json_schema(RunRequest)
            data = json.loads(run_request.model_dump_json())

            validate_data_against_schema(data, schema)


class TestDocumentModels:
    """Test Document-related models and their contracts."""

    def test_document_meta_schema(self) -> None:
        """Verify DocumentMeta schema has required fields."""
        schema = generate_json_schema(DocumentMeta)
        props = schema.get("properties", {})

        required_props = ["page_count", "file_size", "mime_type", "filename"]
        for prop in required_props:
            assert prop in props, f"DocumentMeta missing {prop}"

    def test_document_response_valid_data(self) -> None:
        """Verify valid DocumentResponse data passes schema validation."""
        doc_meta = DocumentMeta(
            page_count=5,
            file_size=1024000,
            mime_type="application/pdf",
            filename="test.pdf",
        )
        doc_response = DocumentResponse(
            document_id=str(uuid4()),
            document_ref="uploads/test.pdf",
            meta=doc_meta,
        )
        schema = generate_json_schema(DocumentResponse)
        data = json.loads(doc_response.model_dump_json())

        validate_data_against_schema(data, schema)


class TestFieldModels:
    """Test Field-related models and their contracts."""

    def test_field_model_schema(self) -> None:
        """Verify FieldModel schema has required fields."""
        schema = generate_json_schema(FieldModel)
        props = schema.get("properties", {})

        required_props = ["id", "name", "field_type", "document_id", "page"]
        for prop in required_props:
            assert prop in props, f"FieldModel missing {prop}"

    def test_field_model_valid_data(self) -> None:
        """Verify valid FieldModel data passes schema validation."""
        field = FieldModel(
            id=str(uuid4()),
            name="First Name",
            field_type=FieldType.TEXT,
            value="John",
            confidence=0.95,
            bbox=BBox(x=100, y=200, width=150, height=20, page=1),
            document_id=str(uuid4()),
            page=1,
            is_required=True,
            is_editable=True,
        )
        schema = generate_json_schema(FieldModel)
        data = json.loads(field.model_dump_json())

        validate_data_against_schema(data, schema)

    def test_mapping_schema(self) -> None:
        """Verify Mapping schema has required fields."""
        schema = generate_json_schema(Mapping)
        props = schema.get("properties", {})

        required_props = ["id", "source_field_id", "target_field_id", "confidence"]
        for prop in required_props:
            assert prop in props, f"Mapping missing {prop}"

    def test_mapping_valid_data(self) -> None:
        """Verify valid Mapping data passes schema validation."""
        mapping = Mapping(
            id=str(uuid4()),
            source_field_id=str(uuid4()),
            target_field_id=str(uuid4()),
            confidence=0.88,
            is_confirmed=False,
        )
        schema = generate_json_schema(Mapping)
        data = json.loads(mapping.model_dump_json())

        validate_data_against_schema(data, schema)


class TestEvidenceModels:
    """Test Evidence-related models and their contracts."""

    def test_evidence_schema(self) -> None:
        """Verify Evidence schema has required fields."""
        schema = generate_json_schema(Evidence)
        props = schema.get("properties", {})

        required_props = ["id", "field_id", "source", "confidence", "document_id"]
        for prop in required_props:
            assert prop in props, f"Evidence missing {prop}"

    def test_evidence_valid_data(self) -> None:
        """Verify valid Evidence data passes schema validation."""
        evidence = Evidence(
            id=str(uuid4()),
            field_id=str(uuid4()),
            source="ocr",
            bbox=BBox(x=50, y=100, width=200, height=30, page=1),
            confidence=0.92,
            text="Extracted text value",
            document_id=str(uuid4()),
        )
        schema = generate_json_schema(Evidence)
        data = json.loads(evidence.model_dump_json())

        validate_data_against_schema(data, schema)


class TestActivityModels:
    """Test Activity-related models and their contracts."""

    def test_activity_schema(self) -> None:
        """Verify Activity schema has required fields."""
        schema = generate_json_schema(Activity)
        props = schema.get("properties", {})

        required_props = ["id", "timestamp", "action"]
        for prop in required_props:
            assert prop in props, f"Activity missing {prop}"

    def test_activity_valid_data(self) -> None:
        """Verify valid Activity data passes schema validation."""
        activity = Activity(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            action=ActivityAction.JOB_CREATED,
            details={"mode": "transfer"},
            field_id=None,
        )
        schema = generate_json_schema(Activity)
        data = json.loads(activity.model_dump_json())

        validate_data_against_schema(data, schema)


class TestIssueModels:
    """Test Issue-related models and their contracts."""

    def test_issue_schema(self) -> None:
        """Verify Issue schema has required fields."""
        schema = generate_json_schema(Issue)
        props = schema.get("properties", {})

        required_props = ["id", "field_id", "issue_type", "message", "severity"]
        for prop in required_props:
            assert prop in props, f"Issue missing {prop}"

    def test_issue_valid_data(self) -> None:
        """Verify valid Issue data passes schema validation."""
        issue = Issue(
            id=str(uuid4()),
            field_id=str(uuid4()),
            issue_type=IssueType.LOW_CONFIDENCE,
            message="Extraction confidence below threshold",
            severity=IssueSeverity.WARNING,
            suggested_action="Review and confirm value",
        )
        schema = generate_json_schema(Issue)
        data = json.loads(issue.model_dump_json())

        validate_data_against_schema(data, schema)


class TestErrorResponse:
    """Test error response format contracts."""

    def test_error_response_schema(self) -> None:
        """Verify ErrorResponse schema has required fields."""
        schema = generate_json_schema(ErrorResponse)
        props = schema.get("properties", {})

        assert "success" in props
        assert "error" in props

    def test_error_response_valid_data(self) -> None:
        """Verify valid ErrorResponse data passes schema validation."""
        error_response = ErrorResponse(
            success=False,
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Invalid input data",
                field="document_id",
            ),
        )
        schema = generate_json_schema(ErrorResponse)
        data = json.loads(error_response.model_dump_json())

        validate_data_against_schema(data, schema)

    def test_error_response_with_trace_id(self) -> None:
        """Verify ErrorResponse with trace_id passes validation."""
        error_response = ErrorResponse(
            success=False,
            error=ErrorDetail(
                code="INTERNAL_ERROR",
                message="An internal error occurred",
                trace_id=str(uuid4()),
            ),
        )
        schema = generate_json_schema(ErrorResponse)
        data = json.loads(error_response.model_dump_json())

        validate_data_against_schema(data, schema)


class TestApiResponseWrapper:
    """Test ApiResponse wrapper format contracts."""

    def test_api_response_schema(self) -> None:
        """Verify ApiResponse schema has required structure."""
        schema = generate_json_schema(ApiResponse)
        props = schema.get("properties", {})

        assert "success" in props
        assert "data" in props

    def test_api_response_with_job_response(self) -> None:
        """Verify ApiResponse wrapping JobResponse."""
        job_response = JobResponse(job_id=str(uuid4()))
        api_response = ApiResponse(
            success=True,
            data=job_response,
            meta={"mode": "transfer"},
        )

        # Convert to dict and verify structure
        data = json.loads(api_response.model_dump_json())

        assert data["success"] is True
        assert "data" in data
        assert "job_id" in data["data"]


class TestReviewResponse:
    """Test ReviewResponse format contracts."""

    def test_review_response_schema(self) -> None:
        """Verify ReviewResponse schema has required fields."""
        schema = generate_json_schema(ReviewResponse)
        props = schema.get("properties", {})

        required_props = ["issues", "previews", "fields", "confidence_summary"]
        for prop in required_props:
            assert prop in props, f"ReviewResponse missing {prop}"

    def test_review_response_valid_data(self) -> None:
        """Verify valid ReviewResponse data passes schema validation."""
        doc_id = str(uuid4())
        review = ReviewResponse(
            issues=[
                Issue(
                    id=str(uuid4()),
                    field_id=str(uuid4()),
                    issue_type=IssueType.LOW_CONFIDENCE,
                    message="Low confidence extraction",
                    severity=IssueSeverity.WARNING,
                )
            ],
            previews=[
                PagePreview(
                    page=1,
                    document_id=doc_id,
                    url=f"/api/v1/documents/{doc_id}/pages/1/preview",
                    annotations=[],
                )
            ],
            fields=[
                FieldModel(
                    id=str(uuid4()),
                    name="Test Field",
                    field_type=FieldType.TEXT,
                    value="Test Value",
                    document_id=doc_id,
                    page=1,
                )
            ],
            confidence_summary=ConfidenceSummary(
                total_fields=1,
                high_confidence=0,
                medium_confidence=1,
                low_confidence=0,
                no_value=0,
                average_confidence=0.75,
            ),
        )
        schema = generate_json_schema(ReviewResponse)
        data = json.loads(review.model_dump_json())

        validate_data_against_schema(data, schema)


class TestJobContextContract:
    """Test full JobContext contract."""

    def _create_test_document(self, doc_type: DocumentType) -> Document:
        """Create a test document."""
        return Document(
            id=str(uuid4()),
            ref="uploads/test.pdf",
            document_type=doc_type,
            meta=DocumentMeta(
                page_count=3,
                file_size=500000,
                mime_type="application/pdf",
                filename="test.pdf",
            ),
            created_at=datetime.now(timezone.utc),
        )

    def test_job_context_schema(self) -> None:
        """Verify JobContext schema has required fields."""
        schema = generate_json_schema(JobContext)
        props = schema.get("properties", {})

        required_props = [
            "id",
            "mode",
            "status",
            "target_document",
            "fields",
            "mappings",
            "extractions",
            "created_at",
            "updated_at",
        ]
        for prop in required_props:
            assert prop in props, f"JobContext missing {prop}"

    def test_job_context_transfer_mode(self) -> None:
        """Verify JobContext for transfer mode passes validation."""
        source_doc = self._create_test_document(DocumentType.SOURCE)
        target_doc = self._create_test_document(DocumentType.TARGET)

        job_context = JobContext(
            id=str(uuid4()),
            mode=JobMode.TRANSFER,
            status=JobStatus.CREATED,
            source_document=source_doc,
            target_document=target_doc,
            fields=[],
            mappings=[],
            extractions=[],
            evidence=[],
            issues=[],
            activities=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            progress=0.0,
            current_step=None,
            current_stage=None,
            next_actions=[],
            iteration_count=0,
        )
        schema = generate_json_schema(JobContext)
        data = json.loads(job_context.model_dump_json())

        validate_data_against_schema(data, schema)

    def test_job_context_scratch_mode(self) -> None:
        """Verify JobContext for scratch mode passes validation."""
        target_doc = self._create_test_document(DocumentType.TARGET)

        job_context = JobContext(
            id=str(uuid4()),
            mode=JobMode.SCRATCH,
            status=JobStatus.RUNNING,
            source_document=None,
            target_document=target_doc,
            fields=[],
            mappings=[],
            extractions=[],
            evidence=[],
            issues=[],
            activities=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            progress=0.5,
            current_step="extracting",
            current_stage="ingest",
            next_actions=["continue", "pause"],
            iteration_count=1,
        )
        schema = generate_json_schema(JobContext)
        data = json.loads(job_context.model_dump_json())

        validate_data_against_schema(data, schema)


class TestRunResponseContract:
    """Test RunResponse contract."""

    def _create_test_document(self) -> Document:
        """Create a test document."""
        return Document(
            id=str(uuid4()),
            ref="uploads/test.pdf",
            document_type=DocumentType.TARGET,
            meta=DocumentMeta(
                page_count=1,
                file_size=100000,
                mime_type="application/pdf",
                filename="test.pdf",
            ),
            created_at=datetime.now(timezone.utc),
        )

    def test_run_response_schema(self) -> None:
        """Verify RunResponse schema has required fields."""
        schema = generate_json_schema(RunResponse)
        props = schema.get("properties", {})

        required_props = ["status", "job_context"]
        for prop in required_props:
            assert prop in props, f"RunResponse missing {prop}"

    def test_run_response_valid_data(self) -> None:
        """Verify valid RunResponse data passes validation."""
        target_doc = self._create_test_document()
        job_context = JobContext(
            id=str(uuid4()),
            mode=JobMode.SCRATCH,
            status=JobStatus.DONE,
            source_document=None,
            target_document=target_doc,
            fields=[],
            mappings=[],
            extractions=[],
            evidence=[],
            issues=[],
            activities=[],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            progress=1.0,
            current_step=None,
            current_stage=None,
            next_actions=[],
            iteration_count=0,
        )

        run_response = RunResponse(
            status=JobStatus.DONE,
            job_context=job_context,
            next_actions=["download_pdf", "export_json"],
        )
        schema = generate_json_schema(RunResponse)
        data = json.loads(run_response.model_dump_json())

        validate_data_against_schema(data, schema)


class TestFieldAnswerAndEditContracts:
    """Test FieldAnswer and FieldEdit contracts."""

    def test_field_answer_valid_data(self) -> None:
        """Verify valid FieldAnswer data passes validation."""
        answer = FieldAnswer(field_id=str(uuid4()), value="John Doe")
        schema = generate_json_schema(FieldAnswer)
        data = json.loads(answer.model_dump_json())

        validate_data_against_schema(data, schema)

    def test_field_edit_with_all_fields(self) -> None:
        """Verify FieldEdit with all fields passes validation."""
        edit = FieldEdit(
            field_id=str(uuid4()),
            value="Updated Value",
            bbox=BBox(x=100, y=200, width=150, height=25, page=1),
            render_params={"font_size": 12, "bold": True},
        )
        schema = generate_json_schema(FieldEdit)
        data = json.loads(edit.model_dump_json())

        validate_data_against_schema(data, schema)

    def test_field_edit_minimal(self) -> None:
        """Verify minimal FieldEdit passes validation."""
        edit = FieldEdit(field_id=str(uuid4()))
        schema = generate_json_schema(FieldEdit)
        data = json.loads(edit.model_dump_json())

        validate_data_against_schema(data, schema)
