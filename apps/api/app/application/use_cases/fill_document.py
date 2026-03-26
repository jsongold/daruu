"""Fill Document Use Case.

This use case handles filling target documents with extracted values:
- AcroForm field filling for PDF forms
- Coordinate-based overlay drawing for non-AcroForm PDFs
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field


class FillMethod(str, Enum):
    """Method for filling the document."""

    ACROFORM = "acroform"  # Use AcroForm field filling
    OVERLAY = "overlay"  # Use coordinate-based overlay


class FieldValue(BaseModel):
    """A value to fill into a field."""

    field_id: str = Field(..., description="Target field ID")
    value: str = Field(..., description="Value to fill")
    field_type: str = Field(default="text", description="Field type")
    page: int = Field(..., ge=1, description="Page number")
    bbox: tuple[float, float, float, float] = Field(
        ..., description="Field bounding box (x0, y0, x1, y1)"
    )

    model_config = {"frozen": True}


class RenderParams(BaseModel):
    """Rendering parameters for overlay drawing."""

    font_name: str = Field(default="Helvetica", description="Font family name")
    font_size: float = Field(default=12.0, gt=0, description="Font size in points")
    font_color: tuple[float, float, float] = Field(
        default=(0, 0, 0), description="RGB color (0-1 range)"
    )
    alignment: str = Field(default="left", description="Text alignment")
    line_height: float = Field(default=1.2, gt=0, description="Line height multiplier")
    max_lines: int = Field(default=1, ge=1, description="Maximum lines for wrapping")
    padding: tuple[float, float, float, float] = Field(
        default=(0, 0, 0, 0), description="Padding (top, right, bottom, left)"
    )

    model_config = {"frozen": True}


class FillRequest(BaseModel):
    """Request to fill a document."""

    job_id: str = Field(..., description="Job ID")
    document_id: str = Field(..., description="Target document ID")
    document_ref: str = Field(..., description="Reference to target document")
    values: list[FieldValue] = Field(..., description="Values to fill")
    method: FillMethod = Field(..., description="Fill method to use")
    render_params: RenderParams = Field(
        default_factory=RenderParams, description="Default rendering parameters"
    )
    field_render_params: dict[str, RenderParams] = Field(
        default_factory=dict, description="Field-specific rendering parameters"
    )

    model_config = {"frozen": True}


class FillResult(BaseModel):
    """Result of document filling."""

    job_id: str = Field(..., description="Job ID")
    document_id: str = Field(..., description="Target document ID")
    output_ref: str = Field(..., description="Reference to filled PDF")
    success: bool = Field(..., description="Whether filling succeeded")
    filled_fields: list[str] = Field(default_factory=list, description="Field IDs that were filled")
    failed_fields: list[str] = Field(
        default_factory=list, description="Field IDs that failed to fill"
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Issues encountered (overflow, overlap, etc.)",
    )
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"frozen": True}


class PDFWriter(Protocol):
    """Interface for PDF writing operations."""

    async def fill_acroform_field(
        self,
        pdf_ref: str,
        field_name: str,
        value: str,
    ) -> bool:
        """Fill an AcroForm field in the PDF.

        Returns True if successful, False otherwise.
        """
        ...

    async def draw_text_overlay(
        self,
        pdf_ref: str,
        page: int,
        bbox: tuple[float, float, float, float],
        text: str,
        params: RenderParams,
    ) -> bool:
        """Draw text as an overlay on the PDF.

        Returns True if successful, False otherwise.
        """
        ...

    async def save_pdf(
        self,
        output_ref: str,
    ) -> None:
        """Save the modified PDF to the output reference."""
        ...

    async def check_overflow(
        self,
        bbox: tuple[float, float, float, float],
        text: str,
        params: RenderParams,
    ) -> bool:
        """Check if text would overflow the bounding box.

        Returns True if overflow would occur.
        """
        ...

    async def check_overlap(
        self,
        page: int,
        bbox: tuple[float, float, float, float],
        existing_bboxes: list[tuple[float, float, float, float]],
    ) -> bool:
        """Check if bbox would overlap with existing bboxes.

        Returns True if overlap would occur.
        """
        ...


@dataclass(frozen=True)
class FillDocumentUseCase:
    """Use case for filling target documents.

    Supports two methods:
    - AcroForm: Direct field filling for PDF forms
    - Overlay: Coordinate-based text drawing for non-form PDFs

    Quality checks:
    - Overflow detection (text exceeds bbox)
    - Overlap detection (text overlaps other fields)
    - Font embedding for consistent display
    """

    async def execute(
        self,
        request: FillRequest,
        pdf_writer: PDFWriter,
    ) -> FillResult:
        """Execute document filling.

        Args:
            request: Fill request with values and parameters
            pdf_writer: PDF writer implementation

        Returns:
            Fill result with output reference and status
        """
        filled_fields: list[str] = []
        failed_fields: list[str] = []
        issues: list[str] = []
        errors: list[str] = []

        # Track filled bboxes for overlap detection (per page)
        filled_bboxes: dict[int, list[tuple[float, float, float, float]]] = {}

        for field_value in request.values:
            try:
                # Get render params for this field
                params = request.field_render_params.get(
                    field_value.field_id, request.render_params
                )

                # Check for potential issues
                if request.method == FillMethod.OVERLAY:
                    # Check overflow
                    would_overflow = await pdf_writer.check_overflow(
                        field_value.bbox, field_value.value, params
                    )
                    if would_overflow:
                        issues.append(f"Field {field_value.field_id}: Text may overflow bbox")

                    # Check overlap
                    page_bboxes = filled_bboxes.get(field_value.page, [])
                    would_overlap = await pdf_writer.check_overlap(
                        field_value.page, field_value.bbox, page_bboxes
                    )
                    if would_overlap:
                        issues.append(
                            f"Field {field_value.field_id}: Bbox overlaps with another field"
                        )

                # Fill the field
                success = await self._fill_field(pdf_writer, request, field_value, params)

                if success:
                    filled_fields.append(field_value.field_id)
                    # Track bbox for overlap detection
                    if field_value.page not in filled_bboxes:
                        filled_bboxes[field_value.page] = []
                    filled_bboxes[field_value.page].append(field_value.bbox)
                else:
                    failed_fields.append(field_value.field_id)

            except Exception as e:
                failed_fields.append(field_value.field_id)
                errors.append(f"Field {field_value.field_id}: {str(e)}")

        # Generate output reference
        output_ref = f"outputs/{request.job_id}/output.pdf"

        # Save the PDF
        try:
            await pdf_writer.save_pdf(output_ref)
        except Exception as e:
            errors.append(f"Failed to save PDF: {str(e)}")
            return FillResult(
                job_id=request.job_id,
                document_id=request.document_id,
                output_ref="",
                success=False,
                filled_fields=filled_fields,
                failed_fields=failed_fields,
                issues=issues,
                errors=errors,
            )

        return FillResult(
            job_id=request.job_id,
            document_id=request.document_id,
            output_ref=output_ref,
            success=len(errors) == 0,
            filled_fields=filled_fields,
            failed_fields=failed_fields,
            issues=issues,
            errors=errors,
        )

    async def _fill_field(
        self,
        pdf_writer: PDFWriter,
        request: FillRequest,
        field_value: FieldValue,
        params: RenderParams,
    ) -> bool:
        """Fill a single field using the appropriate method."""
        if request.method == FillMethod.ACROFORM:
            # Use AcroForm field name (assume field_id maps to form field name)
            return await pdf_writer.fill_acroform_field(
                request.document_ref,
                field_value.field_id,
                field_value.value,
            )
        else:
            # Use overlay drawing
            return await pdf_writer.draw_text_overlay(
                request.document_ref,
                field_value.page,
                field_value.bbox,
                field_value.value,
                params,
            )
