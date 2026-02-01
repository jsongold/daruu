"""LangChain LLM Gateway implementation.

Implements the LLMGateway interface using LangChain for model abstraction.
This allows switching between different LLM providers (OpenAI, Anthropic, etc.)
without changing the application code.
"""

from dataclasses import dataclass
from uuid import uuid4

from app.application.ports.llm_gateway import (
    AmbiguityResolutionResult,
    BoxCandidate,
    EvidenceRef,
    FieldContext,
    FollowUpQuestion,
    LabelCandidate,
    LinkedField,
    LLMGateway,
    OCRToken,
)
from app.config import get_settings


@dataclass
class LangChainLLMGateway:
    """LangChain implementation of LLMGateway.

    This adapter implements LLM operations using LangChain, providing:
    - Provider abstraction (OpenAI, Anthropic, Google, etc.)
    - Agent construction with tools (OCR, PDF extraction, etc.)
    - Structured output parsing for type-safe results

    Currently a stub implementation - will be completed with LangChain integration.
    """

    model_name: str = "gpt-4o-mini"

    def __post_init__(self) -> None:
        """Initialize the LangChain components."""
        settings = get_settings()
        self.model_name = settings.openai_model

    async def link_labels_to_fields(
        self,
        label_candidates: list[LabelCandidate],
        box_candidates: list[BoxCandidate],
        page_image_ref: str,
    ) -> list[LinkedField]:
        """Link labels to field positions using LLM.

        This is a CRITICAL step that requires LLM because:
        - Label text variations (year-to-year changes)
        - Multiple candidates for same semantic field
        - Table/form structure interpretation
        - Nested box relationships require understanding

        Args:
            label_candidates: Labels found via OCR/detection
            box_candidates: Input boxes/regions detected
            page_image_ref: Reference to the page image for visual context

        Returns:
            List of fields with labels linked to positions

        TODO: Implement with LangChain
        - Use vision-capable model (GPT-4V, Claude 3) for visual understanding
        - Provide OCR results and box candidates as context
        - Use structured output to ensure valid field definitions
        """
        # Stub implementation - raises NotImplementedError
        # Real implementation will use LangChain with:
        # 1. Vision model for image understanding
        # 2. Structured output for LinkedField[] result
        # 3. Tools for OCR lookup and coordinate calculation
        raise NotImplementedError(
            "LangChain label-to-field linking not yet implemented. "
            "TODO: Implement with LangChain vision model and structured output."
        )

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

        TODO: Implement with LangChain
        - Use reasoning model for ambiguity resolution
        - Provide OCR results and field context
        - Return structured result with evidence
        """
        # Stub implementation - returns best OCR token as value
        if not ocr_tokens:
            return AmbiguityResolutionResult(
                value="",
                confidence=0.0,
                evidence=[],
                rationale="No OCR tokens available",
                alternatives=[],
            )

        # Simple stub: use the first token with highest confidence
        best_token = max(ocr_tokens, key=lambda t: t.confidence)

        return AmbiguityResolutionResult(
            value=best_token.text,
            confidence=best_token.confidence * 0.8,  # Reduce confidence for stub
            evidence=[
                EvidenceRef(
                    id=f"ev_{uuid4().hex[:8]}",
                    kind="ocr",
                    document="source",
                    page=1,  # Would need actual page from context
                    bbox=best_token.bbox,
                    text=best_token.text,
                    confidence=best_token.confidence,
                )
            ],
            rationale="Stub implementation: Selected highest-confidence OCR token",
            alternatives=[t.text for t in ocr_tokens if t.text != best_token.text][:3],
        )

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

        TODO: Implement with LangChain
        - Use reasoning model to generate minimal question set
        - Group related fields into single questions
        - Provide context-aware suggestions
        """
        # Stub implementation - generate one question per field
        questions: list[FollowUpQuestion] = []

        for field in missing_fields:
            questions.append(
                FollowUpQuestion(
                    field_id=field.field_id,
                    question=f"Please provide the value for '{field.field_name}'",
                    reason="Value could not be extracted from the document",
                    expected_format=field.expected_format,
                    suggestions=[],
                )
            )

        for field, confidence in uncertain_fields:
            questions.append(
                FollowUpQuestion(
                    field_id=field.field_id,
                    question=(
                        f"Please verify the value for '{field.field_name}' "
                        f"(confidence: {confidence:.0%})"
                    ),
                    reason=f"Extraction confidence is low ({confidence:.0%})",
                    expected_format=field.expected_format,
                    suggestions=[],
                )
            )

        return questions

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

        TODO: Implement with LangChain
        - Use model for intelligent normalization
        - Apply field-type-specific rules
        - Handle Japanese-specific normalizations
        """
        # Stub implementation - return raw value with basic normalization
        normalized = raw_value.strip()

        # Basic half-width to full-width conversion for numbers (Japanese forms)
        # This is a stub - real implementation would use LangChain
        half_to_full = {
            "0": "0", "1": "1", "2": "2", "3": "3", "4": "4",
            "5": "5", "6": "6", "7": "7", "8": "8", "9": "9",
        }

        # Apply basic normalization based on field type
        if field_context.field_type == "date":
            # Try to normalize date format
            normalized = normalized.replace("/", "-")

        return normalized, 0.9  # High confidence for basic normalization


# Ensure the adapter implements the protocol
def _verify_protocol() -> None:
    """Verify that LangChainLLMGateway implements LLMGateway."""
    adapter: LLMGateway = LangChainLLMGateway()  # noqa: F841
