"""Tests for Ingest service Pydantic models.

Tests validate model creation, field constraints, and immutability.
"""

import pytest
from app.models.ingest import (
    DocumentMeta,
    IngestError,
    IngestErrorCode,
    IngestRequest,
    IngestResult,
    PageMeta,
    RenderedPage,
)
from pydantic import ValidationError


class TestPageMeta:
    """Tests for PageMeta model."""

    def test_valid_page_meta(self) -> None:
        """Test creating valid PageMeta."""
        page = PageMeta(page_number=1, width=612.0, height=792.0)
        assert page.page_number == 1
        assert page.width == 612.0
        assert page.height == 792.0
        assert page.rotation == 0  # default

    def test_page_meta_with_rotation(self) -> None:
        """Test PageMeta with rotation."""
        page = PageMeta(page_number=1, width=612.0, height=792.0, rotation=90)
        assert page.rotation == 90

    def test_page_number_zero_fails(self) -> None:
        """Test that page_number=0 is rejected (1-indexed)."""
        with pytest.raises(ValidationError):
            PageMeta(page_number=0, width=612.0, height=792.0)

    def test_negative_width_fails(self) -> None:
        """Test that negative width is rejected."""
        with pytest.raises(ValidationError):
            PageMeta(page_number=1, width=-1.0, height=792.0)

    def test_zero_height_fails(self) -> None:
        """Test that zero height is rejected."""
        with pytest.raises(ValidationError):
            PageMeta(page_number=1, width=612.0, height=0)

    def test_invalid_rotation_fails(self) -> None:
        """Test that rotation > 270 is rejected."""
        with pytest.raises(ValidationError):
            PageMeta(page_number=1, width=612.0, height=792.0, rotation=360)

    def test_page_meta_is_frozen(self) -> None:
        """Test that PageMeta is immutable."""
        page = PageMeta(page_number=1, width=612.0, height=792.0)
        with pytest.raises(ValidationError):
            page.width = 800.0  # type: ignore


class TestDocumentMeta:
    """Tests for DocumentMeta model."""

    def test_valid_document_meta(self) -> None:
        """Test creating valid DocumentMeta."""
        pages = (
            PageMeta(page_number=1, width=612.0, height=792.0),
            PageMeta(page_number=2, width=612.0, height=792.0),
        )
        meta = DocumentMeta(page_count=2, pages=pages)
        assert meta.page_count == 2
        assert len(meta.pages) == 2

    def test_zero_page_count_fails(self) -> None:
        """Test that page_count=0 is rejected."""
        with pytest.raises(ValidationError):
            DocumentMeta(page_count=0, pages=())

    def test_document_meta_is_frozen(self) -> None:
        """Test that DocumentMeta is immutable."""
        pages = (PageMeta(page_number=1, width=612.0, height=792.0),)
        meta = DocumentMeta(page_count=1, pages=pages)
        with pytest.raises(ValidationError):
            meta.page_count = 5  # type: ignore


class TestRenderedPage:
    """Tests for RenderedPage model."""

    def test_valid_rendered_page(self) -> None:
        """Test creating valid RenderedPage."""
        page = RenderedPage(
            page_number=1,
            image_ref="/artifacts/doc-123/page_1.png",
            width=1275,
            height=1650,
            dpi=150,
        )
        assert page.page_number == 1
        assert page.image_ref == "/artifacts/doc-123/page_1.png"
        assert page.width == 1275
        assert page.height == 1650
        assert page.dpi == 150

    def test_default_dpi(self) -> None:
        """Test that default DPI is 150."""
        page = RenderedPage(
            page_number=1,
            image_ref="/artifacts/page.png",
            width=100,
            height=100,
        )
        assert page.dpi == 150

    def test_invalid_page_number_fails(self) -> None:
        """Test that page_number < 1 is rejected."""
        with pytest.raises(ValidationError):
            RenderedPage(
                page_number=0,
                image_ref="/artifacts/page.png",
                width=100,
                height=100,
            )

    def test_zero_width_fails(self) -> None:
        """Test that zero width is rejected."""
        with pytest.raises(ValidationError):
            RenderedPage(
                page_number=1,
                image_ref="/artifacts/page.png",
                width=0,
                height=100,
            )


class TestIngestError:
    """Tests for IngestError model."""

    def test_valid_error(self) -> None:
        """Test creating valid IngestError."""
        error = IngestError(
            code=IngestErrorCode.INVALID_PDF,
            message="File is not a valid PDF",
        )
        assert error.code == IngestErrorCode.INVALID_PDF
        assert error.message == "File is not a valid PDF"
        assert error.page_number is None

    def test_error_with_page_number(self) -> None:
        """Test error with specific page number."""
        error = IngestError(
            code=IngestErrorCode.RENDER_FAILED,
            message="Failed to render page 5",
            page_number=5,
        )
        assert error.page_number == 5

    def test_all_error_codes(self) -> None:
        """Test all error codes are valid."""
        for code in IngestErrorCode:
            error = IngestError(code=code, message=f"Test {code.value}")
            assert error.code == code


class TestIngestRequest:
    """Tests for IngestRequest model."""

    def test_valid_request(self) -> None:
        """Test creating valid IngestRequest."""
        request = IngestRequest(
            document_id="doc-123",
            document_ref="/uploads/document.pdf",
        )
        assert request.document_id == "doc-123"
        assert request.document_ref == "/uploads/document.pdf"
        assert request.render_dpi == 150  # default
        assert request.render_pages is None  # default (all pages)

    def test_request_with_custom_dpi(self) -> None:
        """Test request with custom DPI."""
        request = IngestRequest(
            document_id="doc-123",
            document_ref="/uploads/document.pdf",
            render_dpi=300,
        )
        assert request.render_dpi == 300

    def test_request_with_specific_pages(self) -> None:
        """Test request with specific pages to render."""
        request = IngestRequest(
            document_id="doc-123",
            document_ref="/uploads/document.pdf",
            render_pages=[1, 3, 5],
        )
        assert request.render_pages == [1, 3, 5]

    def test_empty_document_id_fails(self) -> None:
        """Test that empty document_id is rejected."""
        with pytest.raises(ValidationError):
            IngestRequest(
                document_id="",
                document_ref="/uploads/document.pdf",
            )

    def test_empty_document_ref_fails(self) -> None:
        """Test that empty document_ref is rejected."""
        with pytest.raises(ValidationError):
            IngestRequest(
                document_id="doc-123",
                document_ref="",
            )

    def test_dpi_too_high_fails(self) -> None:
        """Test that DPI > 600 is rejected."""
        with pytest.raises(ValidationError):
            IngestRequest(
                document_id="doc-123",
                document_ref="/uploads/document.pdf",
                render_dpi=1200,
            )

    def test_request_is_frozen(self) -> None:
        """Test that IngestRequest is immutable."""
        request = IngestRequest(
            document_id="doc-123",
            document_ref="/uploads/document.pdf",
        )
        with pytest.raises(ValidationError):
            request.render_dpi = 300  # type: ignore


class TestIngestResult:
    """Tests for IngestResult model."""

    def test_successful_result(self) -> None:
        """Test creating successful IngestResult."""
        pages_meta = (PageMeta(page_number=1, width=612.0, height=792.0),)
        meta = DocumentMeta(page_count=1, pages=pages_meta)
        artifacts = (
            RenderedPage(
                page_number=1,
                image_ref="/artifacts/doc-123/page_1.png",
                width=1275,
                height=1650,
            ),
        )

        result = IngestResult(
            document_id="doc-123",
            success=True,
            meta=meta,
            artifacts=artifacts,
        )

        assert result.document_id == "doc-123"
        assert result.success is True
        assert result.meta is not None
        assert len(result.artifacts) == 1
        assert len(result.errors) == 0

    def test_failed_result(self) -> None:
        """Test creating failed IngestResult."""
        errors = (
            IngestError(
                code=IngestErrorCode.PASSWORD_PROTECTED,
                message="Document requires password",
            ),
        )

        result = IngestResult(
            document_id="doc-123",
            success=False,
            errors=errors,
        )

        assert result.success is False
        assert result.meta is None
        assert len(result.artifacts) == 0
        assert len(result.errors) == 1
        assert result.errors[0].code == IngestErrorCode.PASSWORD_PROTECTED

    def test_result_with_partial_success(self) -> None:
        """Test result with some pages failing."""
        pages_meta = (
            PageMeta(page_number=1, width=612.0, height=792.0),
            PageMeta(page_number=2, width=612.0, height=792.0),
        )
        meta = DocumentMeta(page_count=2, pages=pages_meta)
        artifacts = (
            RenderedPage(
                page_number=1,
                image_ref="/artifacts/doc-123/page_1.png",
                width=1275,
                height=1650,
            ),
        )
        errors = (
            IngestError(
                code=IngestErrorCode.RENDER_FAILED,
                message="Failed to render page 2",
                page_number=2,
            ),
        )

        result = IngestResult(
            document_id="doc-123",
            success=True,  # Overall success, but with errors
            meta=meta,
            artifacts=artifacts,
            errors=errors,
        )

        assert result.success is True
        assert len(result.artifacts) == 1
        assert len(result.errors) == 1

    def test_result_is_frozen(self) -> None:
        """Test that IngestResult is immutable."""
        result = IngestResult(document_id="doc-123", success=False)
        with pytest.raises(ValidationError):
            result.success = True  # type: ignore
