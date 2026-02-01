"""Port interfaces for Agents (Clean Architecture).

Agents are components that use LLM for reasoning, judgment, and proposals.
They are implemented as Ports (interfaces) so they can be easily replaced
or mocked for testing.

Following the Service vs Agent distinction:
- Service: Deterministic business logic (OcrService, PdfWriteService, etc.)
- Agent: Non-deterministic LLM reasoning (FieldLabellingAgent, etc.)
"""

from typing import Protocol

from app.models import FieldModel
from app.models.common import BBox


class FieldLabellingAgent(Protocol):
    """Agent for linking labels to field positions (bbox).

    This agent uses LLM to determine which label corresponds to which
    input field/bbox in the document. This is essential because:
    - Label strings may vary
    - Multiple candidates may exist
    - Tables/nested structures need interpretation
    - Year-to-year layout differences require reasoning

    Example usage:
        agent = LangChainFieldLabellingAgent(llm_client)
        fields = await agent.link_labels_to_bboxes(
            label_candidates=["Name", "Full Name", "氏名"],
            box_candidates=[BBox(...), BBox(...)],
            page_image=image_bytes,
        )
    """

    async def link_labels_to_bboxes(
        self,
        label_candidates: list[str],
        box_candidates: list[BBox],
        page_image: bytes | None = None,
        page_text: str | None = None,
        context: dict[str, any] | None = None,
    ) -> list[FieldModel]:
        """Link semantic labels to field positions (bbox).

        Args:
            label_candidates: List of potential label strings
            box_candidates: List of bounding boxes for potential fields
            page_image: Optional page image for visual analysis
            page_text: Optional extracted text from the page
            context: Optional additional context (table structure, etc.)

        Returns:
            List of FieldModel with name, type, bbox, anchor, confidence, etc.
        """
        ...


class ValueExtractionAgent(Protocol):
    """Agent for extracting and normalizing field values.

    This agent uses LLM to:
    - Resolve ambiguity when multiple value candidates exist
    - Normalize values (full-width/half-width, date formats, addresses)
    - Detect conflicts between different sources
    - Generate follow-up questions for missing/uncertain fields

    Example usage:
        agent = LangChainValueExtractionAgent(llm_client)
        result = await agent.extract_value(
            field=field_model,
            ocr_tokens=[...],
            pdf_text="...",
            evidence=[...],
        )
    """

    async def extract_value(
        self,
        field: FieldModel,
        ocr_tokens: list[dict[str, any]] | None = None,
        pdf_text: str | None = None,
        evidence: list[dict[str, any]] | None = None,
    ) -> dict[str, any]:
        """Extract and normalize a field value.

        Args:
            field: Field definition with type, bbox, anchor
            ocr_tokens: Optional OCR results with text, bbox, confidence
            pdf_text: Optional native PDF text extraction
            evidence: Optional evidence from previous extraction attempts

        Returns:
            Dictionary with:
            - value_candidates: List of (value, confidence, rationale, evidence_refs)
            - normalized_value: Normalized value (standardized format)
            - conflict_detected: Boolean indicating conflicts
            - followup_questions: List of questions for missing/uncertain info
        """
        ...


class MappingAgent(Protocol):
    """Agent for mapping source fields to target fields.

    This agent uses LLM to determine correspondences between
    source document fields and target document fields, handling:
    - 1-to-1 mappings
    - 1-to-many mappings
    - Many-to-1 mappings
    - Table row correspondences
    - Ambiguous mappings requiring user input

    Example usage:
        agent = LangChainMappingAgent(llm_client)
        mappings = await agent.generate_mappings(
            source_fields=[...],
            target_fields=[...],
            template_history=[...],
        )
    """

    async def generate_mappings(
        self,
        source_fields: list[FieldModel],
        target_fields: list[FieldModel],
        template_history: list[dict[str, any]] | None = None,
        user_rules: dict[str, any] | None = None,
    ) -> dict[str, any]:
        """Generate mappings between source and target fields.

        Args:
            source_fields: Fields from the source document
            target_fields: Fields from the target document
            template_history: Optional historical mapping patterns
            user_rules: Optional user-defined mapping rules

        Returns:
            Dictionary with:
            - mappings: List of Mapping objects (source_field_id, target_field_id, transform)
            - evidence_refs: Optional evidence for mapping decisions
            - followup_questions: Optional questions for ambiguous mappings
        """
        ...
