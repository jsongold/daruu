"""End-to-end tests for AcroForm field extraction feature.

Tests the complete flow of:
1. AcroForm API endpoint (GET /documents/{id}/acroform-fields)
2. Pipeline integration for field extraction
3. Non-AcroForm PDF handling

Uses real PDF files with AcroForm fields from apps/tests/assets/.
"""

import io
from pathlib import Path
from typing import Generator

import pytest
from app.main import app
from app.models.acroform import AcroFormFieldInfo, AcroFormFieldsResponse
from fastapi.testclient import TestClient

# =============================================================================
# Test Assets
# =============================================================================

# Path to test PDF with AcroForm fields
# Test file is at: apps/api/tests/test_acroform_e2e.py
# PDF is at: apps/tests/assets/2025bun_01_input.pdf
ACROFORM_PDF_PATH = (
    Path(__file__).parent.parent.parent / "tests" / "assets" / "2025bun_01_input.pdf"
)


def create_pdf_with_acroform_fields() -> bytes:
    """Create a simple PDF with AcroForm fields for testing.

    Creates a PDF with:
    - 1 text field
    - 1 checkbox
    - 1 combobox (dropdown)

    Returns:
        PDF content as bytes.
    """
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size

    # Add a text field
    widget_text = fitz.Widget()
    widget_text.field_name = "test_name"
    widget_text.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget_text.rect = fitz.Rect(100, 100, 300, 125)
    widget_text.field_value = "John Doe"
    page.add_widget(widget_text)

    # Add a checkbox
    widget_checkbox = fitz.Widget()
    widget_checkbox.field_name = "test_agree"
    widget_checkbox.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    widget_checkbox.rect = fitz.Rect(100, 150, 120, 170)
    page.add_widget(widget_checkbox)

    # Add a combobox (dropdown)
    widget_combo = fitz.Widget()
    widget_combo.field_name = "test_option"
    widget_combo.field_type = fitz.PDF_WIDGET_TYPE_COMBOBOX
    widget_combo.rect = fitz.Rect(100, 200, 300, 225)
    widget_combo.choice_values = ["Option A", "Option B", "Option C"]
    page.add_widget(widget_combo)

    pdf_bytes = doc.tobytes()
    doc.close()

    return pdf_bytes


def create_pdf_without_acroform() -> bytes:
    """Create a simple PDF without any AcroForm fields.

    Returns:
        PDF content as bytes.
    """
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Add some text content (not a form field)
    text_point = fitz.Point(100, 100)
    page.insert_text(text_point, "This is a regular PDF without form fields.")

    pdf_bytes = doc.tobytes()
    doc.close()

    return pdf_bytes


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create a test client."""
    yield TestClient(app)


@pytest.fixture
def api_prefix() -> str:
    """Get the API prefix."""
    from app.config import get_settings

    return get_settings().api_prefix


@pytest.fixture
def acroform_pdf_content() -> bytes:
    """Get PDF content with AcroForm fields.

    Uses the real test PDF if available, otherwise creates one.
    """
    if ACROFORM_PDF_PATH.exists():
        return ACROFORM_PDF_PATH.read_bytes()
    return create_pdf_with_acroform_fields()


@pytest.fixture
def non_acroform_pdf_content() -> bytes:
    """Get PDF content without AcroForm fields."""
    return create_pdf_without_acroform()


@pytest.fixture
def simple_acroform_pdf_content() -> bytes:
    """Get a simple programmatically-created PDF with AcroForm fields."""
    return create_pdf_with_acroform_fields()


# =============================================================================
# AcroForm API Endpoint Tests
# =============================================================================


class TestAcroFormFieldsEndpoint:
    """Tests for GET /documents/{id}/acroform-fields endpoint."""

    def test_returns_acroform_fields_for_pdf_with_forms(
        self,
        client: TestClient,
        api_prefix: str,
        acroform_pdf_content: bytes,
    ) -> None:
        """Test that AcroForm fields are correctly returned for a PDF with forms."""
        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test_form.pdf", io.BytesIO(acroform_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        assert upload_response.status_code == 201
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Validate response structure
        result = data["data"]
        assert result["has_acroform"] is True
        assert len(result["fields"]) > 0
        assert len(result["page_dimensions"]) > 0
        assert result["preview_scale"] == 2

    def test_returns_correct_field_types(
        self,
        client: TestClient,
        api_prefix: str,
        acroform_pdf_content: bytes,
    ) -> None:
        """Test that field types are correctly identified."""
        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test_form.pdf", io.BytesIO(acroform_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
        result = response.json()["data"]

        # Check for expected field types
        field_types = {field["field_type"] for field in result["fields"]}

        # The test PDF should have text, checkbox, and combobox fields
        assert "text" in field_types, "Expected text fields in the PDF"
        assert "checkbox" in field_types, "Expected checkbox fields in the PDF"
        assert "combobox" in field_types, "Expected combobox fields in the PDF"

    def test_returns_valid_bbox_coordinates(
        self,
        client: TestClient,
        api_prefix: str,
        acroform_pdf_content: bytes,
    ) -> None:
        """Test that bounding boxes have valid coordinates."""
        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test_form.pdf", io.BytesIO(acroform_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
        result = response.json()["data"]

        for field in result["fields"]:
            bbox = field["bbox"]

            # Validate bbox structure
            assert "x" in bbox
            assert "y" in bbox
            assert "width" in bbox
            assert "height" in bbox
            assert "page" in bbox

            # Validate bbox values are reasonable
            assert bbox["x"] >= 0, f"bbox x should be >= 0, got {bbox['x']}"
            assert bbox["y"] >= 0, f"bbox y should be >= 0, got {bbox['y']}"
            assert bbox["width"] >= 0, f"bbox width should be >= 0, got {bbox['width']}"
            assert bbox["height"] >= 0, f"bbox height should be >= 0, got {bbox['height']}"
            assert bbox["page"] >= 1, f"bbox page should be >= 1, got {bbox['page']}"

    def test_returns_page_dimensions(
        self,
        client: TestClient,
        api_prefix: str,
        acroform_pdf_content: bytes,
    ) -> None:
        """Test that page dimensions are correctly returned."""
        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test_form.pdf", io.BytesIO(acroform_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
        result = response.json()["data"]

        # Validate page dimensions
        page_dims = result["page_dimensions"]
        assert len(page_dims) > 0

        for page_dim in page_dims:
            assert page_dim["page"] >= 1
            assert page_dim["width"] > 0
            assert page_dim["height"] > 0


class TestNonAcroFormPDF:
    """Tests for PDFs without AcroForm fields."""

    def test_returns_has_acroform_false(
        self,
        client: TestClient,
        api_prefix: str,
        non_acroform_pdf_content: bytes,
    ) -> None:
        """Test that non-AcroForm PDFs return has_acroform=false."""
        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={
                "file": ("regular.pdf", io.BytesIO(non_acroform_pdf_content), "application/pdf")
            },
            data={"document_type": "target"},
        )
        assert upload_response.status_code == 201
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        result = data["data"]
        assert result["has_acroform"] is False
        assert len(result["fields"]) == 0

    def test_returns_page_dimensions_even_without_forms(
        self,
        client: TestClient,
        api_prefix: str,
        non_acroform_pdf_content: bytes,
    ) -> None:
        """Test that page dimensions are returned even for non-form PDFs."""
        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={
                "file": ("regular.pdf", io.BytesIO(non_acroform_pdf_content), "application/pdf")
            },
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
        result = response.json()["data"]

        # Should still have page dimensions
        assert len(result["page_dimensions"]) > 0


class TestAcroFormEndpointEdgeCases:
    """Edge case tests for the AcroForm endpoint."""

    def test_returns_404_for_nonexistent_document(
        self,
        client: TestClient,
        api_prefix: str,
    ) -> None:
        """Test that 404 is returned for non-existent document."""
        response = client.get(f"{api_prefix}/documents/nonexistent-doc-id/acroform-fields")
        assert response.status_code == 404

    def test_handles_simple_acroform_pdf(
        self,
        client: TestClient,
        api_prefix: str,
        simple_acroform_pdf_content: bytes,
    ) -> None:
        """Test with a programmatically created PDF with known fields."""
        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={
                "file": (
                    "simple_form.pdf",
                    io.BytesIO(simple_acroform_pdf_content),
                    "application/pdf",
                )
            },
            data={"document_type": "target"},
        )
        assert upload_response.status_code == 201
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")

        assert response.status_code == 200
        result = response.json()["data"]

        # Verify known fields exist
        field_names = {field["field_name"] for field in result["fields"]}
        assert "test_name" in field_names
        assert "test_agree" in field_names
        assert "test_option" in field_names

    def test_field_values_are_extracted(
        self,
        client: TestClient,
        api_prefix: str,
        simple_acroform_pdf_content: bytes,
    ) -> None:
        """Test that pre-filled field values are extracted."""
        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={
                "file": (
                    "simple_form.pdf",
                    io.BytesIO(simple_acroform_pdf_content),
                    "application/pdf",
                )
            },
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
        result = response.json()["data"]

        # Find the text field that was pre-filled
        text_field = next((f for f in result["fields"] if f["field_name"] == "test_name"), None)

        assert text_field is not None
        assert text_field["value"] == "John Doe"


class TestAcroFormFieldCount:
    """Tests for verifying field counts match expectations."""

    def test_real_pdf_field_count(
        self,
        client: TestClient,
        api_prefix: str,
        acroform_pdf_content: bytes,
    ) -> None:
        """Test that the real test PDF has expected number of fields."""
        # Skip if using generated PDF instead of real one
        if not ACROFORM_PDF_PATH.exists():
            pytest.skip("Real test PDF not available")

        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test_form.pdf", io.BytesIO(acroform_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
        result = response.json()["data"]

        # The real PDF has 189 fields
        assert len(result["fields"]) == 189

    def test_field_type_distribution(
        self,
        client: TestClient,
        api_prefix: str,
        acroform_pdf_content: bytes,
    ) -> None:
        """Test the distribution of field types in the PDF."""
        # Skip if using generated PDF instead of real one
        if not ACROFORM_PDF_PATH.exists():
            pytest.skip("Real test PDF not available")

        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test_form.pdf", io.BytesIO(acroform_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
        result = response.json()["data"]

        # Count field types
        type_counts: dict[str, int] = {}
        for field in result["fields"]:
            field_type = field["field_type"]
            type_counts[field_type] = type_counts.get(field_type, 0) + 1

        # The real PDF has text, checkbox, and combobox fields
        assert type_counts.get("text", 0) > 0
        assert type_counts.get("checkbox", 0) > 0
        assert type_counts.get("combobox", 0) > 0


# =============================================================================
# Response Model Validation Tests
# =============================================================================


class TestResponseModelValidation:
    """Tests for response model validation."""

    def test_response_matches_pydantic_model(
        self,
        client: TestClient,
        api_prefix: str,
        acroform_pdf_content: bytes,
    ) -> None:
        """Test that response can be parsed by Pydantic model."""
        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test_form.pdf", io.BytesIO(acroform_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
        result = response.json()["data"]

        # Validate with Pydantic model
        validated = AcroFormFieldsResponse(**result)

        assert validated.has_acroform is True
        assert len(validated.fields) > 0
        assert len(validated.page_dimensions) > 0

        # Validate individual fields
        for field in validated.fields:
            assert isinstance(field, AcroFormFieldInfo)
            assert field.field_name is not None
            assert field.field_type in [
                "text",
                "checkbox",
                "combobox",
                "radio",
                "button",
                "listbox",
                "signature",
                "unknown",
            ]

    def test_bbox_model_validation(
        self,
        client: TestClient,
        api_prefix: str,
        acroform_pdf_content: bytes,
    ) -> None:
        """Test that bbox fields validate correctly."""
        from app.models.common import BBox

        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test_form.pdf", io.BytesIO(acroform_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Get AcroForm fields
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
        result = response.json()["data"]

        # Validate each bbox
        for field_data in result["fields"]:
            bbox = BBox(**field_data["bbox"])
            assert bbox.x >= 0
            assert bbox.y >= 0
            assert bbox.width >= 0
            assert bbox.height >= 0
            assert bbox.page >= 1


# =============================================================================
# Performance Tests
# =============================================================================


class TestAcroFormPerformance:
    """Performance tests for AcroForm extraction."""

    def test_extraction_completes_in_reasonable_time(
        self,
        client: TestClient,
        api_prefix: str,
        acroform_pdf_content: bytes,
    ) -> None:
        """Test that extraction completes within 5 seconds."""
        import time

        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test_form.pdf", io.BytesIO(acroform_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Time the extraction
        start_time = time.time()
        response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
        elapsed_time = time.time() - start_time

        assert response.status_code == 200
        assert elapsed_time < 5.0, f"Extraction took {elapsed_time:.2f}s, expected < 5s"

    def test_multiple_extractions_consistent(
        self,
        client: TestClient,
        api_prefix: str,
        acroform_pdf_content: bytes,
    ) -> None:
        """Test that multiple extractions return consistent results."""
        # Upload the PDF
        upload_response = client.post(
            f"{api_prefix}/documents",
            files={"file": ("test_form.pdf", io.BytesIO(acroform_pdf_content), "application/pdf")},
            data={"document_type": "target"},
        )
        document_id = upload_response.json()["data"]["document_id"]

        # Extract multiple times
        results = []
        for _ in range(3):
            response = client.get(f"{api_prefix}/documents/{document_id}/acroform-fields")
            results.append(response.json()["data"])

        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result["has_acroform"] == first_result["has_acroform"]
            assert len(result["fields"]) == len(first_result["fields"])
            assert len(result["page_dimensions"]) == len(first_result["page_dimensions"])
