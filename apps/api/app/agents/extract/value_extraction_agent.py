"""LangChain-based Value Extraction Agent.

This agent uses LLM to assist with value extraction:
- Resolve ambiguity between candidates
- Normalize values to standard formats
- Detect conflicts between sources
- Generate follow-up questions

NOTE: This is NOT an OCR replacement. The agent only assists with:
- Ambiguity resolution
- Format normalization
- Conflict detection
- Question generation

The actual text extraction is done by native PDF extraction or OCR.
"""

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agents.llm_wrapper import extract_usage_from_response, log_llm_io
from app.config import get_settings
from app.models.cost import CostTracker
from app.models.extract.models import ExtractField, FollowupQuestion
from app.services.extract.domain.models import ValueCandidate
from app.services.extract.ports import ValueExtractionAgentPort

logger = logging.getLogger(__name__)


class LangChainValueExtractionAgent:
    """Value extraction agent using LangChain.

    Implements ValueExtractionAgentPort for LLM-assisted
    value extraction tasks.

    Uses OpenAI models via LangChain for:
    - Candidate resolution (selecting best value from options)
    - Value normalization (standardizing formats)
    - Conflict detection (identifying contradictory values)
    - Question generation (creating follow-up prompts)

    Tracks token usage for cost estimation via get_cost_tracker().
    """

    def __init__(
        self,
        llm: ChatOpenAI | None = None,
        temperature: float = 0.0,
        model: str | None = None,
    ) -> None:
        """Initialize the agent with an LLM.

        Args:
            llm: Optional pre-configured LangChain LLM instance
            temperature: LLM temperature (default: 0 for determinism)
            model: Model name (defaults to settings.openai_model)
        """
        settings = get_settings()

        self._model_name = model or settings.openai_model

        if llm is not None:
            self._llm = llm
        else:
            # Create LLM from settings
            api_key = settings.openai_api_key

            if not api_key:
                logger.warning("OPENAI_API_KEY not configured. LLM operations will fail.")

            self._llm = ChatOpenAI(
                model=self._model_name,
                temperature=temperature,
                api_key=api_key or "not-configured",
                base_url=settings.openai_base_url,
                timeout=settings.openai_timeout_seconds,
            )

        self._temperature = temperature
        self._cost_tracker = CostTracker.create(model_name=self._model_name)

    def get_cost_tracker(self) -> CostTracker:
        """Get the current cost tracker with accumulated usage.

        Returns:
            CostTracker with all LLM usage since initialization
        """
        return self._cost_tracker

    def reset_cost_tracker(self) -> None:
        """Reset the cost tracker to zero."""
        self._cost_tracker = CostTracker.create(model_name=self._model_name)

    def _track_usage(self, response: Any, operation: str) -> None:
        """Track token usage from an LLM response.

        Args:
            response: LangChain response object
            operation: Description of the operation
        """
        usage = extract_usage_from_response(
            response=response,
            model=self._model_name,
            agent_name="ValueExtractionAgent",
            operation=operation,
        )
        self._cost_tracker = self._cost_tracker.add_llm_usage(usage)

    @log_llm_io
    async def _invoke_llm(
        self,
        messages: list[Any],
        agent_name: str = "ValueExtractionAgent",
        operation: str = "",
    ) -> Any:
        """Call LLM. Decorated with log_llm_io for debug prompt logging."""
        return await self._llm.ainvoke(messages)

    async def resolve_candidates(
        self,
        field: ExtractField,
        candidates: tuple[ValueCandidate, ...],
        context: dict[str, Any] | None = None,
    ) -> ValueCandidate:
        """Resolve ambiguity when multiple candidates exist.

        Uses LLM reasoning to select the best candidate based on
        field type, confidence scores, and contextual information.

        Args:
            field: Field definition with type and validation
            candidates: Possible value candidates
            context: Optional additional context

        Returns:
            Selected best candidate with updated rationale

        Raises:
            ValueError: If no candidates provided
            RuntimeError: If LLM call fails
        """
        if not candidates:
            raise ValueError("No candidates provided")

        # If only one candidate, return it directly
        if len(candidates) == 1:
            return candidates[0]

        # Prepare candidate information for the prompt
        candidates_info = [
            {
                "index": i,
                "value": c.value,
                "confidence": c.confidence,
                "rationale": c.rationale,
            }
            for i, c in enumerate(candidates)
        ]

        system_prompt = RESOLVE_SYSTEM_PROMPT
        user_prompt = RESOLVE_USER_PROMPT.format(
            field_name=field.name,
            field_type=field.field_type,
            candidates=json.dumps(candidates_info, ensure_ascii=False, indent=2),
            context=json.dumps(context or {}, ensure_ascii=False),
        )

        try:
            response = await self._invoke_llm(
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ],
                operation="resolve_candidates",
            )

            # Track token usage
            self._track_usage(response, "resolve_candidates")

            # Parse response to get selected index
            response_text = response.content.strip()
            selected_index = self._parse_selected_index(response_text, len(candidates))

            # Return selected candidate with updated rationale
            selected = candidates[selected_index]
            return ValueCandidate(
                value=selected.value,
                confidence=selected.confidence,
                rationale=f"LLM selected: {response_text[:200]}",
                evidence_refs=selected.evidence_refs,
            )

        except Exception as e:
            logger.error(f"LLM candidate resolution failed: {e}", exc_info=True)
            # Fallback: return highest confidence candidate
            best = max(candidates, key=lambda c: c.confidence)
            return ValueCandidate(
                value=best.value,
                confidence=best.confidence * 0.8,  # Reduce confidence for fallback
                rationale=f"Fallback selection (LLM failed): {e}",
                evidence_refs=best.evidence_refs,
            )

    def _parse_selected_index(self, response: str, num_candidates: int) -> int:
        """Parse the selected index from LLM response.

        Args:
            response: LLM response text
            num_candidates: Number of available candidates

        Returns:
            Selected index (0-based)
        """
        # Try to extract a number from the response
        import re

        # Look for patterns like "index: 0", "selected: 1", or just a number
        patterns = [
            r"index[:\s]+(\d+)",
            r"selected[:\s]+(\d+)",
            r"candidate[:\s]+(\d+)",
            r"^(\d+)",
            r"\b(\d+)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, response.lower())
            if match:
                idx = int(match.group(1))
                if 0 <= idx < num_candidates:
                    return idx

        # Default to first candidate if parsing fails
        logger.warning(f"Could not parse index from response: {response[:100]}")
        return 0

    async def normalize_value(
        self,
        field: ExtractField,
        value: str,
        target_format: str | None = None,
    ) -> str:
        """Normalize a value to a standard format.

        Handles common normalizations:
        - Date: YYYY-MM-DD (including Japanese era dates)
        - Phone: digits only or formatted
        - Address: standardized Japanese address
        - Name: preserve original order
        - Numbers: remove formatting, convert full-width

        Args:
            field: Field definition with type
            value: Raw extracted value
            target_format: Optional target format specification

        Returns:
            Normalized value string

        Raises:
            ValueError: If value cannot be normalized
        """
        if not value or not value.strip():
            return value

        system_prompt = NORMALIZE_SYSTEM_PROMPT
        user_prompt = NORMALIZE_USER_PROMPT.format(
            field_type=field.field_type,
            field_name=field.name,
            value=value,
            target_format=target_format or "default",
        )

        try:
            response = await self._invoke_llm(
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ],
                operation="normalize_value",
            )

            # Track token usage
            self._track_usage(response, "normalize_value")

            normalized = response.content.strip()
            # Remove any quotes that might have been added
            if normalized.startswith('"') and normalized.endswith('"'):
                normalized = normalized[1:-1]
            if normalized.startswith("'") and normalized.endswith("'"):
                normalized = normalized[1:-1]

            return normalized

        except Exception as e:
            logger.error(f"LLM normalization failed: {e}", exc_info=True)
            # Return original value if normalization fails
            return value.strip()

    async def detect_conflicts(
        self,
        field: ExtractField,
        candidates: tuple[ValueCandidate, ...],
    ) -> tuple[bool, str | None]:
        """Detect conflicts between value candidates.

        Analyzes candidates to determine if they represent
        conflicting values (not just formatting differences).

        Args:
            field: Field definition
            candidates: Value candidates from different sources

        Returns:
            Tuple of (has_conflict, conflict_description)
        """
        if len(candidates) < 2:
            return False, None

        # Quick check: if all values are identical, no conflict
        values = {c.value.strip().lower() for c in candidates}
        if len(values) == 1:
            return False, None

        # Prepare candidates for LLM analysis
        candidates_info = [{"value": c.value, "confidence": c.confidence} for c in candidates]

        system_prompt = CONFLICT_SYSTEM_PROMPT
        user_prompt = CONFLICT_USER_PROMPT.format(
            field_name=field.name,
            field_type=field.field_type,
            candidates=json.dumps(candidates_info, ensure_ascii=False, indent=2),
        )

        try:
            response = await self._invoke_llm(
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ],
                operation="detect_conflicts",
            )

            # Track token usage
            self._track_usage(response, "detect_conflicts")

            response_text = response.content.strip().lower()

            # Parse response for conflict detection
            has_conflict = any(
                keyword in response_text
                for keyword in ["conflict", "contradictory", "inconsistent", "different meaning"]
            )

            # Don't flag as conflict if explicitly no conflict
            if any(
                phrase in response_text
                for phrase in [
                    "no conflict",
                    "no real conflict",
                    "same",
                    "equivalent",
                    "formatting",
                ]
            ):
                has_conflict = False

            description = response.content.strip() if has_conflict else None
            return has_conflict, description

        except Exception as e:
            logger.error(f"LLM conflict detection failed: {e}", exc_info=True)
            # Conservative fallback: assume conflict if values differ significantly
            return len(values) > 1, f"Unable to analyze (LLM error): {e}"

    async def generate_question(
        self,
        field: ExtractField,
        reason: str,
        candidates: tuple[ValueCandidate, ...] | None = None,
    ) -> FollowupQuestion:
        """Generate a follow-up question for user clarification.

        Creates a user-friendly question to resolve ambiguity
        or missing information.

        Args:
            field: Field that needs clarification
            reason: Why clarification is needed
            candidates: Optional candidates to present

        Returns:
            FollowupQuestion with appropriate question text
        """
        candidate_values = [c.value for c in candidates] if candidates else []

        system_prompt = QUESTION_SYSTEM_PROMPT
        user_prompt = QUESTION_USER_PROMPT.format(
            field_name=field.name,
            field_type=field.field_type,
            reason=reason,
            candidates=json.dumps(candidate_values, ensure_ascii=False),
        )

        try:
            response = await self._invoke_llm(
                messages=[
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ],
                operation="generate_question",
            )

            # Track token usage
            self._track_usage(response, "generate_question")

            question_text = response.content.strip()

            return FollowupQuestion(
                field_id=field.field_id,
                question=question_text,
                candidates=tuple(candidate_values),
                reason=reason,
            )

        except Exception as e:
            logger.error(f"LLM question generation failed: {e}", exc_info=True)
            # Fallback: generate a basic question
            fallback_question = f"Please provide the value for '{field.name}'."
            if candidate_values:
                fallback_question += f" Possible values: {', '.join(candidate_values)}"

            return FollowupQuestion(
                field_id=field.field_id,
                question=fallback_question,
                candidates=tuple(candidate_values),
                reason=reason,
            )


# Ensure LangChainValueExtractionAgent satisfies ValueExtractionAgentPort
_agent_check: ValueExtractionAgentPort = LangChainValueExtractionAgent()


# Prompt templates for LLM operations

RESOLVE_SYSTEM_PROMPT = """You are a document value extraction assistant specializing in Japanese documents.
Your task is to select the best candidate value from a list of options.

Consider:
1. Field type and expected format
2. Confidence scores of each candidate
3. Consistency with field context
4. Common patterns in Japanese documents
5. OCR error patterns (similar-looking characters)

Respond with ONLY the index number (0-based) of the best candidate on the first line,
followed by a brief rationale on the next line.

Example response:
0
This candidate has the highest confidence and matches the expected date format."""

RESOLVE_USER_PROMPT = """Select the best candidate for the following field:

Field Name: {field_name}
Field Type: {field_type}

Candidates:
{candidates}

Additional Context:
{context}

Which candidate index (0-based) is the best choice?"""

NORMALIZE_SYSTEM_PROMPT = """You are a value normalization assistant for Japanese documents.
Your task is to convert raw extracted values to standard formats.

Common normalizations:
- Dates: Convert to YYYY-MM-DD format
  - "令和5年1月15日" -> "2023-01-15"
  - "R5.1.15" -> "2023-01-15"
  - "2024/01/15" -> "2024-01-15"
  - "令和6年" -> "2024" (year only)
- Numbers: Remove formatting characters
  - "1,234,567円" -> "1234567"
  - "１２３４" (full-width) -> "1234"
  - "100.50" -> "100.50"
- Phone: Standardize format
  - "090-1234-5678" -> "09012345678" (digits only)
  - "０９０１２３４５６７８" -> "09012345678"
- Postal codes: Format as XXX-XXXX
  - "1234567" -> "123-4567"
  - "〒123-4567" -> "123-4567"
- Names: Preserve original order (Japanese: Last First)
  - Keep kanji names as-is
  - For romaji, keep original order

IMPORTANT:
- Only output the normalized value, nothing else
- Do not add explanations or quotes
- If the value cannot be normalized, return it unchanged"""

NORMALIZE_USER_PROMPT = """Normalize the following value:

Field Name: {field_name}
Field Type: {field_type}
Target Format: {target_format}

Raw Value: {value}

Normalized value:"""

CONFLICT_SYSTEM_PROMPT = """You are a conflict detection assistant for document extraction.
Your task is to determine if multiple value candidates represent conflicting information.

Consider:
1. Semantic meaning - Do the values represent different information?
2. Format variations - "2024-01-15" and "2024/01/15" are NOT conflicts
3. Partial vs. complete - "Yamada" vs "Yamada Taro" may not be a conflict
4. OCR errors - "123456" vs "l23456" is likely an OCR error, not a conflict
5. Full-width/half-width - "１２３" vs "123" are NOT conflicts

Respond with:
- "NO CONFLICT" if the values are equivalent or compatible
- "CONFLICT: [description]" if they truly conflict

Be conservative - only flag true semantic conflicts."""

CONFLICT_USER_PROMPT = """Analyze these candidates for the field "{field_name}" (type: {field_type}):

{candidates}

Do these candidates represent conflicting values?"""

QUESTION_SYSTEM_PROMPT = """You are a user question generation assistant for document extraction.
Your task is to create clear, friendly questions to ask users when automatic extraction cannot resolve ambiguity.

Guidelines:
1. Be specific about what information is needed
2. If candidates are available, present them as options
3. Use polite, professional language (appropriate for both Japanese and English contexts)
4. Keep questions concise and actionable
5. Do not use overly formal or stiff language

IMPORTANT: Only output the question text, nothing else."""

QUESTION_USER_PROMPT = """Generate a clarification question for:

Field Name: {field_name}
Field Type: {field_type}
Reason: {reason}
Available Candidates: {candidates}

Question:"""
