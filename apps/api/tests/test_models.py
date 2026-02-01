"""Tests for Pydantic models."""

import pytest
from pydantic import ValidationError

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
    PaginationMeta,
    ReviewResponse,
    RunMode,
    RunRequest,
    RunResponse,
)


class TestBBox:
    """Tests for BBox model."""

    def test_valid_bbox(self) -> None:
        """Test creating a valid BBox."""
        bbox = BBox(x=10.0, y=20.0, width=100.0, height=50.0, page=1)
        assert bbox.x == 10.0
        assert bbox.y == 20.0
        assert bbox.width == 100.0
        assert bbox.height == 50.0
        assert bbox.page == 1

    def test_bbox_negative_width_fails(self) -> None:
        """Test that negative width is rejected."""
        with pytest.raises(ValidationError):
            BBox(x=10.0, y=20.0, width=-100.0, height=50.0, page=1)

    def test_bbox_negative_height_fails(self) -> None:
        """Test that negative height is rejected."""
        with pytest.raises(ValidationError):
            BBox(x=10.0, y=20.0, width=100.0, height=-50.0, page=1)

    def test_bbox_zero_page_fails(self) -> None:
        """Test that page 0 is rejected (1-indexed)."""
        with pytest.raises(ValidationError):
            BBox(x=10.0, y=20.0, width=100.0, height=50.0, page=0)

    def test_bbox_is_frozen(self) -> None:
        """Test that BBox is immutable."""
        bbox = BBox(x=10.0, y=20.0, width=100.0, height=50.0, page=1)
        with pytest.raises(ValidationError):
            bbox.x = 20.0  # type: ignore


class TestDocumentMeta:
    """Tests for DocumentMeta model."""

    def test_valid_document_meta(self) -> None:
        """Test creating valid DocumentMeta."""
        meta = DocumentMeta(
            page_count=10,
            file_size=1024,
            mime_type="application/pdf",
            filename="test.pdf",
        )
        assert meta.page_count == 10
        assert meta.file_size == 1024
        assert meta.mime_type == "application/pdf"
        assert meta.filename == "test.pdf"
        assert meta.has_password is False

    def test_document_meta_zero_pages_fails(self) -> None:
        """Test that zero pages is rejected."""
        with pytest.raises(ValidationError):
            DocumentMeta(
                page_count=0,
                file_size=1024,
                mime_type="application/pdf",
                filename="test.pdf",
            )

    def test_document_meta_negative_size_fails(self) -> None:
        """Test that negative file size is rejected."""
        with pytest.raises(ValidationError):
            DocumentMeta(
                page_count=1,
                file_size=-1,
                mime_type="application/pdf",
                filename="test.pdf",
            )


class TestFieldModel:
    """Tests for FieldModel."""

    def test_valid_field(self) -> None:
        """Test creating a valid field."""
        field = FieldModel(
            id="field-1",
            name="Name",
            field_type=FieldType.TEXT,
            document_id="doc-1",
            page=1,
        )
        assert field.id == "field-1"
        assert field.name == "Name"
        assert field.field_type == FieldType.TEXT
        assert field.value is None
        assert field.confidence is None
        assert field.is_required is False
        assert field.is_editable is True

    def test_field_with_value_and_confidence(self) -> None:
        """Test field with extracted value."""
        field = FieldModel(
            id="field-1",
            name="Name",
            field_type=FieldType.TEXT,
            value="John Doe",
            confidence=0.95,
            document_id="doc-1",
            page=1,
        )
        assert field.value == "John Doe"
        assert field.confidence == 0.95

    def test_field_confidence_out_of_range_fails(self) -> None:
        """Test that confidence > 1.0 is rejected."""
        with pytest.raises(ValidationError):
            FieldModel(
                id="field-1",
                name="Name",
                confidence=1.5,
                document_id="doc-1",
                page=1,
            )


class TestMapping:
    """Tests for Mapping model."""

    def test_valid_mapping(self) -> None:
        """Test creating a valid mapping."""
        mapping = Mapping(
            id="map-1",
            source_field_id="src-1",
            target_field_id="tgt-1",
            confidence=0.85,
        )
        assert mapping.id == "map-1"
        assert mapping.source_field_id == "src-1"
        assert mapping.target_field_id == "tgt-1"
        assert mapping.confidence == 0.85
        assert mapping.is_confirmed is False


class TestEvidence:
    """Tests for Evidence model."""

    def test_valid_evidence(self) -> None:
        """Test creating valid evidence."""
        evidence = Evidence(
            id="ev-1",
            field_id="field-1",
            source="ocr",
            confidence=0.9,
            document_id="doc-1",
        )
        assert evidence.id == "ev-1"
        assert evidence.source == "ocr"
        assert evidence.confidence == 0.9


class TestExtraction:
    """Tests for Extraction model."""

    def test_valid_extraction(self) -> None:
        """Test creating valid extraction."""
        extraction = Extraction(
            id="ext-1",
            field_id="field-1",
            value="Sample Value",
            confidence=0.8,
        )
        assert extraction.id == "ext-1"
        assert extraction.value == "Sample Value"
        assert extraction.confidence == 0.8
        assert extraction.evidence_ids == []


class TestIssue:
    """Tests for Issue model."""

    def test_valid_issue(self) -> None:
        """Test creating valid issue."""
        issue = Issue(
            id="issue-1",
            field_id="field-1",
            issue_type=IssueType.LOW_CONFIDENCE,
            message="Low confidence detected",
            severity=IssueSeverity.WARNING,
        )
        assert issue.id == "issue-1"
        assert issue.issue_type == IssueType.LOW_CONFIDENCE
        assert issue.severity == IssueSeverity.WARNING


class TestActivity:
    """Tests for Activity model."""

    def test_valid_activity(self) -> None:
        """Test creating valid activity."""
        from datetime import datetime

        activity = Activity(
            id="act-1",
            timestamp=datetime.utcnow(),
            action=ActivityAction.JOB_CREATED,
            details={"mode": "transfer"},
        )
        assert activity.id == "act-1"
        assert activity.action == ActivityAction.JOB_CREATED


class TestJobCreate:
    """Tests for JobCreate request model."""

    def test_transfer_mode(self) -> None:
        """Test creating transfer mode job request."""
        request = JobCreate(
            mode=JobMode.TRANSFER,
            source_document_id="src-doc",
            target_document_id="tgt-doc",
        )
        assert request.mode == JobMode.TRANSFER
        assert request.source_document_id == "src-doc"
        assert request.target_document_id == "tgt-doc"

    def test_scratch_mode(self) -> None:
        """Test creating scratch mode job request."""
        request = JobCreate(
            mode=JobMode.SCRATCH,
            target_document_id="tgt-doc",
        )
        assert request.mode == JobMode.SCRATCH
        assert request.source_document_id is None


class TestRunRequest:
    """Tests for RunRequest model."""

    def test_step_mode(self) -> None:
        """Test step run mode."""
        request = RunRequest(run_mode=RunMode.STEP)
        assert request.run_mode == RunMode.STEP
        assert request.max_steps is None

    def test_with_max_steps(self) -> None:
        """Test run request with max steps."""
        request = RunRequest(run_mode=RunMode.UNTIL_DONE, max_steps=10)
        assert request.max_steps == 10

    def test_invalid_max_steps_fails(self) -> None:
        """Test that max_steps < 1 is rejected."""
        with pytest.raises(ValidationError):
            RunRequest(run_mode=RunMode.STEP, max_steps=0)


class TestApiResponse:
    """Tests for ApiResponse wrapper."""

    def test_success_response(self) -> None:
        """Test successful API response."""
        response = ApiResponse[str](success=True, data="result")
        assert response.success is True
        assert response.data == "result"
        assert response.error is None

    def test_error_response(self) -> None:
        """Test error API response."""
        response = ApiResponse[str](success=False, error="Something went wrong")
        assert response.success is False
        assert response.data is None
        assert response.error == "Something went wrong"


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response(self) -> None:
        """Test creating error response."""
        error = ErrorDetail(
            code="NOT_FOUND",
            message="Resource not found",
        )
        response = ErrorResponse(error=error)
        assert response.success is False
        assert response.error.code == "NOT_FOUND"

    def test_error_with_trace_id(self) -> None:
        """Test error with trace ID for 500 errors."""
        error = ErrorDetail(
            code="INTERNAL_ERROR",
            message="An error occurred",
            trace_id="trace-123",
        )
        assert error.trace_id == "trace-123"


class TestConfidenceSummary:
    """Tests for ConfidenceSummary model."""

    def test_valid_summary(self) -> None:
        """Test creating valid confidence summary."""
        summary = ConfidenceSummary(
            total_fields=10,
            high_confidence=5,
            medium_confidence=3,
            low_confidence=1,
            no_value=1,
            average_confidence=0.75,
        )
        assert summary.total_fields == 10
        assert summary.average_confidence == 0.75


class TestFieldAnswer:
    """Tests for FieldAnswer model."""

    def test_valid_answer(self) -> None:
        """Test creating valid field answer."""
        answer = FieldAnswer(field_id="field-1", value="John Doe")
        assert answer.field_id == "field-1"
        assert answer.value == "John Doe"


class TestFieldEdit:
    """Tests for FieldEdit model."""

    def test_edit_value_only(self) -> None:
        """Test editing field value only."""
        edit = FieldEdit(field_id="field-1", value="New Value")
        assert edit.field_id == "field-1"
        assert edit.value == "New Value"
        assert edit.bbox is None

    def test_edit_with_bbox(self) -> None:
        """Test editing field with bbox."""
        bbox = BBox(x=10.0, y=20.0, width=100.0, height=50.0, page=1)
        edit = FieldEdit(field_id="field-1", value="New Value", bbox=bbox)
        assert edit.bbox == bbox
