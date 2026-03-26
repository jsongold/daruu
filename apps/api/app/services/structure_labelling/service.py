"""Structure/Labelling Service for document structure extraction and field linking.

This service orchestrates:
1. Deterministic structure detection (boxes, tables, text regions)
2. LLM-based label-to-position linking via FieldLabellingAgent

Service vs Agent (per PRD):
- StructureLabellingService: Deterministic orchestration and coordination
- FieldLabellingAgent: LLM reasoning for label-to-bbox linking (optional based on strategy)

Single Writer Responsibility:
- Creates/updates Field objects (name, type, bbox, anchor)
- Creates Evidence(kind=llm_linking) for audit trail

Non-Responsibility:
- Value extraction (Extract service)
- Coordinate adjustment (Adjust service)

Strategy Support:
- LOCAL_ONLY: Structure detection only, no LLM linking
- LLM_ONLY: Skip detection, LLM performs all analysis
- HYBRID: Detect structures, then LLM links labels (default)
- LLM_WITH_LOCAL_FALLBACK: LLM first, fall back to local on failure
"""

import logging
from typing import Any
from uuid import uuid4

from app.models.common import BBox
from app.models.processing_strategy import (
    DEFAULT_STRATEGY,
    ProcessingStrategy,
    StrategyConfig,
)
from app.models.structure_labelling import (
    BoxCandidateInput,
    EvidenceOutput,
    FieldOutput,
    StructureLabellingRequest,
    StructureLabellingResult,
    TableCandidateInput,
    TextBlockInput,
)
from app.services.structure_labelling.domain.models import (
    BoxCandidate,
    EvidenceKind,
    LabelCandidate,
    LinkedField,
    StructureEvidence,
    TableCandidate,
    TableCell,
    TextBlock,
)
from app.services.structure_labelling.ports import (
    FieldLabellingAgentPort,
    PageImageLoaderPort,
    StructureDetectorPort,
)

logger = logging.getLogger(__name__)


class StructureLabellingService:
    """Application service for structure detection and label linking.

    Coordinates PDF structure analysis and LLM-based field labelling
    using injected adapters for detection and agent reasoning.

    Supports different processing strategies:
    - LOCAL_ONLY: Only structure detection, no LLM linking
    - LLM_ONLY: Skip detection, LLM analyzes directly
    - HYBRID: Detect first, then LLM links (default)
    - LLM_WITH_LOCAL_FALLBACK: LLM first, local fallback on error

    Example usage:
        agent = LangChainFieldLabellingAgent(llm_config)
        detector = OpenCVStructureDetector()
        loader = LocalPageImageLoader("/data/artifacts")

        # Default hybrid mode
        service = StructureLabellingService(agent, detector, loader)

        # Local-only mode (no LLM costs)
        from app.models.processing_strategy import FAST_LOCAL_STRATEGY
        service = StructureLabellingService(
            agent, detector, loader,
            strategy_config=FAST_LOCAL_STRATEGY
        )

        request = StructureLabellingRequest(
            document_id="doc-123",
            document_ref="/uploads/doc.pdf",
            page_images=[PageImageInput(page=1, image_ref="/artifacts/page1.png")],
        )
        result = await service.process(request)
    """

    # Confidence threshold below which needs_review flag is set
    REVIEW_CONFIDENCE_THRESHOLD: float = 0.7

    def __init__(
        self,
        field_labelling_agent: FieldLabellingAgentPort | None,
        structure_detector: StructureDetectorPort,
        page_image_loader: PageImageLoaderPort,
        strategy_config: StrategyConfig | None = None,
    ) -> None:
        """Initialize the service with required adapters.

        Args:
            field_labelling_agent: LLM agent for label-to-bbox linking
                (optional for LOCAL_ONLY strategy)
            structure_detector: Deterministic structure detector
            page_image_loader: Loader for page images
            strategy_config: Strategy configuration (defaults to HYBRID)
        """
        self._agent = field_labelling_agent
        self._detector = structure_detector
        self._loader = page_image_loader
        self._strategy = strategy_config or DEFAULT_STRATEGY

        # Validate configuration
        if self._strategy.should_use_llm() and self._agent is None:
            raise ValueError(
                f"Strategy {self._strategy.strategy.value} requires a field_labelling_agent, "
                "but none was provided. Use LOCAL_ONLY strategy or provide an agent."
            )

    @property
    def strategy(self) -> StrategyConfig:
        """Get the current processing strategy configuration."""
        return self._strategy

    def with_strategy(self, strategy: StrategyConfig) -> "StructureLabellingService":
        """Create a new service instance with a different strategy.

        Returns a new instance with the specified strategy, preserving
        all other configuration. Follows immutable pattern.

        Args:
            strategy: New strategy configuration to use

        Returns:
            New StructureLabellingService instance with updated strategy
        """
        return StructureLabellingService(
            field_labelling_agent=self._agent,
            structure_detector=self._detector,
            page_image_loader=self._loader,
            strategy_config=strategy,
        )

    async def process(
        self,
        request: StructureLabellingRequest,
        strategy_override: StrategyConfig | None = None,
    ) -> StructureLabellingResult:
        """Process a document for structure detection and field labelling.

        Main entry point that orchestrates the full workflow:
        1. Load page images
        2. Convert input candidates to domain models
        3. Run structure detection if no candidates provided
        4. Call FieldLabellingAgent for each page (based on strategy)
        5. Aggregate and return results

        Args:
            request: Structure labelling request with inputs
            strategy_override: Optional strategy override for this request only.
                Can also be specified via request.options["processing_strategy"].

        Returns:
            StructureLabellingResult with fields and evidence

        Raises:
            ValueError: If request validation fails
        """
        # Determine effective strategy (parameter > options > default)
        effective_strategy = self._resolve_strategy(request.options, strategy_override)

        warnings: list[str] = []
        errors: list[str] = []
        all_fields: list[LinkedField] = []
        all_evidence: list[StructureEvidence] = []

        # Log strategy being used
        logger.info(
            f"Processing document {request.document_id} with strategy: "
            f"{effective_strategy.strategy.value}"
        )

        # Load page images
        image_refs = [img.image_ref for img in request.page_images]
        try:
            page_images = await self._loader.load_images(image_refs)
        except FileNotFoundError as e:
            return StructureLabellingResult(
                document_id=request.document_id,
                success=False,
                fields=[],
                evidence=[],
                page_count=len(request.page_images),
                warnings=warnings,
                errors=[f"Failed to load page images: {e}"],
            )

        # Convert request inputs to domain models
        text_blocks_by_page = self._convert_text_blocks(request.native_text_blocks)
        box_candidates_by_page = self._convert_box_candidates(request.box_candidates)
        table_candidates_by_page = self._convert_table_candidates(request.table_candidates)

        # Process each page
        for page_input in request.page_images:
            page = page_input.page
            page_image = page_images.get(page_input.image_ref)

            if page_image is None:
                errors.append(f"Page {page}: Image not loaded")
                continue

            try:
                fields, evidence = await self._process_page(
                    document_id=request.document_id,
                    page=page,
                    page_image=page_image,
                    text_blocks=text_blocks_by_page.get(page, []),
                    box_candidates=box_candidates_by_page.get(page, []),
                    table_candidates=table_candidates_by_page.get(page, []),
                    options=request.options,
                    strategy_override=effective_strategy,
                )
                all_fields.extend(fields)
                all_evidence.extend(evidence)
            except Exception as e:
                errors.append(f"Page {page}: Processing failed - {e}")
                continue

        # Convert domain models to output DTOs
        field_outputs = [self._field_to_output(f) for f in all_fields]
        evidence_outputs = [self._evidence_to_output(e, request.document_id) for e in all_evidence]

        return StructureLabellingResult(
            document_id=request.document_id,
            success=len(errors) == 0,
            fields=field_outputs,
            evidence=evidence_outputs,
            page_count=len(request.page_images),
            warnings=warnings,
            errors=errors,
        )

    def _resolve_strategy(
        self,
        options: dict[str, Any] | None,
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
        # Explicit override takes precedence
        if override is not None:
            return override

        # Check request options for strategy
        if options and "processing_strategy" in options:
            strategy_value = options["processing_strategy"]
            if isinstance(strategy_value, StrategyConfig):
                return strategy_value
            if isinstance(strategy_value, str):
                # Parse string strategy name
                try:
                    strategy_enum = ProcessingStrategy(strategy_value)
                    return StrategyConfig(strategy=strategy_enum)
                except ValueError:
                    logger.warning(f"Unknown strategy '{strategy_value}', using default")

        # Fall back to service default
        return self._strategy

    async def _process_page(
        self,
        document_id: str,
        page: int,
        page_image: bytes,
        text_blocks: list[TextBlock],
        box_candidates: list[BoxCandidate],
        table_candidates: list[TableCandidate],
        options: dict[str, Any] | None,
        strategy_override: StrategyConfig | None = None,
    ) -> tuple[list[LinkedField], list[StructureEvidence]]:
        """Process a single page for structure detection and labelling.

        Args:
            document_id: Document identifier
            page: Page number
            page_image: Page image bytes
            text_blocks: Native PDF text blocks
            box_candidates: Pre-detected box candidates (or empty)
            table_candidates: Pre-detected table candidates (or empty)
            options: Processing options
            strategy_override: Optional per-request strategy override

        Returns:
            Tuple of linked fields and supporting evidence
        """
        strategy = strategy_override or self._strategy
        label_candidates: list[LabelCandidate] = []

        # Determine processing order based on strategy
        if strategy.is_llm_first():
            return await self._process_llm_first(
                document_id=document_id,
                page=page,
                page_image=page_image,
                text_blocks=text_blocks,
                box_candidates=box_candidates,
                table_candidates=table_candidates,
                options=options,
                strategy=strategy,
            )

        # Local-first processing (LOCAL_ONLY or HYBRID)
        # Run structure detection if no candidates provided
        if not box_candidates and not table_candidates:
            detected = await self._detector.detect_structures(
                page=page,
                page_image=page_image,
                text_blocks=text_blocks,
                options=options,
            )
            box_candidates = list(detected.box_candidates)
            table_candidates = list(detected.table_candidates)
            # Use detected labels if no text blocks provided
            label_candidates = list(detected.label_candidates)
        else:
            # Generate label candidates from text blocks
            label_candidates = self._extract_label_candidates(text_blocks, page)

        # For LOCAL_ONLY strategy, create fields from detected structures
        # without LLM linking
        if strategy.strategy == ProcessingStrategy.LOCAL_ONLY:
            return self._create_fields_from_local_detection(
                page=page,
                label_candidates=label_candidates,
                box_candidates=box_candidates,
                table_candidates=table_candidates,
            )

        # HYBRID strategy: Use LLM for label-to-box linking
        if self._agent is not None:
            fields, evidence = await self._agent.link_labels_to_boxes(
                page=page,
                page_image=page_image,
                label_candidates=label_candidates,
                box_candidates=box_candidates,
                table_candidates=table_candidates,
                text_blocks=text_blocks,
                context=options,
            )
            return fields, evidence

        # Fallback to local-only if agent unavailable
        logger.warning(
            "HYBRID strategy requested but agent unavailable, falling back to local-only"
        )
        return self._create_fields_from_local_detection(
            page=page,
            label_candidates=label_candidates,
            box_candidates=box_candidates,
            table_candidates=table_candidates,
        )

    async def _process_llm_first(
        self,
        document_id: str,
        page: int,
        page_image: bytes,
        text_blocks: list[TextBlock],
        box_candidates: list[BoxCandidate],
        table_candidates: list[TableCandidate],
        options: dict[str, Any] | None,
        strategy: StrategyConfig,
    ) -> tuple[list[LinkedField], list[StructureEvidence]]:
        """Process page with LLM first, falling back to local on error.

        Args:
            document_id: Document identifier
            page: Page number
            page_image: Page image bytes
            text_blocks: Native PDF text blocks
            box_candidates: Pre-detected box candidates
            table_candidates: Pre-detected table candidates
            options: Processing options
            strategy: Strategy configuration

        Returns:
            Tuple of linked fields and supporting evidence
        """
        label_candidates = self._extract_label_candidates(text_blocks, page)

        # Try LLM first
        if self._agent is not None:
            try:
                fields, evidence = await self._agent.link_labels_to_boxes(
                    page=page,
                    page_image=page_image,
                    label_candidates=label_candidates,
                    box_candidates=box_candidates,
                    table_candidates=table_candidates,
                    text_blocks=text_blocks,
                    context=options,
                )
                return fields, evidence
            except Exception as e:
                if strategy.should_fallback_on_error():
                    logger.warning(f"LLM processing failed, falling back to local: {e}")
                else:
                    raise

        # LLM_ONLY without fallback should not reach here with valid config
        if strategy.strategy == ProcessingStrategy.LLM_ONLY:
            raise RuntimeError("LLM_ONLY strategy requires a functioning agent")

        # Fallback to local detection
        if not box_candidates and not table_candidates:
            detected = await self._detector.detect_structures(
                page=page,
                page_image=page_image,
                text_blocks=text_blocks,
                options=options,
            )
            box_candidates = list(detected.box_candidates)
            table_candidates = list(detected.table_candidates)
            label_candidates = list(detected.label_candidates)

        return self._create_fields_from_local_detection(
            page=page,
            label_candidates=label_candidates,
            box_candidates=box_candidates,
            table_candidates=table_candidates,
        )

    def _create_fields_from_local_detection(
        self,
        page: int,
        label_candidates: list[LabelCandidate],
        box_candidates: list[BoxCandidate],
        table_candidates: list[TableCandidate],
    ) -> tuple[list[LinkedField], list[StructureEvidence]]:
        """Create fields from local detection without LLM linking.

        Uses heuristic proximity matching to link labels to boxes.
        Less accurate than LLM but requires no external API calls.

        Args:
            page: Page number
            label_candidates: Detected label candidates
            box_candidates: Detected box candidates
            table_candidates: Detected table candidates

        Returns:
            Tuple of linked fields and evidence
        """
        fields: list[LinkedField] = []
        evidence: list[StructureEvidence] = []

        # Create fields from box candidates with proximity-based label matching
        for box in box_candidates:
            field_id = f"field_{uuid4().hex[:8]}"
            evidence_id = f"ev_{uuid4().hex[:8]}"

            # Find nearest label by proximity (simple heuristic)
            nearest_label = self._find_nearest_label(box, label_candidates)

            field_name = nearest_label.text if nearest_label else f"field_{box.id}"
            field_type = self._infer_field_type(box, nearest_label)

            field = LinkedField(
                id=field_id,
                name=field_name,
                field_type=field_type,
                page=page,
                bbox=box.bbox,
                anchor_bbox=nearest_label.bbox if nearest_label else None,
                confidence=box.confidence * 0.8,  # Reduce confidence for heuristic
                needs_review=True,  # Always flag for review without LLM
                evidence_refs=(evidence_id,),
            )
            fields.append(field)

            ev = StructureEvidence(
                id=evidence_id,
                kind=EvidenceKind.LOCAL_DETECTION,
                field_id=field_id,
                page=page,
                bbox=box.bbox,
                text=field_name,
                confidence=box.confidence * 0.8,
                rationale="Field created via local heuristic detection without LLM verification",
            )
            evidence.append(ev)

        return fields, evidence

    def _find_nearest_label(
        self,
        box: BoxCandidate,
        labels: list[LabelCandidate],
        language: str = "auto",
    ) -> LabelCandidate | None:
        """Find the best label for a box using weighted scoring.

        Uses multiple factors to determine the best match:
        - Distance (closer = better)
        - Direction (reading direction preference)
        - Semantic hints (label type matching)
        - Alignment (horizontal/vertical alignment)

        Args:
            box: The box candidate to find a label for
            labels: Available label candidates
            language: Language hint for reading direction ("ja", "en", "auto")

        Returns:
            Best matching label, or None if no good match
        """
        if not labels:
            return None

        scores: list[tuple[LabelCandidate, float]] = []
        for label in labels:
            score = self._calculate_label_score(box, label, language)
            if score > 0:
                scores.append((label, score))

        if not scores:
            return None

        # Return the label with the highest score
        return max(scores, key=lambda x: x[1])[0]

    def _calculate_label_score(
        self,
        box: BoxCandidate,
        label: LabelCandidate,
        language: str,
    ) -> float:
        """Calculate weighted score for a label-box pair.

        Scoring weights:
        - Distance: 0.4 (closer = higher score)
        - Direction: 0.3 (reading direction preference)
        - Semantic: 0.2 (hint matching)
        - Alignment: 0.1 (horizontal/vertical alignment)

        Args:
            box: Box candidate
            label: Label candidate
            language: Language hint for reading direction

        Returns:
            Score between 0 and 1, or 0 if invalid match
        """
        # Weights for scoring components
        DISTANCE_WEIGHT = 0.4
        DIRECTION_WEIGHT = 0.3
        SEMANTIC_WEIGHT = 0.2
        ALIGNMENT_WEIGHT = 0.1

        # Maximum distance threshold (pixels)
        MAX_DISTANCE = 200.0

        # 1. Distance score (closer = higher, 0 at MAX_DISTANCE)
        distance = self._calculate_label_distance(label.bbox, box.bbox)
        if distance > MAX_DISTANCE:
            return 0.0
        distance_score = max(0.0, 1.0 - distance / MAX_DISTANCE)

        # 2. Direction score (reading direction preference)
        direction_score = self._calculate_direction_score(box, label, language)
        if direction_score < 0:
            # Invalid position (e.g., label too far in wrong direction)
            return 0.0

        # 3. Semantic score (hint matching)
        semantic_score = self._calculate_semantic_score(box, label)

        # 4. Alignment score (horizontal/vertical alignment)
        alignment_score = self._calculate_alignment_score(box, label)

        # Combine scores with weights
        total_score = (
            distance_score * DISTANCE_WEIGHT
            + direction_score * DIRECTION_WEIGHT
            + semantic_score * SEMANTIC_WEIGHT
            + alignment_score * ALIGNMENT_WEIGHT
        )

        return total_score

    def _calculate_label_distance(self, label_bbox: BBox, box_bbox: BBox) -> float:
        """Calculate distance between label and box bounding boxes.

        Uses center-to-edge distance for more accurate proximity.

        Args:
            label_bbox: Label bounding box
            box_bbox: Box bounding box

        Returns:
            Distance in pixels
        """
        # Center of label
        label_center_x = label_bbox.x + label_bbox.width / 2
        label_center_y = label_bbox.y + label_bbox.height / 2

        # Nearest point on box to label center
        nearest_x = max(box_bbox.x, min(label_center_x, box_bbox.x + box_bbox.width))
        nearest_y = max(box_bbox.y, min(label_center_y, box_bbox.y + box_bbox.height))

        # Euclidean distance
        return ((label_center_x - nearest_x) ** 2 + (label_center_y - nearest_y) ** 2) ** 0.5

    def _calculate_direction_score(
        self,
        box: BoxCandidate,
        label: LabelCandidate,
        language: str,
    ) -> float:
        """Calculate direction score based on label position relative to box.

        Scoring based on reading direction conventions:
        - Western (default): Labels above or to the left preferred
        - Japanese: Labels above or to the left, with consideration for
          top-to-bottom, right-to-left column layouts

        Args:
            box: Box candidate
            label: Label candidate
            language: Language hint ("ja", "en", "auto")

        Returns:
            Score between 0 and 1, or -1 if invalid position
        """
        label_bbox = label.bbox
        box_bbox = box.bbox

        # Calculate relative positions
        label_right = label_bbox.x + label_bbox.width
        label_bottom = label_bbox.y + label_bbox.height
        box_right = box_bbox.x + box_bbox.width
        box_bottom = box_bbox.y + box_bbox.height

        # Determine if label is above, below, left, or right of box
        is_above = label_bottom <= box_bbox.y + 20  # Allow 20px overlap
        is_below = label_bbox.y >= box_bottom - 20
        is_left = label_right <= box_bbox.x + 20
        is_right = label_bbox.x >= box_right - 20

        # Detect Japanese text (simple heuristic)
        is_japanese = language == "ja" or (
            language == "auto" and self._contains_japanese(label.text)
        )

        # Score based on position
        if is_above:
            # Label above box - preferred in both Western and Japanese forms
            return 1.0
        elif is_left:
            # Label to the left - common in both layouts
            return 0.9
        elif is_right and is_japanese:
            # Label to the right - valid in Japanese vertical layouts
            return 0.6
        elif is_below:
            # Label below - less common but can happen in some forms
            return 0.3

        # Check if label overlaps significantly with box (invalid)
        overlap_x = max(0, min(label_right, box_right) - max(label_bbox.x, box_bbox.x))
        overlap_y = max(0, min(label_bottom, box_bottom) - max(label_bbox.y, box_bbox.y))
        overlap_area = overlap_x * overlap_y
        box_area = box_bbox.width * box_bbox.height

        if box_area > 0 and overlap_area / box_area > 0.5:
            return -1.0  # Too much overlap, invalid

        # Diagonal positions with some tolerance
        return 0.4

    def _contains_japanese(self, text: str) -> bool:
        """Check if text contains Japanese characters.

        Args:
            text: Text to check

        Returns:
            True if text contains Japanese characters
        """
        for char in text:
            code = ord(char)
            # Hiragana, Katakana, or CJK unified ideographs
            if (
                (0x3040 <= code <= 0x309F)  # Hiragana
                or (0x30A0 <= code <= 0x30FF)  # Katakana
                or (0x4E00 <= code <= 0x9FFF)  # CJK
            ):
                return True
        return False

    def _calculate_semantic_score(
        self,
        box: BoxCandidate,
        label: LabelCandidate,
    ) -> float:
        """Calculate semantic score based on hint matching.

        Matches label semantic hints with box type expectations.

        Args:
            box: Box candidate
            label: Label candidate

        Returns:
            Score between 0 and 1
        """
        if not label.semantic_hints:
            return 0.5  # Neutral score when no hints

        # Map semantic hints to expected box types
        hint_to_box_type = {
            "checkbox": {"checkbox", "check"},
            "signature": {"signature"},
            "date": {"text", "date"},
            "amount": {"text", "number"},
            "phone": {"text", "phone"},
            "email": {"text", "email"},
            "address": {"text"},
            "name": {"text"},
            "number": {"text", "number"},
            "company": {"text"},
            "bank": {"text"},
        }

        box_type = box.box_type or "text"

        # Check if any hint matches the box type
        for hint in label.semantic_hints:
            expected_types = hint_to_box_type.get(hint, {"text"})
            if box_type in expected_types:
                return 1.0  # Perfect match
            if "text" in expected_types and box_type in {"text", "unknown", ""}:
                return 0.8  # Good match

        # Check for mismatch penalties
        has_checkbox_hint = "checkbox" in label.semantic_hints
        is_checkbox_box = box_type == "checkbox" or (
            box.bbox.width < 40
            and box.bbox.height < 40
            and 0.7 < box.bbox.width / max(box.bbox.height, 1) < 1.5
        )

        if has_checkbox_hint != is_checkbox_box:
            return 0.2  # Mismatch penalty

        return 0.5  # Neutral

    def _calculate_alignment_score(
        self,
        box: BoxCandidate,
        label: LabelCandidate,
    ) -> float:
        """Calculate alignment score based on horizontal/vertical alignment.

        Labels aligned with boxes (same row or column) get higher scores.

        Args:
            box: Box candidate
            label: Label candidate

        Returns:
            Score between 0 and 1
        """
        label_bbox = label.bbox
        box_bbox = box.bbox

        # Calculate centers
        label_center_x = label_bbox.x + label_bbox.width / 2
        label_center_y = label_bbox.y + label_bbox.height / 2
        box_center_x = box_bbox.x + box_bbox.width / 2
        box_center_y = box_bbox.y + box_bbox.height / 2

        # Horizontal alignment (for labels above/below)
        horizontal_offset = abs(label_center_x - box_center_x)
        horizontal_tolerance = max(box_bbox.width / 2, label_bbox.width / 2, 50)
        horizontal_alignment = max(0.0, 1.0 - horizontal_offset / horizontal_tolerance)

        # Vertical alignment (for labels left/right)
        vertical_offset = abs(label_center_y - box_center_y)
        vertical_tolerance = max(box_bbox.height / 2, label_bbox.height / 2, 30)
        vertical_alignment = max(0.0, 1.0 - vertical_offset / vertical_tolerance)

        # Return the better alignment score
        return max(horizontal_alignment, vertical_alignment)

    def _infer_field_type(
        self,
        box: BoxCandidate,
        label: LabelCandidate | None,
    ) -> str:
        """Infer field type from box characteristics and label hints.

        Args:
            box: The box candidate
            label: Associated label (if any)

        Returns:
            Inferred field type string
        """
        # Use box type if available
        if box.box_type and box.box_type != "unknown":
            return box.box_type

        # Check label hints if available
        if label and label.semantic_hints:
            hint_to_type = {
                "checkbox": "checkbox",
                "signature": "signature",
                "date": "date",
                "amount": "currency",
                "phone": "phone",
                "email": "email",
                "address": "address",
                "name": "text",
            }
            for hint in label.semantic_hints:
                if hint in hint_to_type:
                    return hint_to_type[hint]

        # Infer from box aspect ratio
        aspect_ratio = box.bbox.width / max(box.bbox.height, 1)
        if aspect_ratio < 1.2 and box.bbox.width < 30:
            return "checkbox"
        if aspect_ratio > 5:
            return "text"

        return "text"

    def _extract_label_candidates(
        self, text_blocks: list[TextBlock], page: int
    ) -> list[LabelCandidate]:
        """Extract label candidates from text blocks.

        Simple heuristic: treat short text blocks as potential labels.
        The Agent will determine which are actually labels.

        Args:
            text_blocks: Native PDF text blocks
            page: Page number

        Returns:
            List of potential label candidates
        """
        candidates: list[LabelCandidate] = []

        for block in text_blocks:
            # Heuristic: labels are typically short (< 50 chars)
            # and often contain certain patterns
            if len(block.text.strip()) > 0 and len(block.text) < 100:
                candidates.append(
                    LabelCandidate(
                        id=f"label_{block.id}",
                        text=block.text.strip(),
                        bbox=block.bbox,
                        source="pdf_text",
                        confidence=block.confidence,
                        semantic_hints=self._infer_semantic_hints(block.text),
                    )
                )

        return candidates

    def _infer_semantic_hints(self, text: str) -> list[str]:
        """Infer semantic hints from label text.

        Uses comprehensive keyword patterns for Japanese and English
        to identify field types for better label-to-box matching.

        Args:
            text: Label text

        Returns:
            List of semantic hints
        """
        hints: list[str] = []
        text_lower = text.lower()

        # Comprehensive field type patterns (Japanese and English)
        patterns = {
            "name": [
                "name",
                "名前",
                "氏名",
                "フリガナ",
                "姓",
                "名",
                "full name",
                "姓名",
                "ふりがな",
                "カナ",
                "かな",
                "漢字",
                "first name",
                "last name",
                "given name",
                "family name",
                "担当者",
                "代表者",
                "申請者",
            ],
            "date": [
                "date",
                "日付",
                "年月日",
                "生年月日",
                "年",
                "月",
                "日",
                "有効期限",
                "発行日",
                "期限",
                "開始日",
                "終了日",
                "締切",
                "deadline",
                "due date",
                "expiry",
                "valid until",
                "valid from",
                "issued",
                "birthday",
                "dob",
                "入社日",
                "退社日",
                "作成日",
                "更新日",
                "登録日",
            ],
            "address": [
                "address",
                "住所",
                "所在地",
                "居所",
                "郵便番号",
                "〒",
                "都道府県",
                "市区町村",
                "番地",
                "建物名",
                "マンション",
                "アパート",
                "street",
                "city",
                "state",
                "zip",
                "postal",
                "prefecture",
                "country",
                "送付先",
                "請求先",
                "配送先",
                "本店所在地",
            ],
            "phone": [
                "phone",
                "tel",
                "電話",
                "携帯",
                "fax",
                "ファックス",
                "連絡先",
                "telephone",
                "mobile",
                "cell",
                "緊急連絡先",
                "内線",
                "ext",
                "自宅電話",
                "勤務先電話",
                "fax番号",
                "ファクス",
            ],
            "email": [
                "email",
                "mail",
                "メール",
                "e-mail",
                "eメール",
                "メールアドレス",
                "electronic mail",
                "連絡先メール",
                "email address",
            ],
            "amount": [
                "amount",
                "金額",
                "合計",
                "円",
                "￥",
                "価格",
                "料金",
                "総額",
                "単価",
                "税込",
                "税抜",
                "消費税",
                "小計",
                "total",
                "subtotal",
                "price",
                "cost",
                "fee",
                "charge",
                "payment",
                "支払額",
                "請求額",
                "入金額",
                "数量",
                "quantity",
                "qty",
                "個数",
            ],
            "checkbox": [
                "check",
                "チェック",
                "該当",
                "有",
                "無",
                "yes",
                "no",
                "□",
                "■",
                "☑",
                "☐",
                "✓",
                "✔",
                "選択",
                "option",
                "希望する",
                "希望しない",
                "同意",
                "確認",
                "agree",
                "confirm",
            ],
            "signature": [
                "signature",
                "署名",
                "印",
                "サイン",
                "印鑑",
                "捺印",
                "押印",
                "sign here",
                "autograph",
                "代表印",
                "社印",
                "認印",
                "実印",
                "記名",
                "自署",
            ],
            "number": [
                "number",
                "番号",
                "no.",
                "no",
                "id",
                "コード",
                "個数",
                "数量",
                "code",
                "reference",
                "ref",
                "account",
                "口座番号",
                "顧客番号",
                "従業員番号",
                "社員番号",
                "会員番号",
                "整理番号",
                "受付番号",
                "注文番号",
                "order number",
                "invoice number",
                "請求番号",
            ],
            "company": [
                "company",
                "会社",
                "法人",
                "事業者",
                "企業",
                "組織",
                "corporation",
                "corp",
                "inc",
                "ltd",
                "株式会社",
                "有限会社",
                "合同会社",
                "事業所",
                "勤務先",
                "所属",
                "部署",
                "department",
                "division",
                "employer",
                "organization",
            ],
            "bank": [
                "bank",
                "銀行",
                "口座",
                "支店",
                "金融機関",
                "account",
                "branch",
                "routing",
                "swift",
                "iban",
                "普通",
                "当座",
                "預金種別",
                "口座名義",
                "account holder",
                "振込先",
            ],
        }

        for hint, keywords in patterns.items():
            if any(kw in text_lower for kw in keywords):
                hints.append(hint)

        return hints

    def _convert_text_blocks(self, inputs: list[TextBlockInput]) -> dict[int, list[TextBlock]]:
        """Convert input text blocks to domain models grouped by page."""
        by_page: dict[int, list[TextBlock]] = {}

        for inp in inputs:
            block = TextBlock(
                id=inp.id,
                text=inp.text,
                bbox=BBox(
                    x=inp.bbox[0],
                    y=inp.bbox[1],
                    width=inp.bbox[2],
                    height=inp.bbox[3],
                    page=inp.page,
                ),
                font_name=inp.font_name,
                font_size=inp.font_size,
            )
            if inp.page not in by_page:
                by_page[inp.page] = []
            by_page[inp.page].append(block)

        return by_page

    def _convert_box_candidates(
        self, inputs: list[BoxCandidateInput]
    ) -> dict[int, list[BoxCandidate]]:
        """Convert input box candidates to domain models grouped by page."""
        by_page: dict[int, list[BoxCandidate]] = {}

        for inp in inputs:
            candidate = BoxCandidate(
                id=inp.id,
                bbox=BBox(
                    x=inp.bbox[0],
                    y=inp.bbox[1],
                    width=inp.bbox[2],
                    height=inp.bbox[3],
                    page=inp.page,
                ),
                box_type=inp.box_type,
                confidence=inp.confidence,
            )
            if inp.page not in by_page:
                by_page[inp.page] = []
            by_page[inp.page].append(candidate)

        return by_page

    def _convert_table_candidates(
        self, inputs: list[TableCandidateInput]
    ) -> dict[int, list[TableCandidate]]:
        """Convert input table candidates to domain models grouped by page."""
        by_page: dict[int, list[TableCandidate]] = {}

        for inp in inputs:
            cells = tuple(
                TableCell(
                    row=c.row,
                    col=c.col,
                    bbox=BBox(
                        x=c.bbox[0],
                        y=c.bbox[1],
                        width=c.bbox[2],
                        height=c.bbox[3],
                        page=inp.page,
                    ),
                    text=c.text,
                    is_header=c.is_header,
                )
                for c in inp.cells
            )

            candidate = TableCandidate(
                id=inp.id,
                bbox=BBox(
                    x=inp.bbox[0],
                    y=inp.bbox[1],
                    width=inp.bbox[2],
                    height=inp.bbox[3],
                    page=inp.page,
                ),
                rows=inp.rows,
                cols=inp.cols,
                cells=cells,
                confidence=inp.confidence,
            )
            if inp.page not in by_page:
                by_page[inp.page] = []
            by_page[inp.page].append(candidate)

        return by_page

    def _field_to_output(self, field: LinkedField) -> FieldOutput:
        """Convert domain LinkedField to output DTO."""
        return FieldOutput(
            id=field.id,
            name=field.name,
            field_type=field.field_type,
            page=field.page,
            bbox=[
                field.bbox.x,
                field.bbox.y,
                field.bbox.width,
                field.bbox.height,
            ],
            anchor_bbox=(
                [
                    field.anchor_bbox.x,
                    field.anchor_bbox.y,
                    field.anchor_bbox.width,
                    field.anchor_bbox.height,
                ]
                if field.anchor_bbox
                else None
            ),
            confidence=field.confidence,
            needs_review=field.needs_review,
            evidence_refs=list(field.evidence_refs),
            box_candidate_id=field.box_candidate_id,
        )

    def _evidence_to_output(self, evidence: StructureEvidence, document_id: str) -> EvidenceOutput:
        """Convert domain StructureEvidence to output DTO."""
        return EvidenceOutput(
            id=evidence.id,
            kind=evidence.kind.value,
            field_id=evidence.field_id,
            page=evidence.page,
            bbox=(
                [
                    evidence.bbox.x,
                    evidence.bbox.y,
                    evidence.bbox.width,
                    evidence.bbox.height,
                ]
                if evidence.bbox
                else None
            ),
            text=evidence.text,
            confidence=evidence.confidence,
            rationale=evidence.rationale,
        )
