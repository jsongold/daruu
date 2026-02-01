"""Mapping service for Source-Target field correspondence.

This is a Service that orchestrates:
1. Deterministic string matching (via StringMatcherPort)
2. LLM-based reasoning for ambiguous cases (via MappingAgentPort)
3. User rule application and template history lookup

Service vs Agent:
- This Service handles the overall mapping workflow
- It delegates non-deterministic reasoning to the MappingAgent
- The agent is injected via Protocol for testability/swappability

Strategy Support:
- LOCAL_ONLY: RapidFuzz matching only, no LLM disambiguation
- LLM_ONLY: LLM infers all mappings directly
- HYBRID: Fuzzy match first, then LLM for ambiguous cases (default)
- LLM_WITH_LOCAL_FALLBACK: LLM first, fall back to fuzzy on failure
"""

import logging
from uuid import uuid4

from app.models.mapping import (
    FollowupQuestion,
    MappingItem,
    MappingRequest,
    MappingResult,
    SourceField,
    TargetField,
    UserRule,
)
from app.models.processing_strategy import (
    DEFAULT_STRATEGY,
    ProcessingStrategy,
    StrategyConfig,
)
from app.services.mapping.domain import (
    MappingCandidate,
    MappingReason,
    MappingRule,
)
from app.services.mapping.ports import (
    MappingAgentPort,
    StringMatcherPort,
    TemplateHistoryPort,
)

logger = logging.getLogger(__name__)


class MappingService:
    """Application service for field mapping.

    Coordinates deterministic matching and LLM-based reasoning
    to generate source-to-target field mappings.

    Supports different processing strategies:
    - LOCAL_ONLY: Fuzzy string matching only, no LLM
    - LLM_ONLY: LLM infers all mappings directly
    - HYBRID: Fuzzy match first, LLM resolves ambiguities (default)
    - LLM_WITH_LOCAL_FALLBACK: LLM first, fuzzy fallback on error

    Example usage:
        string_matcher = RapidFuzzAdapter()
        mapping_agent = LangChainMappingAgent()
        template_history = SupabaseTemplateHistory()

        # Default hybrid mode
        service = MappingService(
            string_matcher=string_matcher,
            mapping_agent=mapping_agent,
            template_history=template_history,
        )

        # Local-only mode (no LLM costs)
        from app.models.processing_strategy import FAST_LOCAL_STRATEGY
        service = MappingService(
            string_matcher=string_matcher,
            strategy_config=FAST_LOCAL_STRATEGY,
        )

        request = MappingRequest(
            source_fields=[...],
            target_fields=[...],
        )
        result = await service.map_fields(request)
    """

    def __init__(
        self,
        string_matcher: StringMatcherPort,
        mapping_agent: MappingAgentPort | None = None,
        template_history: TemplateHistoryPort | None = None,
        strategy_config: StrategyConfig | None = None,
    ) -> None:
        """Initialize the mapping service with adapters.

        Args:
            string_matcher: Adapter for string similarity matching
            mapping_agent: Optional adapter for LLM-based reasoning
            template_history: Optional adapter for template history lookup
            strategy_config: Strategy configuration (defaults to HYBRID)
        """
        self._string_matcher = string_matcher
        self._mapping_agent = mapping_agent
        self._template_history = template_history
        self._strategy = strategy_config or DEFAULT_STRATEGY

        # Validate configuration
        if self._strategy.should_use_llm() and self._mapping_agent is None:
            if self._strategy.strategy == ProcessingStrategy.LLM_ONLY:
                raise ValueError(
                    "LLM_ONLY strategy requires a mapping_agent, "
                    "but none was provided. Use LOCAL_ONLY strategy or provide an agent."
                )
            # For HYBRID and LLM_WITH_LOCAL_FALLBACK, we can gracefully degrade
            logger.warning(
                f"Strategy {self._strategy.strategy.value} prefers LLM but no agent provided. "
                "Will use local-only fallback."
            )

    @property
    def strategy(self) -> StrategyConfig:
        """Get the current processing strategy configuration."""
        return self._strategy

    def with_strategy(self, strategy: StrategyConfig) -> "MappingService":
        """Create a new service instance with a different strategy.

        Returns a new instance with the specified strategy, preserving
        all other configuration. Follows immutable pattern.

        Args:
            strategy: New strategy configuration to use

        Returns:
            New MappingService instance with updated strategy
        """
        return MappingService(
            string_matcher=self._string_matcher,
            mapping_agent=self._mapping_agent,
            template_history=self._template_history,
            strategy_config=strategy,
        )

    async def map_fields(
        self,
        request: MappingRequest,
        strategy_override: StrategyConfig | None = None,
    ) -> MappingResult:
        """Generate field mappings from source to target fields.

        Workflow varies based on strategy:

        HYBRID/LOCAL_ONLY:
        1. Apply user-defined rules (highest priority)
        2. Check template history for known mappings
        3. Perform deterministic string matching
        4. Use LLM agent for ambiguous cases (HYBRID only)
        5. Generate followup questions for unresolved mappings

        LLM_ONLY:
        1. Apply user-defined rules (highest priority)
        2. Use LLM to infer all remaining mappings directly

        LLM_WITH_LOCAL_FALLBACK:
        1. Apply user-defined rules (highest priority)
        2. Try LLM for all mappings
        3. Fall back to fuzzy matching on LLM failure

        Args:
            request: Mapping request with source/target fields and options
            strategy_override: Optional strategy override for this request

        Returns:
            MappingResult with mappings, evidence refs, and followup questions
        """
        # Resolve effective strategy
        effective_strategy = self._resolve_strategy(
            request.options if hasattr(request, 'options') else None,
            strategy_override,
        )

        logger.info(f"Mapping fields with strategy: {effective_strategy.strategy.value}")

        mappings: list[MappingItem] = []
        followup_questions: list[FollowupQuestion] = []
        evidence_refs: list[str] = []
        mapped_source_ids: set[str] = set()
        mapped_target_ids: set[str] = set()

        # Step 1: Apply user-defined rules (always, regardless of strategy)
        if request.user_rules:
            rule_mappings = self._apply_user_rules(
                source_fields=request.source_fields,
                target_fields=request.target_fields,
                user_rules=request.user_rules,
            )
            for mapping in rule_mappings:
                mappings.append(mapping)
                mapped_source_ids.add(mapping.source_field_id)
                mapped_target_ids.add(mapping.target_field_id)

        # Step 2: Check template history (always, regardless of strategy)
        if request.template_history and self._template_history:
            history_mappings = await self._apply_template_history(
                source_fields=request.source_fields,
                target_fields=request.target_fields,
                template_ids=request.template_history,
                already_mapped_sources=mapped_source_ids,
            )
            for mapping in history_mappings:
                mappings.append(mapping)
                mapped_source_ids.add(mapping.source_field_id)
                mapped_target_ids.add(mapping.target_field_id)

        # Get remaining unmapped fields
        unmapped_sources = tuple(
            f for f in request.source_fields if f.id not in mapped_source_ids
        )
        available_targets = tuple(
            f for f in request.target_fields if f.id not in mapped_target_ids
        )

        # Process based on strategy
        if effective_strategy.is_llm_first():
            # LLM_ONLY or LLM_WITH_LOCAL_FALLBACK
            llm_result = await self._process_llm_first(
                unmapped_sources=unmapped_sources,
                available_targets=available_targets,
                request=request,
                strategy=effective_strategy,
            )
            mappings.extend(llm_result.mappings)
            followup_questions.extend(llm_result.followup_questions)
            mapped_source_ids.update(m.source_field_id for m in llm_result.mappings)
            mapped_target_ids.update(m.target_field_id for m in llm_result.mappings)
        else:
            # LOCAL_ONLY or HYBRID - use fuzzy matching first
            local_result = await self._process_local_first(
                unmapped_sources=unmapped_sources,
                available_targets=available_targets,
                request=request,
                strategy=effective_strategy,
            )
            mappings.extend(local_result.mappings)
            followup_questions.extend(local_result.followup_questions)
            mapped_source_ids.update(m.source_field_id for m in local_result.mappings)
            mapped_target_ids.update(m.target_field_id for m in local_result.mappings)

        # Calculate unmapped fields
        final_unmapped_sources = tuple(
            f.id for f in request.source_fields if f.id not in mapped_source_ids
        )
        final_unmapped_targets = tuple(
            f.id
            for f in request.target_fields
            if f.id not in mapped_target_ids and f.is_required
        )

        return MappingResult(
            mappings=tuple(mappings),
            evidence_refs=tuple(evidence_refs),
            followup_questions=tuple(followup_questions),
            unmapped_source_fields=final_unmapped_sources,
            unmapped_target_fields=final_unmapped_targets,
        )

    def _resolve_strategy(
        self,
        options: dict | None,
        override: StrategyConfig | None,
    ) -> StrategyConfig:
        """Resolve the effective strategy for a request.

        Priority order:
        1. Explicit override parameter (highest)
        2. Strategy specified in request options
        3. Service default strategy (lowest)

        Args:
            options: Request options dict (may contain "processing_strategy")
            override: Explicit strategy override parameter

        Returns:
            Effective StrategyConfig to use for processing
        """
        if override is not None:
            return override

        if options and "processing_strategy" in options:
            strategy_value = options["processing_strategy"]
            if isinstance(strategy_value, StrategyConfig):
                return strategy_value
            if isinstance(strategy_value, str):
                try:
                    strategy_enum = ProcessingStrategy(strategy_value)
                    return StrategyConfig(strategy=strategy_enum)
                except ValueError:
                    logger.warning(
                        f"Unknown strategy '{strategy_value}', using default"
                    )

        return self._strategy

    async def _process_local_first(
        self,
        unmapped_sources: tuple[SourceField, ...],
        available_targets: tuple[TargetField, ...],
        request: MappingRequest,
        strategy: StrategyConfig,
    ) -> "_MappingStepResult":
        """Process mapping with local fuzzy matching first.

        Used for LOCAL_ONLY and HYBRID strategies.

        Args:
            unmapped_sources: Source fields to map
            available_targets: Available target fields
            request: Original mapping request
            strategy: Strategy configuration

        Returns:
            Mapping step result with mappings and questions
        """
        mappings: list[MappingItem] = []
        followup_questions: list[FollowupQuestion] = []
        mapped_target_ids: set[str] = set()

        for source_field in unmapped_sources:
            if not available_targets:
                break

            # Filter out already-mapped targets
            current_targets = tuple(
                t for t in available_targets if t.id not in mapped_target_ids
            )
            if not current_targets:
                break

            candidates = self._find_candidates(
                source_field=source_field,
                target_fields=current_targets,
            )

            if not candidates:
                continue

            # Check for high-confidence single match
            best_candidate = candidates[0]
            is_clear_winner = (
                best_candidate.similarity_score >= request.confidence_threshold
                and (
                    len(candidates) == 1
                    or candidates[1].similarity_score
                    < best_candidate.similarity_score - 0.15
                )
            )

            if is_clear_winner:
                # Clear winner, create mapping
                mapping = self._create_mapping_from_candidate(
                    source_field=source_field,
                    candidate=best_candidate,
                )
                mappings.append(mapping)
                mapped_target_ids.add(mapping.target_field_id)
            elif strategy.strategy == ProcessingStrategy.HYBRID and self._mapping_agent:
                # Use LLM for ambiguous cases in HYBRID mode
                try:
                    resolved = await self._mapping_agent.resolve_mapping(
                        source_field=source_field,
                        candidates=candidates,
                        target_fields=request.target_fields,
                    )
                    if resolved:
                        mappings.append(resolved)
                        mapped_target_ids.add(resolved.target_field_id)
                    elif request.require_confirmation:
                        question = await self._mapping_agent.generate_question(
                            source_field=source_field,
                            candidates=candidates,
                            target_fields=request.target_fields,
                        )
                        followup_questions.append(question)
                except Exception as e:
                    logger.warning(f"LLM resolution failed: {e}")
                    # In HYBRID, LLM failure is not critical
            elif strategy.strategy == ProcessingStrategy.LOCAL_ONLY:
                # In LOCAL_ONLY, accept best candidate if above threshold
                if best_candidate.similarity_score >= request.confidence_threshold * 0.8:
                    mapping = self._create_mapping_from_candidate(
                        source_field=source_field,
                        candidate=best_candidate,
                    )
                    # Mark as needing review due to ambiguity
                    mapping = MappingItem(
                        id=mapping.id,
                        source_field_id=mapping.source_field_id,
                        target_field_id=mapping.target_field_id,
                        confidence=mapping.confidence * 0.9,  # Reduce confidence
                        reason=MappingReason.FUZZY_MATCH_AMBIGUOUS.value
                        if len(candidates) > 1
                        else mapping.reason,
                        is_confirmed=False,
                    )
                    mappings.append(mapping)
                    mapped_target_ids.add(mapping.target_field_id)

        return _MappingStepResult(
            mappings=tuple(mappings),
            followup_questions=tuple(followup_questions),
        )

    async def _process_llm_first(
        self,
        unmapped_sources: tuple[SourceField, ...],
        available_targets: tuple[TargetField, ...],
        request: MappingRequest,
        strategy: StrategyConfig,
    ) -> "_MappingStepResult":
        """Process mapping with LLM first.

        Used for LLM_ONLY and LLM_WITH_LOCAL_FALLBACK strategies.

        Args:
            unmapped_sources: Source fields to map
            available_targets: Available target fields
            request: Original mapping request
            strategy: Strategy configuration

        Returns:
            Mapping step result with mappings and questions
        """
        mappings: list[MappingItem] = []
        followup_questions: list[FollowupQuestion] = []

        if self._mapping_agent is None:
            if strategy.strategy == ProcessingStrategy.LLM_ONLY:
                raise RuntimeError("LLM_ONLY strategy requires a mapping agent")
            # For LLM_WITH_LOCAL_FALLBACK, fall back to local
            logger.warning("No LLM agent, falling back to local processing")
            return await self._process_local_first(
                unmapped_sources=unmapped_sources,
                available_targets=available_targets,
                request=request,
                strategy=StrategyConfig(strategy=ProcessingStrategy.LOCAL_ONLY),
            )

        try:
            # Try batch inference with LLM
            inferred = await self._mapping_agent.infer_mappings_batch(
                source_fields=unmapped_sources,
                target_fields=available_targets,
                existing_mappings=(),
            )
            mappings.extend(inferred)
        except Exception as e:
            if strategy.should_fallback_on_error():
                logger.warning(f"LLM batch inference failed, falling back: {e}")
                return await self._process_local_first(
                    unmapped_sources=unmapped_sources,
                    available_targets=available_targets,
                    request=request,
                    strategy=StrategyConfig(strategy=ProcessingStrategy.LOCAL_ONLY),
                )
            else:
                raise

        return _MappingStepResult(
            mappings=tuple(mappings),
            followup_questions=tuple(followup_questions),
        )

    def _apply_user_rules(
        self,
        source_fields: tuple[SourceField, ...],
        target_fields: tuple[TargetField, ...],
        user_rules: tuple[UserRule, ...],
    ) -> list[MappingItem]:
        """Apply user-defined mapping rules.

        Args:
            source_fields: Source fields to match
            target_fields: Target fields to match against
            user_rules: User-defined rules to apply

        Returns:
            List of mappings generated from rules
        """
        mappings: list[MappingItem] = []

        for rule in user_rules:
            # Find matching source fields
            matching_sources = [
                f
                for f in source_fields
                if self._pattern_matches(rule.source_pattern, f.name)
            ]
            # Find matching target fields
            matching_targets = [
                f
                for f in target_fields
                if self._pattern_matches(rule.target_pattern, f.name)
            ]

            # Create mappings for matches
            for source in matching_sources:
                for target in matching_targets:
                    mapping = MappingItem(
                        id=str(uuid4()),
                        source_field_id=source.id,
                        target_field_id=target.id,
                        confidence=1.0,  # User rules are fully confident
                        reason=MappingReason.USER_RULE.value,
                        is_confirmed=True,
                    )
                    mappings.append(mapping)
                    break  # One target per source

        return mappings

    def _pattern_matches(self, pattern: str, value: str) -> bool:
        """Check if a pattern matches a value.

        Supports simple wildcard matching with '*'.

        Args:
            pattern: Pattern with optional wildcards
            value: Value to match against

        Returns:
            True if pattern matches value
        """
        # Simple wildcard support
        if pattern == "*":
            return True
        if "*" not in pattern:
            return pattern.lower() == value.lower()

        # Convert to regex-like matching
        parts = pattern.lower().split("*")
        value_lower = value.lower()

        if len(parts) == 2:
            prefix, suffix = parts
            if prefix and suffix:
                return value_lower.startswith(prefix) and value_lower.endswith(suffix)
            elif prefix:
                return value_lower.startswith(prefix)
            elif suffix:
                return value_lower.endswith(suffix)

        return pattern.lower() == value_lower

    async def _apply_template_history(
        self,
        source_fields: tuple[SourceField, ...],
        target_fields: tuple[TargetField, ...],
        template_ids: tuple[str, ...],
        already_mapped_sources: set[str],
    ) -> list[MappingItem]:
        """Apply mappings from template history.

        Args:
            source_fields: Source fields to look up
            target_fields: Available target fields
            template_ids: Template IDs to search history
            already_mapped_sources: Source IDs already mapped (skip these)

        Returns:
            List of mappings from template history
        """
        if not self._template_history:
            return []

        mappings: list[MappingItem] = []
        source_names = tuple(f.name for f in source_fields if f.id not in already_mapped_sources)

        historical = await self._template_history.get_historical_mappings(
            template_ids=template_ids,
            source_field_names=source_names,
        )

        target_id_set = {f.id for f in target_fields}

        for source_field in source_fields:
            if source_field.id in already_mapped_sources:
                continue
            if source_field.name in historical:
                target_id = historical[source_field.name]
                if target_id in target_id_set:
                    mapping = MappingItem(
                        id=str(uuid4()),
                        source_field_id=source_field.id,
                        target_field_id=target_id,
                        confidence=0.9,  # High confidence from history
                        reason=MappingReason.TEMPLATE_HISTORY.value,
                        is_confirmed=False,
                    )
                    mappings.append(mapping)

        return mappings

    def _find_candidates(
        self,
        source_field: SourceField,
        target_fields: tuple[TargetField, ...],
    ) -> tuple[MappingCandidate, ...]:
        """Find mapping candidates using string matching.

        Args:
            source_field: Source field to find matches for
            target_fields: Available target fields to match against

        Returns:
            Tuple of MappingCandidate sorted by score descending
        """
        target_names = tuple(f.name for f in target_fields)
        target_id_map = {f.name: f.id for f in target_fields}

        matches = self._string_matcher.find_matches(
            source=source_field.name,
            targets=target_names,
            threshold=0.4,  # Low threshold to get candidates
            limit=5,
        )

        candidates: list[MappingCandidate] = []
        for target_name, score in matches:
            target_id = target_id_map.get(target_name)
            if target_id:
                reason = (
                    MappingReason.EXACT_MATCH
                    if score >= 0.99
                    else MappingReason.FUZZY_MATCH
                )
                candidate = MappingCandidate(
                    source_field_id=source_field.id,
                    target_field_id=target_id,
                    similarity_score=score,
                    match_reason=reason,
                )
                candidates.append(candidate)

        return tuple(candidates)

    def _create_mapping_from_candidate(
        self,
        source_field: SourceField,
        candidate: MappingCandidate,
    ) -> MappingItem:
        """Create a MappingItem from a confirmed candidate.

        Args:
            source_field: The source field being mapped
            candidate: The confirmed mapping candidate

        Returns:
            MappingItem ready for the result
        """
        return MappingItem(
            id=str(uuid4()),
            source_field_id=source_field.id,
            target_field_id=candidate.target_field_id,
            confidence=candidate.similarity_score,
            reason=candidate.match_reason.value,
            is_confirmed=False,
        )


class _MappingStepResult:
    """Internal result for a mapping processing step.

    Used to collect results from processing steps before
    aggregating into the final MappingResult.
    """

    def __init__(
        self,
        mappings: tuple[MappingItem, ...],
        followup_questions: tuple[FollowupQuestion, ...],
    ) -> None:
        self.mappings = mappings
        self.followup_questions = followup_questions
