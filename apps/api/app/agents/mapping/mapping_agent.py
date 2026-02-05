"""LangChain-based mapping agent for LLM reasoning.

This agent uses LangChain to leverage LLMs for:
- Semantic understanding of field names
- Disambiguation of multiple mapping candidates
- Generating user-friendly followup questions

The agent is designed to be provider-agnostic (OpenAI, Anthropic, etc.)
through LangChain's unified interface.
"""

import json
import logging
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.config import DEFAULT_MODEL
from app.models.cost import CostTracker, LLMUsage
from app.models.mapping import (
    FollowupQuestion,
    MappingItem,
    SourceField,
    TargetField,
)
from app.services.mapping.domain import MappingCandidate, MappingReason

logger = logging.getLogger(__name__)


class MappingDecisionOutput(BaseModel):
    """Structured output for LLM mapping decision.

    Used with LangChain's structured output feature.
    """

    target_field_id: str | None = Field(
        default=None,
        description="ID of the selected target field, or None if cannot determine",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the decision (0.0 to 1.0)",
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation of the decision",
    )


class FollowupQuestionOutput(BaseModel):
    """Structured output for LLM-generated followup question."""

    question: str = Field(
        ...,
        description="User-friendly question text",
    )
    context: str = Field(
        default="",
        description="Additional context to help the user",
    )


class BatchMappingItem(BaseModel):
    """A single mapping in a batch response."""

    source_field_id: str = Field(
        ...,
        description="ID of the source field",
    )
    target_field_id: str | None = Field(
        default=None,
        description="ID of the matched target field, or None if no match",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this mapping",
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation",
    )


class BatchMappingOutput(BaseModel):
    """Structured output for batch mapping inference."""

    mappings: list[BatchMappingItem] = Field(
        default_factory=list,
        description="List of mapping decisions",
    )


# System prompts for different operations
MAPPING_RESOLUTION_SYSTEM_PROMPT = """You are a document field mapping expert. Your task is to match source fields from one document to target fields in another document.

Given a source field and multiple candidate target fields, determine the best semantic match.

Consider:
1. Semantic meaning of field names (not just string similarity)
2. Field types and expected values
3. Common document field naming patterns
4. Context clues from the field values

If no good match exists, return null for target_field_id with confidence 0.
If you're uncertain between candidates, prefer the lower confidence score."""

QUESTION_GENERATION_SYSTEM_PROMPT = """You are a helpful assistant that generates clear, concise questions to help users resolve ambiguous field mappings.

When a source field could map to multiple target fields, create a question that:
1. Clearly identifies the source field
2. Presents the candidate options
3. Provides relevant context to help the user decide
4. Uses simple, non-technical language

Generate questions in the same language as the field names (detect from context)."""

BATCH_MAPPING_SYSTEM_PROMPT = """You are a document field mapping expert. Your task is to match multiple source fields to their best target fields.

For each source field, find the best matching target field based on:
1. Semantic meaning (not just string similarity)
2. Field types and expected data formats
3. Document structure and context
4. Patterns from any existing mappings provided

Rules:
- Each target field can only be mapped once (no duplicates)
- If no good match exists, set target_field_id to null
- Confidence should reflect how certain you are (0.0-1.0)
- Consider existing mappings as patterns to follow"""


class LangChainMappingAgent:
    """LangChain-based agent for semantic field mapping.

    Uses LangChain to:
    - Resolve ambiguous mapping candidates
    - Generate followup questions for user disambiguation
    - Infer mappings based on semantic understanding

    Tracks token usage for cost estimation via get_cost_tracker().

    Example usage:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        agent = LangChainMappingAgent(llm=llm)

        result = await agent.resolve_mapping(
            source_field=source,
            candidates=candidates,
            target_fields=targets,
        )
    """

    def __init__(
        self,
        llm: object | None = None,
        temperature: float = 0.0,
        model_name: str = DEFAULT_MODEL,
    ) -> None:
        """Initialize the mapping agent.

        Args:
            llm: Optional pre-configured LangChain LLM instance.
                 If None, will be created when needed using model_name.
            temperature: Temperature for LLM responses (default 0 for determinism)
            model_name: Model name to use if llm not provided
        """
        self._llm = llm
        self._temperature = temperature
        self._model_name = model_name
        self._llm_initialized = False
        self._cost_tracker = CostTracker.create(model_name=model_name)

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
            response: Response object (can be Pydantic model from structured output)
            operation: Description of the operation
        """
        input_tokens = 0
        output_tokens = 0

        # For structured output responses, estimate based on response size
        if hasattr(response, "model_dump_json"):
            # Pydantic model - estimate output tokens
            json_str = response.model_dump_json()
            output_tokens = max(1, int(len(json_str) / 4))
            input_tokens = 300  # Typical prompt estimate
        elif hasattr(response, "response_metadata"):
            metadata = response.response_metadata
            if isinstance(metadata, dict):
                token_usage = metadata.get("token_usage", {})
                if token_usage:
                    input_tokens = token_usage.get("prompt_tokens", 0)
                    output_tokens = token_usage.get("completion_tokens", 0)

        usage = LLMUsage.create(
            model=self._model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            agent_name="MappingAgent",
            operation=operation,
        )
        self._cost_tracker = self._cost_tracker.add_llm_usage(usage)

    def _get_llm(self) -> object:
        """Get or create the LLM instance.

        Returns:
            LangChain LLM instance

        Raises:
            ImportError: If langchain-openai is not installed
            ValueError: If OpenAI API key is not configured
        """
        if self._llm is not None:
            return self._llm

        if not self._llm_initialized:
            try:
                from langchain_openai import ChatOpenAI

                from app.config import get_settings

                settings = get_settings()

                if not settings.openai_api_key:
                    raise ValueError(
                        "OpenAI API key not configured. "
                        "Set DARU_OPENAI_API_KEY environment variable."
                    )

                self._llm = ChatOpenAI(
                    model=self._model_name,
                    temperature=self._temperature,
                    api_key=settings.openai_api_key,
                    timeout=settings.openai_timeout_seconds,
                )
                self._llm_initialized = True
                logger.info(
                    "Initialized LangChain ChatOpenAI with model: %s",
                    self._model_name,
                )

            except ImportError as e:
                raise ImportError(
                    "langchain-openai is required for LLM-based mapping. "
                    "Install with: pip install langchain-openai"
                ) from e

        return self._llm

    async def resolve_mapping(
        self,
        source_field: SourceField,
        candidates: tuple[MappingCandidate, ...],
        target_fields: tuple[TargetField, ...],
        context: str | None = None,
    ) -> MappingItem | None:
        """Use LLM to resolve ambiguous mapping candidates.

        Called when multiple candidates have similar scores or
        when semantic understanding is needed.

        Args:
            source_field: The source field to map
            candidates: Potential mapping candidates with scores
            target_fields: Full list of target fields for context
            context: Optional additional context for the LLM

        Returns:
            Resolved MappingItem if LLM can determine the mapping,
            None if mapping cannot be resolved
        """
        if not candidates:
            return None

        try:
            llm = self._get_llm()

            # Build the prompt
            prompt_text = self._build_resolution_prompt(
                source_field=source_field,
                candidates=candidates,
                target_fields=target_fields,
                context=context,
            )

            # Use structured output for reliable parsing
            structured_llm = llm.with_structured_output(MappingDecisionOutput)

            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=MAPPING_RESOLUTION_SYSTEM_PROMPT),
                HumanMessage(content=prompt_text),
            ]

            decision: MappingDecisionOutput = await structured_llm.ainvoke(messages)

            # Track token usage
            self._track_usage(decision, "resolve_mapping")

            logger.debug(
                "LLM mapping decision for '%s': target=%s, confidence=%.2f, reason=%s",
                source_field.name,
                decision.target_field_id,
                decision.confidence,
                decision.reasoning,
            )

            # Validate the decision
            if decision.target_field_id and decision.confidence >= 0.5:
                # Verify target_field_id is valid
                valid_target_ids = {f.id for f in target_fields}
                if decision.target_field_id in valid_target_ids:
                    return MappingItem(
                        id=str(uuid4()),
                        source_field_id=source_field.id,
                        target_field_id=decision.target_field_id,
                        confidence=decision.confidence,
                        reason=MappingReason.SEMANTIC_MATCH.value,
                        is_confirmed=False,
                    )
                else:
                    logger.warning(
                        "LLM returned invalid target_field_id: %s",
                        decision.target_field_id,
                    )

            return None

        except ImportError:
            # LangChain not available, fall back to simple heuristic
            logger.warning(
                "LangChain not available, using fallback for resolve_mapping"
            )
            return self._fallback_resolve_mapping(source_field, candidates)

        except Exception as e:
            logger.error("Error in LLM mapping resolution: %s", str(e))
            # Fall back to best candidate by score
            return self._fallback_resolve_mapping(source_field, candidates)

    def _fallback_resolve_mapping(
        self,
        source_field: SourceField,
        candidates: tuple[MappingCandidate, ...],
    ) -> MappingItem | None:
        """Fallback mapping when LLM is not available.

        Simply selects the highest-scoring candidate.

        Args:
            source_field: Source field to map
            candidates: Mapping candidates

        Returns:
            MappingItem for best candidate, or None if no candidates
        """
        if not candidates:
            return None

        best_candidate = max(candidates, key=lambda c: c.similarity_score)

        if best_candidate.similarity_score >= 0.6:
            return MappingItem(
                id=str(uuid4()),
                source_field_id=source_field.id,
                target_field_id=best_candidate.target_field_id,
                confidence=best_candidate.similarity_score,
                reason=best_candidate.match_reason.value,
                is_confirmed=False,
            )

        return None

    async def generate_question(
        self,
        source_field: SourceField,
        candidates: tuple[MappingCandidate, ...],
        target_fields: tuple[TargetField, ...],
    ) -> FollowupQuestion:
        """Generate a followup question for user disambiguation.

        Called when the agent cannot confidently resolve a mapping
        and needs user input.

        Args:
            source_field: The source field that needs mapping
            candidates: Potential mapping candidates
            target_fields: Target fields for building question context

        Returns:
            FollowupQuestion for the user to answer
        """
        # Build target ID to field mapping
        target_id_to_field = {f.id: f for f in target_fields}
        candidate_names = [
            target_id_to_field.get(c.target_field_id, TargetField(id=c.target_field_id, name=c.target_field_id)).name
            for c in candidates
        ]

        try:
            llm = self._get_llm()

            # Build prompt for question generation
            prompt_text = self._build_question_prompt(
                source_field=source_field,
                candidates=candidates,
                target_fields=target_fields,
            )

            structured_llm = llm.with_structured_output(FollowupQuestionOutput)

            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=QUESTION_GENERATION_SYSTEM_PROMPT),
                HumanMessage(content=prompt_text),
            ]

            output: FollowupQuestionOutput = await structured_llm.ainvoke(messages)

            # Track token usage
            self._track_usage(output, "generate_question")

            logger.debug(
                "Generated question for '%s': %s",
                source_field.name,
                output.question,
            )

            return FollowupQuestion(
                id=str(uuid4()),
                question=output.question,
                source_field_id=source_field.id,
                candidate_target_ids=tuple(c.target_field_id for c in candidates),
                context=output.context or None,
            )

        except Exception as e:
            logger.warning(
                "Error generating LLM question, using fallback: %s", str(e)
            )
            # Fallback: generate a simple question without LLM
            return FollowupQuestion(
                id=str(uuid4()),
                question=f"Which target field should '{source_field.name}' map to?",
                source_field_id=source_field.id,
                candidate_target_ids=tuple(c.target_field_id for c in candidates),
                context=f"Possible options: {', '.join(candidate_names)}",
            )

    async def infer_mappings_batch(
        self,
        source_fields: tuple[SourceField, ...],
        target_fields: tuple[TargetField, ...],
        existing_mappings: tuple[MappingItem, ...] = (),
    ) -> tuple[MappingItem, ...]:
        """Use LLM to infer mappings for a batch of fields.

        Can leverage patterns from existing mappings to improve
        inference quality.

        Args:
            source_fields: Source fields to map
            target_fields: Available target fields
            existing_mappings: Already-confirmed mappings for context

        Returns:
            Tuple of inferred MappingItems
        """
        if not source_fields or not target_fields:
            return ()

        try:
            llm = self._get_llm()

            # Build prompt for batch mapping
            prompt_text = self._build_batch_prompt(
                source_fields=source_fields,
                target_fields=target_fields,
                existing_mappings=existing_mappings,
            )

            structured_llm = llm.with_structured_output(BatchMappingOutput)

            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=BATCH_MAPPING_SYSTEM_PROMPT),
                HumanMessage(content=prompt_text),
            ]

            output: BatchMappingOutput = await structured_llm.ainvoke(messages)

            # Track token usage
            self._track_usage(output, "infer_mappings_batch")

            logger.debug(
                "Batch mapping returned %d results for %d source fields",
                len(output.mappings),
                len(source_fields),
            )

            # Convert to MappingItems, validating target IDs
            valid_target_ids = {f.id for f in target_fields}
            used_target_ids = {m.target_field_id for m in existing_mappings}
            source_id_set = {f.id for f in source_fields}

            results: list[MappingItem] = []
            for mapping in output.mappings:
                # Validate source and target IDs
                if mapping.source_field_id not in source_id_set:
                    logger.warning(
                        "LLM returned invalid source_field_id: %s",
                        mapping.source_field_id,
                    )
                    continue

                if mapping.target_field_id is None:
                    continue

                if mapping.target_field_id not in valid_target_ids:
                    logger.warning(
                        "LLM returned invalid target_field_id: %s",
                        mapping.target_field_id,
                    )
                    continue

                # Skip if target already used
                if mapping.target_field_id in used_target_ids:
                    logger.debug(
                        "Target %s already mapped, skipping",
                        mapping.target_field_id,
                    )
                    continue

                # Only include confident mappings
                if mapping.confidence >= 0.5:
                    results.append(
                        MappingItem(
                            id=str(uuid4()),
                            source_field_id=mapping.source_field_id,
                            target_field_id=mapping.target_field_id,
                            confidence=mapping.confidence,
                            reason=MappingReason.LLM_INFERENCE.value,
                            is_confirmed=False,
                        )
                    )
                    used_target_ids.add(mapping.target_field_id)

            return tuple(results)

        except ImportError:
            logger.warning(
                "LangChain not available, using fallback for batch mapping"
            )
            return ()

        except Exception as e:
            logger.error("Error in LLM batch mapping: %s", str(e))
            return ()

    def _build_resolution_prompt(
        self,
        source_field: SourceField,
        candidates: tuple[MappingCandidate, ...],
        target_fields: tuple[TargetField, ...],
        context: str | None,
    ) -> str:
        """Build the prompt for mapping resolution.

        Args:
            source_field: Source field to map
            candidates: Mapping candidates
            target_fields: All target fields for context
            context: Additional context

        Returns:
            Formatted prompt string
        """
        target_id_to_field = {f.id: f for f in target_fields}

        candidate_descriptions = []
        for c in candidates:
            target = target_id_to_field.get(c.target_field_id)
            if target:
                desc = f"  - ID: {target.id}, Name: \"{target.name}\""
                if target.field_type:
                    desc += f", Type: {target.field_type}"
                desc += f", Similarity Score: {c.similarity_score:.2f}"
                candidate_descriptions.append(desc)

        prompt = f"""Source Field to Map:
  - ID: {source_field.id}
  - Name: "{source_field.name}"
  - Type: {source_field.field_type or 'unknown'}
  - Current Value: {json.dumps(source_field.value) if source_field.value else 'empty'}

Candidate Target Fields:
{chr(10).join(candidate_descriptions)}

{f'Additional Context: {context}' if context else ''}

Based on semantic meaning, which target field best matches the source field?
Return the target_field_id, your confidence (0.0-1.0), and brief reasoning."""

        return prompt

    def _build_question_prompt(
        self,
        source_field: SourceField,
        candidates: tuple[MappingCandidate, ...],
        target_fields: tuple[TargetField, ...],
    ) -> str:
        """Build the prompt for question generation.

        Args:
            source_field: Source field needing disambiguation
            candidates: Mapping candidates
            target_fields: Target fields for context

        Returns:
            Formatted prompt string
        """
        target_id_to_field = {f.id: f for f in target_fields}

        candidate_info = []
        for c in candidates:
            target = target_id_to_field.get(c.target_field_id)
            if target:
                info = {"id": target.id, "name": target.name}
                if target.field_type:
                    info["type"] = target.field_type
                candidate_info.append(info)

        prompt = f"""Generate a question to help the user choose the correct mapping.

Source Field:
  - Name: "{source_field.name}"
  - Value: {json.dumps(source_field.value) if source_field.value else 'empty'}

Candidate Target Fields:
{json.dumps(candidate_info, indent=2, ensure_ascii=False)}

Create a clear, helpful question asking which target field this source should map to."""

        return prompt

    def _build_batch_prompt(
        self,
        source_fields: tuple[SourceField, ...],
        target_fields: tuple[TargetField, ...],
        existing_mappings: tuple[MappingItem, ...],
    ) -> str:
        """Build the prompt for batch mapping inference.

        Args:
            source_fields: Source fields to map
            target_fields: Available target fields
            existing_mappings: Existing mappings for context

        Returns:
            Formatted prompt string
        """
        source_info = [
            {
                "id": f.id,
                "name": f.name,
                "type": f.field_type,
                "value": f.value,
            }
            for f in source_fields
        ]

        target_info = [
            {
                "id": f.id,
                "name": f.name,
                "type": f.field_type,
                "required": f.is_required,
            }
            for f in target_fields
        ]

        # Get already mapped target IDs
        mapped_target_ids = {m.target_field_id for m in existing_mappings}

        # Format existing mappings as examples
        existing_examples = []
        for m in existing_mappings[:5]:  # Limit examples
            src = next((f for f in source_fields if f.id == m.source_field_id), None)
            tgt = next((f for f in target_fields if f.id == m.target_field_id), None)
            if src and tgt:
                existing_examples.append(
                    f'  - "{src.name}" -> "{tgt.name}"'
                )

        prompt = f"""Map each source field to the best matching target field.

Source Fields:
{json.dumps(source_info, indent=2, ensure_ascii=False)}

Target Fields:
{json.dumps(target_info, indent=2, ensure_ascii=False)}

Already Mapped (do not reuse these target fields):
{json.dumps(list(mapped_target_ids), ensure_ascii=False)}

{f"Existing Mapping Examples:{chr(10)}{chr(10).join(existing_examples)}" if existing_examples else ""}

For each source field, provide:
- source_field_id: the source field's ID
- target_field_id: the best matching target's ID (or null if no match)
- confidence: how confident you are (0.0-1.0)
- reasoning: brief explanation"""

        return prompt
