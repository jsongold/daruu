"""LLM Gateway interface.

Defines the contract for LLM operations used in document analysis.
The primary implementation will use LangChain for model abstraction.

Key responsibilities:
- Link labels to field positions (Structure/Labelling phase)
- Resolve extraction ambiguity
- Generate follow-up questions for missing/uncertain fields
- Normalize extracted values
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel
from pydantic import Field as PydanticField


class LabelCandidate(BaseModel):
    """A candidate label found in the document."""

    text: str = PydanticField(..., description="Label text")
    bbox: tuple[float, float, float, float] = PydanticField(
        ..., description="Bounding box (x0, y0, x1, y1)"
    )
    page: int = PydanticField(..., ge=1, description="Page number")
    confidence: float = PydanticField(..., ge=0.0, le=1.0, description="OCR/detection confidence")

    model_config = {"frozen": True}


class BoxCandidate(BaseModel):
    """A candidate input box/region found in the document."""

    bbox: tuple[float, float, float, float] = PydanticField(
        ..., description="Bounding box (x0, y0, x1, y1)"
    )
    page: int = PydanticField(..., ge=1, description="Page number")
    box_type: str = PydanticField(default="text", description="Type of box (text, checkbox, etc.)")

    model_config = {"frozen": True}


class LinkedField(BaseModel):
    """A field with its label linked to a position."""

    id: str = PydanticField(..., description="Field ID")
    name: str = PydanticField(..., description="Field name/label")
    field_type: str = PydanticField(..., description="Field type")
    page: int = PydanticField(..., ge=1, description="Page number")
    bbox: tuple[float, float, float, float] = PydanticField(
        ..., description="Input region bounding box"
    )
    anchor_bbox: tuple[float, float, float, float] | None = PydanticField(
        None, description="Label/anchor bounding box"
    )
    confidence: float = PydanticField(..., ge=0.0, le=1.0, description="Linking confidence")
    evidence_refs: list[str] = PydanticField(
        default_factory=list, description="References to supporting evidence"
    )

    model_config = {"frozen": True}


class EvidenceRef(BaseModel):
    """Reference to evidence supporting a decision."""

    id: str = PydanticField(..., description="Evidence ID")
    kind: str = PydanticField(
        ..., description="Evidence kind (native_text, ocr, llm_linking, user_input)"
    )
    document: str = PydanticField(..., description="Document type (source/target)")
    page: int = PydanticField(..., ge=1, description="Page number")
    bbox: tuple[float, float, float, float] | None = PydanticField(None, description="Bounding box")
    text: str | None = PydanticField(None, description="Extracted text")
    confidence: float = PydanticField(..., ge=0.0, le=1.0, description="Confidence")

    model_config = {"frozen": True}


class AmbiguityResolutionResult(BaseModel):
    """Result of resolving extraction ambiguity."""

    value: str = PydanticField(..., description="Resolved value")
    confidence: float = PydanticField(..., ge=0.0, le=1.0, description="Resolution confidence")
    evidence: list[EvidenceRef] = PydanticField(
        default_factory=list, description="Supporting evidence"
    )
    rationale: str | None = PydanticField(None, description="Explanation of resolution")
    alternatives: list[str] = PydanticField(
        default_factory=list, description="Alternative values considered"
    )

    model_config = {"frozen": True}


class FollowUpQuestion(BaseModel):
    """A question to ask the user for missing/uncertain information."""

    field_id: str = PydanticField(..., description="Related field ID")
    question: str = PydanticField(..., description="Question text")
    reason: str = PydanticField(..., description="Why this question is needed")
    expected_format: str | None = PydanticField(None, description="Expected answer format")
    suggestions: list[str] = PydanticField(default_factory=list, description="Suggested answers")

    model_config = {"frozen": True}


class OCRToken(BaseModel):
    """A token from OCR extraction."""

    text: str = PydanticField(..., description="Token text")
    bbox: tuple[float, float, float, float] = PydanticField(..., description="Bounding box")
    confidence: float = PydanticField(..., ge=0.0, le=1.0, description="OCR confidence")

    model_config = {"frozen": True}


class FieldContext(BaseModel):
    """Context for a field during extraction."""

    field_id: str = PydanticField(..., description="Field ID")
    field_name: str = PydanticField(..., description="Field name")
    field_type: str = PydanticField(..., description="Field type")
    expected_format: str | None = PydanticField(None, description="Expected format")
    validation_rules: dict[str, str] | None = PydanticField(None, description="Validation rules")

    model_config = {"frozen": True}


@runtime_checkable
class LLMGateway(Protocol):
    """Interface for LLM operations (implemented by LangChain).

    This gateway abstracts LLM functionality for document analysis,
    allowing different LLM providers to be swapped via LangChain.
    """

    async def link_labels_to_fields(
        self,
        label_candidates: list[LabelCandidate],
        box_candidates: list[BoxCandidate],
        page_image_ref: str,
    ) -> list[LinkedField]:
        """Link labels to field positions (Structure/Labelling phase).

        This is a critical step that requires LLM because:
        - Label text variations (year-to-year changes)
        - Multiple candidates for same semantic field
        - Table/form structure interpretation
        - Nested box relationships

        Args:
            label_candidates: Labels found via OCR/detection
            box_candidates: Input boxes/regions detected
            page_image_ref: Reference to the page image for visual context

        Returns:
            List of fields with labels linked to positions
        """
        ...

    async def resolve_ambiguity(
        self,
        field_context: FieldContext,
        ocr_tokens: list[OCRToken],
        context: dict[str, str | int | float | bool],
    ) -> AmbiguityResolutionResult:
        """Resolve extraction ambiguity using LLM reasoning.

        Called when:
        - OCR confidence is low
        - Multiple candidate values exist
        - Value needs normalization (dates, addresses, names)
        - Conflicting information detected

        Args:
            field_context: Context about the field being extracted
            ocr_tokens: OCR tokens in the field region
            context: Additional context (document type, previous values, etc.)

        Returns:
            Resolution result with value, confidence, and evidence
        """
        ...

    async def generate_questions(
        self,
        missing_fields: list[FieldContext],
        uncertain_fields: list[tuple[FieldContext, float]],
        document_context: dict[str, str | int | float | bool],
    ) -> list[FollowUpQuestion]:
        """Generate minimal follow-up questions for missing/uncertain fields.

        The goal is to ask the fewest questions possible to fill
        all missing/uncertain fields. May combine related fields
        into single questions.

        Args:
            missing_fields: Fields with no extracted value
            uncertain_fields: Fields with low confidence (field, confidence)
            document_context: Document-level context

        Returns:
            List of follow-up questions
        """
        ...

    async def normalize_value(
        self,
        raw_value: str,
        field_context: FieldContext,
        normalization_rules: dict[str, str] | None = None,
    ) -> tuple[str, float]:
        """Normalize an extracted value according to rules.

        Examples:
        - Date format: "2024/01/15" -> "2024-01-15"
        - Name: "YAMADA TARO" -> "Yamada Taro"
        - Address: Postal code completion
        - Numbers: Half/full-width conversion

        Args:
            raw_value: Raw extracted value
            field_context: Context about the field
            normalization_rules: Optional custom rules

        Returns:
            Tuple of (normalized_value, confidence)
        """
        ...
