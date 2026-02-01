"""Port interfaces for the Mapping service (Clean Architecture).

These protocols define the boundaries between the domain layer
and external adapters. Following dependency inversion principle,
the domain depends on abstractions, not concrete implementations.
"""

from typing import Protocol

from app.models.mapping import (
    FollowupQuestion,
    MappingItem,
    SourceField,
    TargetField,
)
from app.services.mapping.domain import MappingCandidate


class StringMatcherPort(Protocol):
    """Port for string similarity matching.

    Implementations should handle:
    - Fast string similarity computation
    - Fuzzy matching with configurable thresholds
    - Batch processing for performance

    Example implementations:
    - RapidFuzzAdapter: Uses rapidfuzz library for high-performance fuzzy matching
    - LevenshteinAdapter: Uses python-Levenshtein
    """

    def compute_similarity(
        self,
        source: str,
        target: str,
    ) -> float:
        """Compute similarity score between two strings.

        Args:
            source: Source string to compare
            target: Target string to compare against

        Returns:
            Similarity score from 0.0 (no match) to 1.0 (exact match)
        """
        ...

    def find_matches(
        self,
        source: str,
        targets: tuple[str, ...],
        threshold: float = 0.6,
        limit: int = 5,
    ) -> tuple[tuple[str, float], ...]:
        """Find best matching strings from a list of targets.

        Args:
            source: Source string to match
            targets: Tuple of target strings to search
            threshold: Minimum similarity score to include (default 0.6)
            limit: Maximum number of matches to return (default 5)

        Returns:
            Tuple of (target_string, similarity_score) pairs,
            sorted by score descending
        """
        ...

    def batch_find_matches(
        self,
        sources: tuple[str, ...],
        targets: tuple[str, ...],
        threshold: float = 0.6,
    ) -> dict[str, tuple[tuple[str, float], ...]]:
        """Find matches for multiple source strings.

        Args:
            sources: Tuple of source strings to match
            targets: Tuple of target strings to search
            threshold: Minimum similarity score to include

        Returns:
            Dictionary mapping source strings to their matches
        """
        ...


class MappingAgentPort(Protocol):
    """Port for LLM-based mapping reasoning.

    Implementations should handle:
    - Semantic understanding of field names
    - Disambiguation of multiple candidates
    - Generating user-friendly followup questions

    The agent is called when deterministic matching is insufficient:
    - Multiple high-confidence candidates exist
    - No candidates meet the confidence threshold
    - Field names require semantic interpretation

    Example implementations:
    - LangChainMappingAgent: Uses LangChain with OpenAI/Anthropic
    - LocalLLMAgent: Uses local models like Ollama
    """

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
        ...

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
        ...

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
        ...


class TemplateHistoryPort(Protocol):
    """Port for accessing template mapping history.

    Implementations should handle:
    - Retrieving historical mappings for similar templates
    - Learning from user corrections

    Example implementations:
    - SupabaseTemplateHistory: Uses Supabase for storage
    - InMemoryTemplateHistory: For testing/development
    """

    async def get_historical_mappings(
        self,
        template_ids: tuple[str, ...],
        source_field_names: tuple[str, ...],
    ) -> dict[str, str]:
        """Retrieve historical mappings from similar templates.

        Args:
            template_ids: Template IDs to search for history
            source_field_names: Source field names to look up

        Returns:
            Dictionary mapping source_field_name to target_field_id
            for previously successful mappings
        """
        ...

    async def record_mapping(
        self,
        template_id: str,
        source_field_name: str,
        target_field_id: str,
        was_corrected: bool = False,
    ) -> None:
        """Record a mapping for future reference.

        Args:
            template_id: Template identifier
            source_field_name: Name of the source field
            target_field_id: ID of the target field
            was_corrected: Whether this was a user correction
        """
        ...
