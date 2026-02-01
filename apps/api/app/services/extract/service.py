"""Extract service for value extraction coordination.

This is the main service that coordinates value extraction:
1. Try native PDF text extraction first (deterministic)
2. Fall back to OCR if needed (deterministic)
3. Use ValueExtractionAgent for ambiguity resolution (LLM-assisted)

Service vs Agent:
- This is a Service (deterministic coordination logic)
- It delegates to OcrService (deterministic) and ValueExtractionAgent (LLM)

Following Clean Architecture:
- Depends on Port interfaces, not concrete implementations
- Coordinates the extraction workflow
- Returns immutable result objects

Strategy Support:
- LOCAL_ONLY: Native text + OCR only, no LLM normalization/resolution
- LLM_ONLY: LLM extracts and normalizes all values
- HYBRID: Native/OCR first, LLM for normalization and conflicts (default)
- LLM_WITH_LOCAL_FALLBACK: LLM first, fall back to native/OCR on failure
"""

import logging
from uuid import uuid4

from app.models.common import BBox
from app.models.extract.models import (
    ExtractError,
    ExtractErrorCode,
    ExtractField,
    ExtractRequest,
    ExtractResult,
    Extraction,
    ExtractionSource,
    FollowupQuestion,
    OcrRequest,
    PageArtifact,
)
from app.models.processing_strategy import (
    DEFAULT_STRATEGY,
    ProcessingStrategy,
    StrategyConfig,
)
from app.services.extract.domain.models import (
    EvidenceKind,
    ExtractionEvidence,
    NativeTextResult,
    OcrResult,
    ValueCandidate,
)
from app.services.extract.ports import (
    NativeTextExtractorPort,
    OcrServicePort,
    ValueExtractionAgentPort,
)

logger = logging.getLogger(__name__)


class ExtractService:
    """Application service for value extraction.

    Coordinates the extraction pipeline:
    1. Native PDF text extraction (fast, high confidence)
    2. OCR for missing/low-confidence regions (slower, medium confidence)
    3. LLM agent for ambiguity resolution (slow, reasoning-based)

    Supports different processing strategies:
    - LOCAL_ONLY: Native text + OCR only, no LLM
    - LLM_ONLY: LLM extracts and normalizes all values
    - HYBRID: Native/OCR first, LLM for normalization (default)
    - LLM_WITH_LOCAL_FALLBACK: LLM first, native/OCR fallback

    Example usage:
        native_extractor = PdfPlumberAdapter()
        ocr_service = PaddleOcrAdapter()
        agent = LangChainValueExtractionAgent(llm_client)

        # Default hybrid mode
        service = ExtractService(native_extractor, ocr_service, agent)

        # Local-only mode (no LLM costs)
        from app.models.processing_strategy import FAST_LOCAL_STRATEGY
        service = ExtractService(
            native_extractor, ocr_service, None,
            strategy_config=FAST_LOCAL_STRATEGY,
        )

        request = ExtractRequest(
            document_ref="/uploads/doc.pdf",
            fields=(ExtractField(field_id="name", ...),),
        )
        result = await service.extract(request)
    """

    def __init__(
        self,
        native_extractor: NativeTextExtractorPort,
        ocr_service: OcrServicePort,
        extraction_agent: ValueExtractionAgentPort | None,
        strategy_config: StrategyConfig | None = None,
    ) -> None:
        """Initialize the extract service with adapters.

        Args:
            native_extractor: Adapter for native PDF text extraction
            ocr_service: Adapter for OCR processing
            extraction_agent: Agent for LLM-assisted extraction (optional for LOCAL_ONLY)
            strategy_config: Strategy configuration (defaults to HYBRID)
        """
        self._native_extractor = native_extractor
        self._ocr_service = ocr_service
        self._extraction_agent = extraction_agent
        self._strategy = strategy_config or DEFAULT_STRATEGY

        # Validate configuration
        if self._strategy.should_use_llm() and self._extraction_agent is None:
            if self._strategy.strategy == ProcessingStrategy.LLM_ONLY:
                raise ValueError(
                    "LLM_ONLY strategy requires an extraction_agent, "
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

    def with_strategy(self, strategy: StrategyConfig) -> "ExtractService":
        """Create a new service instance with a different strategy.

        Returns a new instance with the specified strategy, preserving
        all other configuration. Follows immutable pattern.

        Args:
            strategy: New strategy configuration to use

        Returns:
            New ExtractService instance with updated strategy
        """
        return ExtractService(
            native_extractor=self._native_extractor,
            ocr_service=self._ocr_service,
            extraction_agent=self._extraction_agent,
            strategy_config=strategy,
        )

    async def extract(
        self,
        request: ExtractRequest,
        strategy_override: StrategyConfig | None = None,
    ) -> ExtractResult:
        """Extract values from a document.

        Extraction behavior varies based on strategy:

        HYBRID/LOCAL_ONLY:
        1. Native PDF text (fastest, most reliable)
        2. OCR (if native text insufficient)
        3. LLM agent for normalization/resolution (HYBRID only)

        LLM_ONLY:
        1. LLM extracts values directly from document

        LLM_WITH_LOCAL_FALLBACK:
        1. Try LLM extraction first
        2. Fall back to native/OCR on failure

        Args:
            request: Extraction request with document and field definitions
            strategy_override: Optional strategy override for this request

        Returns:
            ExtractResult with extractions, evidence, and any issues
        """
        # Resolve effective strategy
        effective_strategy = self._resolve_strategy(
            getattr(request, 'options', None),
            strategy_override,
        )

        # Derive use_ocr/use_llm from strategy if not explicitly set in request
        use_ocr = request.use_ocr if hasattr(request, 'use_ocr') else True
        use_llm = request.use_llm if hasattr(request, 'use_llm') else effective_strategy.should_use_llm()

        # Override based on strategy
        if effective_strategy.strategy == ProcessingStrategy.LOCAL_ONLY:
            use_llm = False
        elif effective_strategy.strategy == ProcessingStrategy.LLM_ONLY:
            use_llm = True
            # In LLM_ONLY, we skip local extraction steps

        logger.info(
            f"Extracting values with strategy: {effective_strategy.strategy.value}, "
            f"use_ocr={use_ocr}, use_llm={use_llm}"
        )

        extractions: list[Extraction] = []
        all_evidence: list[ExtractionEvidence] = []
        ocr_requests: list[OcrRequest] = []
        followup_questions: list[FollowupQuestion] = []
        errors: list[ExtractError] = []

        # Build artifact lookup by page
        artifacts_by_page = self._build_artifact_lookup(request.artifacts)

        for field in request.fields:
            try:
                result = await self._extract_field(
                    document_ref=request.document_ref,
                    field=field,
                    artifacts_by_page=artifacts_by_page,
                    use_ocr=use_ocr,
                    use_llm=use_llm,
                    confidence_threshold=request.confidence_threshold,
                    strategy=effective_strategy,
                )

                if result.extraction is not None:
                    extractions.append(result.extraction)
                all_evidence.extend(result.evidence)
                ocr_requests.extend(result.ocr_requests)
                followup_questions.extend(result.followup_questions)
                if result.error is not None:
                    errors.append(result.error)

            except Exception as e:
                errors.append(
                    ExtractError(
                        field_id=field.field_id,
                        code=ExtractErrorCode.INVALID_FIELD,
                        message=f"Extraction failed: {str(e)}",
                    )
                )

        return ExtractResult(
            document_ref=request.document_ref,
            success=len(errors) == 0,
            extractions=tuple(extractions),
            evidence=tuple(all_evidence),
            ocr_requests=tuple(ocr_requests),
            followup_questions=tuple(followup_questions),
            errors=tuple(errors),
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

    def _build_artifact_lookup(
        self, artifacts: tuple[PageArtifact, ...]
    ) -> dict[int, PageArtifact]:
        """Build a lookup dictionary of artifacts by page number."""
        return {artifact.page: artifact for artifact in artifacts}

    async def _extract_field(
        self,
        document_ref: str,
        field: ExtractField,
        artifacts_by_page: dict[int, PageArtifact],
        use_ocr: bool,
        use_llm: bool,
        confidence_threshold: float,
        strategy: StrategyConfig | None = None,
    ) -> "_FieldExtractionResult":
        """Extract value for a single field.

        Follows the extraction pipeline based on strategy:

        LOCAL_ONLY/HYBRID (local-first):
        1. Try native text extraction
        2. If insufficient, try OCR
        3. If ambiguous, use LLM agent (HYBRID only)

        LLM_ONLY/LLM_WITH_LOCAL_FALLBACK (LLM-first):
        1. Try LLM extraction first
        2. Fall back to native/OCR on failure (LLM_WITH_LOCAL_FALLBACK only)

        Args:
            document_ref: Reference to the document
            field: Field definition
            artifacts_by_page: Page images for OCR
            use_ocr: Whether to use OCR
            use_llm: Whether to use LLM
            confidence_threshold: Minimum confidence
            strategy: Strategy configuration

        Returns:
            Field extraction result with extraction/evidence/errors
        """
        effective_strategy = strategy or self._strategy
        evidence: list[ExtractionEvidence] = []
        candidates: list[ValueCandidate] = []
        ocr_requests: list[OcrRequest] = []
        followup_questions: list[FollowupQuestion] = []

        # For LLM-first strategies, try LLM extraction first
        if effective_strategy.is_llm_first() and self._extraction_agent is not None:
            try:
                return await self._extract_field_llm_first(
                    document_ref=document_ref,
                    field=field,
                    artifacts_by_page=artifacts_by_page,
                    confidence_threshold=confidence_threshold,
                    strategy=effective_strategy,
                )
            except Exception as e:
                if effective_strategy.should_fallback_on_error():
                    logger.warning(f"LLM extraction failed, falling back to local: {e}")
                    # Continue with local extraction below
                else:
                    raise

        # Local-first extraction (LOCAL_ONLY, HYBRID, or fallback)
        # Step 1: Try native PDF text extraction
        native_result = await self._try_native_extraction(
            document_ref=document_ref,
            field=field,
        )

        if native_result is not None:
            native_evidence = self._create_evidence(
                kind=EvidenceKind.NATIVE_TEXT,
                page=field.page,
                bbox=field.bbox,
                text=native_result.full_text,
                confidence=0.95,  # Native text is high confidence
            )
            evidence.append(native_evidence)

            if native_result.full_text.strip():
                candidates.append(
                    ValueCandidate(
                        value=native_result.full_text.strip(),
                        confidence=0.95,
                        rationale="Extracted from native PDF text layer",
                        evidence_refs=(native_evidence.id,),
                    )
                )

        # Step 2: Try OCR if enabled and native extraction insufficient
        if use_ocr and len(candidates) == 0:
            ocr_result = await self._try_ocr_extraction(
                field=field,
                artifacts_by_page=artifacts_by_page,
            )

            if ocr_result is not None:
                ocr_evidence = self._create_evidence(
                    kind=EvidenceKind.OCR,
                    page=field.page,
                    bbox=field.bbox,
                    text=ocr_result.full_text,
                    confidence=ocr_result.avg_confidence,
                )
                evidence.append(ocr_evidence)

                if ocr_result.full_text.strip():
                    candidates.append(
                        ValueCandidate(
                            value=ocr_result.full_text.strip(),
                            confidence=ocr_result.avg_confidence,
                            rationale=f"Extracted via OCR ({ocr_result.engine})",
                            evidence_refs=(ocr_evidence.id,),
                        )
                    )
            elif field.bbox is not None:
                # Request OCR for this region
                ocr_requests.append(
                    OcrRequest(
                        field_id=field.field_id,
                        page=field.page,
                        bbox=field.bbox,
                        reason="Native text extraction found no content",
                    )
                )

        # Step 3: Use LLM for ambiguity resolution if needed (HYBRID only)
        if use_llm and len(candidates) > 1 and self._extraction_agent is not None:
            best_candidate = await self._resolve_with_llm(
                field=field,
                candidates=tuple(candidates),
            )
            if best_candidate is not None:
                llm_evidence = self._create_evidence(
                    kind=EvidenceKind.LLM,
                    page=field.page,
                    bbox=field.bbox,
                    text=best_candidate.value,
                    confidence=best_candidate.confidence,
                )
                evidence.append(llm_evidence)
                candidates = [best_candidate]

        # Step 4: Check for conflicts (only if LLM available)
        conflict_detected = False
        if use_llm and len(candidates) > 1 and self._extraction_agent is not None:
            conflict_detected, _ = await self._extraction_agent.detect_conflicts(
                field=field,
                candidates=tuple(candidates),
            )

        # Step 5: Build result
        if len(candidates) == 0:
            # No value found - may need follow-up question
            if use_llm and self._extraction_agent is not None:
                question = await self._extraction_agent.generate_question(
                    field=field,
                    reason="No text found in specified region",
                    candidates=None,
                )
                followup_questions.append(question)

            return _FieldExtractionResult(
                extraction=None,
                evidence=evidence,
                ocr_requests=ocr_requests,
                followup_questions=followup_questions,
                error=ExtractError(
                    field_id=field.field_id,
                    code=ExtractErrorCode.NO_TEXT_FOUND,
                    message="No text found for field",
                ),
            )

        # Select best candidate
        best = max(candidates, key=lambda c: c.confidence)

        # Normalize value if using LLM and agent is available
        normalized_value = best.value
        if use_llm and self._extraction_agent is not None:
            try:
                normalized_value = await self._extraction_agent.normalize_value(
                    field=field,
                    value=best.value,
                )
            except ValueError:
                pass  # Keep original if normalization fails

        # Determine source
        source = self._determine_source(best, evidence)

        # Check if review is needed
        needs_review = (
            best.confidence < confidence_threshold or conflict_detected
        )

        extraction = Extraction(
            field_id=field.field_id,
            value=best.value,
            normalized_value=normalized_value if normalized_value != best.value else None,
            confidence=best.confidence,
            source=source,
            evidence=tuple(evidence),
            needs_review=needs_review,
            conflict_detected=conflict_detected,
        )

        return _FieldExtractionResult(
            extraction=extraction,
            evidence=evidence,
            ocr_requests=ocr_requests,
            followup_questions=followup_questions,
            error=None,
        )

    async def _extract_field_llm_first(
        self,
        document_ref: str,
        field: ExtractField,
        artifacts_by_page: dict[int, PageArtifact],
        confidence_threshold: float,
        strategy: StrategyConfig,
    ) -> "_FieldExtractionResult":
        """Extract value using LLM-first approach.

        Used for LLM_ONLY and LLM_WITH_LOCAL_FALLBACK strategies.
        The LLM agent directly extracts and normalizes the value.

        Args:
            document_ref: Reference to the document
            field: Field definition
            artifacts_by_page: Page images for LLM analysis
            confidence_threshold: Minimum confidence
            strategy: Strategy configuration

        Returns:
            Field extraction result

        Raises:
            RuntimeError: If LLM extraction fails and no fallback
        """
        if self._extraction_agent is None:
            raise RuntimeError("LLM-first extraction requires an extraction agent")

        evidence: list[ExtractionEvidence] = []
        followup_questions: list[FollowupQuestion] = []

        # For LLM_ONLY, we let the agent handle everything
        # This is a simplified implementation - a real one would pass
        # the document/page image to the agent for visual analysis

        # Try to get some context from native extraction first
        # (even in LLM_ONLY, we can use this as input context)
        context_text = ""
        native_result = await self._try_native_extraction(
            document_ref=document_ref,
            field=field,
        )
        if native_result is not None and native_result.full_text.strip():
            context_text = native_result.full_text.strip()

        # Create a candidate from the context if available
        if context_text:
            # Let LLM normalize the value
            try:
                normalized_value = await self._extraction_agent.normalize_value(
                    field=field,
                    value=context_text,
                )

                llm_evidence = self._create_evidence(
                    kind=EvidenceKind.LLM,
                    page=field.page,
                    bbox=field.bbox,
                    text=normalized_value,
                    confidence=0.85,  # LLM normalization confidence
                )
                evidence.append(llm_evidence)

                extraction = Extraction(
                    field_id=field.field_id,
                    value=context_text,
                    normalized_value=normalized_value if normalized_value != context_text else None,
                    confidence=0.85,
                    source=ExtractionSource.LLM,
                    evidence=tuple(evidence),
                    needs_review=0.85 < confidence_threshold,
                    conflict_detected=False,
                )

                return _FieldExtractionResult(
                    extraction=extraction,
                    evidence=evidence,
                    ocr_requests=[],
                    followup_questions=followup_questions,
                    error=None,
                )
            except Exception as e:
                logger.warning(f"LLM normalization failed: {e}")
                # Fall through to generate a question

        # No value found or LLM failed - generate follow-up question
        question = await self._extraction_agent.generate_question(
            field=field,
            reason="LLM extraction could not determine value",
            candidates=None,
        )
        followup_questions.append(question)

        return _FieldExtractionResult(
            extraction=None,
            evidence=evidence,
            ocr_requests=[],
            followup_questions=followup_questions,
            error=ExtractError(
                field_id=field.field_id,
                code=ExtractErrorCode.NO_TEXT_FOUND,
                message="LLM could not extract value for field",
            ),
        )

    async def _try_native_extraction(
        self,
        document_ref: str,
        field: ExtractField,
    ) -> NativeTextResult | None:
        """Attempt native PDF text extraction.

        Args:
            document_ref: Reference to the document
            field: Field definition

        Returns:
            NativeTextResult if successful, None otherwise
        """
        try:
            return await self._native_extractor.extract_text(
                document_ref=document_ref,
                page=field.page,
                region=field.bbox,
            )
        except Exception:
            return None

    async def _try_ocr_extraction(
        self,
        field: ExtractField,
        artifacts_by_page: dict[int, PageArtifact],
    ) -> OcrResult | None:
        """Attempt OCR extraction.

        Args:
            field: Field definition
            artifacts_by_page: Page images for OCR

        Returns:
            OcrResult if successful, None otherwise
        """
        artifact = artifacts_by_page.get(field.page)
        if artifact is None:
            return None

        try:
            # NOTE: In production, load image from artifact.image_ref
            # This stub returns None - actual implementation would:
            # 1. Load image bytes from storage
            # 2. Call OCR service with region
            return None
        except Exception:
            return None

    async def _resolve_with_llm(
        self,
        field: ExtractField,
        candidates: tuple[ValueCandidate, ...],
    ) -> ValueCandidate | None:
        """Use LLM to resolve ambiguity between candidates.

        Args:
            field: Field definition
            candidates: Value candidates to resolve

        Returns:
            Best candidate selected by LLM
        """
        try:
            return await self._extraction_agent.resolve_candidates(
                field=field,
                candidates=candidates,
            )
        except Exception:
            return None

    def _create_evidence(
        self,
        kind: EvidenceKind,
        page: int,
        bbox: BBox | None,
        text: str | None,
        confidence: float,
    ) -> ExtractionEvidence:
        """Create an evidence record."""
        return ExtractionEvidence(
            id=f"ev-{uuid4().hex[:8]}",
            kind=kind,
            page=page,
            bbox=bbox,
            text=text,
            confidence=confidence,
        )

    def _determine_source(
        self,
        candidate: ValueCandidate,
        evidence: list[ExtractionEvidence],
    ) -> ExtractionSource:
        """Determine the source of extraction from evidence."""
        if not candidate.evidence_refs:
            return ExtractionSource.NATIVE_TEXT

        for ev in evidence:
            if ev.id in candidate.evidence_refs:
                if ev.kind == EvidenceKind.NATIVE_TEXT:
                    return ExtractionSource.NATIVE_TEXT
                elif ev.kind == EvidenceKind.OCR:
                    return ExtractionSource.OCR
                elif ev.kind == EvidenceKind.LLM:
                    return ExtractionSource.LLM

        return ExtractionSource.NATIVE_TEXT


class _FieldExtractionResult:
    """Internal result for single field extraction.

    Used to collect results from field extraction before
    aggregating into the final ExtractResult.
    """

    def __init__(
        self,
        extraction: Extraction | None,
        evidence: list[ExtractionEvidence],
        ocr_requests: list[OcrRequest],
        followup_questions: list[FollowupQuestion],
        error: ExtractError | None,
    ) -> None:
        self.extraction = extraction
        self.evidence = evidence
        self.ocr_requests = ocr_requests
        self.followup_questions = followup_questions
        self.error = error
