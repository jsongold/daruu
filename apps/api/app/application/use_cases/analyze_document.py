"""Analyze Document Use Case.

This use case handles document structure analysis:
- Detect fields/anchors in the document
- Use LLM for label-to-position linking (Structure/Labelling phase)
- Generate field metadata with confidence scores
"""

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from app.application.ports.llm_gateway import (
    BoxCandidate,
    LabelCandidate,
    LinkedField,
    LLMGateway,
)
from app.application.ports.ocr_gateway import OCRGateway


class AnalyzeRequest(BaseModel):
    """Request to analyze a document."""

    document_id: str = Field(..., description="Document ID to analyze")
    document_ref: str = Field(..., description="Reference to the document file")
    page_image_refs: list[str] = Field(
        ..., description="References to page images for analysis"
    )
    options: dict[str, str | int | float | bool] = Field(
        default_factory=dict, description="Analysis options"
    )

    model_config = {"frozen": True}


class AnalyzeResult(BaseModel):
    """Result of document analysis."""

    document_id: str = Field(..., description="Analyzed document ID")
    fields: list[LinkedField] = Field(
        default_factory=list, description="Detected and linked fields"
    )
    success: bool = Field(..., description="Whether analysis succeeded")
    errors: list[str] = Field(
        default_factory=list, description="Any errors encountered"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Any warnings generated"
    )

    model_config = {"frozen": True}


class DocumentAnalyzer(Protocol):
    """Interface for document structure analysis (detecting boxes/labels)."""

    async def detect_labels(
        self, page_image_ref: str
    ) -> list[LabelCandidate]:
        """Detect label candidates in a page image."""
        ...

    async def detect_boxes(
        self, page_image_ref: str
    ) -> list[BoxCandidate]:
        """Detect input box candidates in a page image."""
        ...


@dataclass(frozen=True)
class AnalyzeDocumentUseCase:
    """Use case for analyzing document structure.

    This use case orchestrates:
    1. Label/text detection (via DocumentAnalyzer or OCR)
    2. Input box detection (form fields, checkboxes, etc.)
    3. Label-to-position linking (via LLM - critical step)

    The LLM is REQUIRED for label-to-position linking because:
    - Label text variations across document versions
    - Multiple candidates for same semantic field
    - Table/form structure interpretation needs reasoning
    - Nested box relationships require understanding
    """

    llm_gateway: LLMGateway
    ocr_gateway: OCRGateway

    async def execute(
        self,
        request: AnalyzeRequest,
        document_analyzer: DocumentAnalyzer | None = None,
    ) -> AnalyzeResult:
        """Execute document analysis.

        Args:
            request: Analysis request with document references
            document_analyzer: Optional custom analyzer (defaults to OCR-based)

        Returns:
            Analysis result with detected and linked fields
        """
        all_fields: list[LinkedField] = []
        errors: list[str] = []
        warnings: list[str] = []

        for page_idx, page_image_ref in enumerate(request.page_image_refs, start=1):
            try:
                # Step 1: Detect labels and boxes
                if document_analyzer:
                    label_candidates = await document_analyzer.detect_labels(
                        page_image_ref
                    )
                    box_candidates = await document_analyzer.detect_boxes(
                        page_image_ref
                    )
                else:
                    # Fallback to OCR-based detection
                    label_candidates, box_candidates = await self._detect_via_ocr(
                        page_image_ref, page_idx
                    )

                # Step 2: Link labels to positions using LLM (CRITICAL)
                # This step requires LLM for accurate semantic understanding
                linked_fields = await self.llm_gateway.link_labels_to_fields(
                    label_candidates=label_candidates,
                    box_candidates=box_candidates,
                    page_image_ref=page_image_ref,
                )

                all_fields.extend(linked_fields)

            except Exception as e:
                errors.append(f"Page {page_idx}: {str(e)}")

        return AnalyzeResult(
            document_id=request.document_id,
            fields=all_fields,
            success=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def _detect_via_ocr(
        self,
        page_image_ref: str,
        page: int,
    ) -> tuple[list[LabelCandidate], list[BoxCandidate]]:
        """Detect labels and boxes using OCR.

        This is a fallback when no custom document analyzer is provided.
        Uses OCR to find text regions and infers boxes from layout.
        """
        # Extract text using OCR
        ocr_result = await self.ocr_gateway.extract_text(page_image_ref)

        # Convert OCR lines to label candidates
        label_candidates = [
            LabelCandidate(
                text=line.text,
                bbox=line.bbox,
                page=page,
                confidence=line.confidence,
            )
            for line in ocr_result.ocr_lines
        ]

        # Detect text regions as potential box candidates
        # In production, this would use more sophisticated detection
        text_regions = await self.ocr_gateway.detect_text_regions(page_image_ref)
        box_candidates = [
            BoxCandidate(bbox=bbox, page=page, box_type="text")
            for bbox in text_regions
        ]

        return label_candidates, box_candidates
