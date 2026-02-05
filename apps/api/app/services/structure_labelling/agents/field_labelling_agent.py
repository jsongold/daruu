"""LangChain-based FieldLabellingAgent implementation.

This agent uses LLM reasoning to link labels to field positions (bbox).
It is the CRITICAL component that performs semantic understanding
and cannot be replaced with rule-based logic per PRD requirements.

Implementation approach:
1. Use LangChain for LLM abstraction (OpenAI, Anthropic, Google, etc.)
2. Use text-based analysis with spatial context
3. Return structured output with fields and evidence

The agent builds a prompt describing labels and boxes with their positions,
then uses the LLM to determine semantic linkages based on:
- Spatial relationships (above, left-of, etc.)
- Semantic meaning of label text
- Form layout conventions
- Field type inference from context
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.config import DEFAULT_MODEL, get_settings
from app.models.common import BBox
from app.models.cost import CostTracker, LLMUsage
from app.services.structure_labelling.domain.models import (
    BoxCandidate,
    EvidenceKind,
    LabelCandidate,
    LinkedField,
    StructureEvidence,
    TableCandidate,
    TextBlock,
)
from app.services.structure_labelling.ports import FieldLabellingAgentPort

logger = logging.getLogger(__name__)


# Pydantic models for structured LLM output
from pydantic import BaseModel, Field as PydanticField


class FieldLinkage(BaseModel):
    """A single label-to-box linkage from LLM analysis."""

    label_id: str = PydanticField(..., description="ID of the label candidate")
    box_id: str = PydanticField(..., description="ID of the box candidate")
    field_name: str = PydanticField(..., description="Semantic name for the field")
    field_type: str = PydanticField(
        ..., description="Field type: text, checkbox, date, number, signature, email, phone"
    )
    confidence: float = PydanticField(
        ..., ge=0.0, le=1.0, description="Confidence in the linkage (0-1)"
    )
    rationale: str = PydanticField(
        ..., description="Explanation of why this label links to this box"
    )


class LinkageResponse(BaseModel):
    """Structured response from LLM for field linkages."""

    linkages: list[FieldLinkage] = PydanticField(
        default_factory=list, description="List of label-to-box linkages"
    )
    unlinked_boxes: list[str] = PydanticField(
        default_factory=list, description="Box IDs that could not be linked to labels"
    )


SYSTEM_PROMPT = """You are an expert at analyzing form documents and linking text labels to their corresponding input boxes.

## CORE CONCEPT: LABEL HIERARCHY

Forms have a hierarchical text structure. Your task is to find the DIRECT LABEL for each input box:

```
Section Header          <- DO NOT use as field label (too general)
  ├── Group Label       <- Use only if it's the closest specific label
  │     └── [input box]
  └── Direct Label      <- USE THIS (closest, most specific)
        └── [input box]
```

### Label Classification

1. **Section Headers**: Category titles spanning multiple fields
   - Characteristics: Large/bold font, wide width, general terminology
   - Examples: "Personal Information", "Payment Details", "Contact Info"
   - Action: DO NOT link directly to boxes

2. **Group Labels**: Sub-category labels with 2-3 related boxes
   - Characteristics: Moderate specificity, multiple boxes nearby
   - Examples: "Address", "Date of Birth", "Emergency Contact"
   - Action: Link only if it's the most specific label available

3. **Direct Labels**: The actual field label immediately near ONE box
   - Characteristics: Short text, within ~30px of one box, specific
   - Examples: "First Name", "City", "Phone", "Email"
   - Action: LINK THESE to their adjacent boxes

## SPATIAL RELATIONSHIP RULES

### Finding the Right Label
For each input box, look for labels in this priority order:
1. **Immediately above** (0-25px) - most common
2. **Immediately left** (0-40px) - common for inline forms
3. **Immediately right** (0-20px) - common for checkboxes
4. **Same row, left side** - for table-like layouts

### Distance Guidelines
- **0-30px**: High confidence - likely the direct label
- **30-60px**: Medium confidence - verify semantic match
- **60-100px**: Low confidence - only if strong semantic match
- **>100px**: Very low confidence - likely not related

### Grid/Table Forms
When forms use grid layouts:
- Row header + Column header together describe the cell
- Example: Row="Date of Birth", Columns="Year", "Month", "Day"
- Field names: "Date of Birth - Year", "Date of Birth - Month", etc.

## SEMANTIC MATCHING

### Field Type Detection
| Type | Common Keywords (multilingual) |
|------|-------------------------------|
| Name | name, 氏名, nom, nombre, 名前 |
| Address | address, 住所, adresse, dirección |
| Date | date, 日付, 年月日, fecha, datum |
| Phone | phone, tel, 電話, téléphone |
| Email | email, mail, メール, correo |
| Amount | amount, total, 金額, 円, $, € |
| Checkbox | check, 有無, yes/no, agree |
| Signature | signature, sign, 署名, 印 |
| Number | number, no., #, 番号, código |

### Handling Ambiguous Labels
When a label is generic (like "Name" appearing twice):
1. Check the parent section/group label for context
2. Consider the position within the form flow
3. Use combined naming: "Emergency Contact - Name"

## LINKING RULES

1. **One-to-One**: Each box gets at most one label; each label links to at most one box
2. **Closest Wins**: When multiple labels could match, prefer the closest one
3. **Semantic Tiebreaker**: If distances are similar, prefer the semantically better match
4. **Leave Unlinked**: If no confident match exists, leave the box unlinked rather than guessing

## CONFIDENCE SCORING

- **0.90-1.00**: Direct label within 25px, clear semantic match
- **0.75-0.90**: Direct label within 50px, good semantic match
- **0.60-0.75**: Moderate distance or needs context from group label
- **0.40-0.60**: Multiple candidates, ambiguous
- **<0.40**: Guessing - prefer leaving unlinked

## OUTPUT FORMAT

For each linkage provide:
- label_id: The text block being used as label
- box_id: The input box being labeled
- field_name: Human-readable field name (use the label text, add context if needed)
- field_type: text, checkbox, date, amount, signature, etc.
- confidence: 0.0-1.0
- rationale: Brief explanation (spatial + semantic reasoning)"""

USER_PROMPT_TEMPLATE = """Link text labels to input boxes in this form document.

## Document Info
- Page: {page}
- Document type: {doc_type}
- Language: {language}
- Reading direction: {reading_direction}

## Text Labels (potential field names)
Each label includes position and nearby boxes:
{labels_json}

## Input Boxes (fields to be filled)
Each box includes position and nearby labels:
{boxes_json}

## Spatial Groups
Elements that appear grouped together:
{spatial_clusters}

## Your Task

1. **Classify each label**: Is it a SECTION_HEADER, GROUP_LABEL, or DIRECT_LABEL?
   - Section headers span multiple fields (ignore for direct linking)
   - Direct labels are closest to exactly one box (use these)

2. **For each input box**: Find its direct label
   - Look for the closest, most specific label
   - Check above first, then left, then right
   - If label is generic, note the parent group/section for context

3. **Determine field type** from label semantics (text, date, phone, checkbox, etc.)

## Output JSON

```json
{{
  "linkages": [
    {{
      "label_id": "label_X",
      "box_id": "box_Y",
      "field_name": "The actual label text to use",
      "field_type": "text|checkbox|date|amount|signature|phone|email",
      "confidence": 0.95,
      "rationale": "Brief explanation: spatial relationship + semantic reasoning"
    }}
  ],
  "unlinked_boxes": ["box_ids_that_have_no_clear_label"]
}}
```

## Important
- Use the CLOSEST specific label, not section headers
- field_name should be human-readable (the direct label text)
- Confidence < 0.5 = prefer leaving unlinked
- When in doubt, leave unlinked rather than guess"""


@dataclass
class LangChainFieldLabellingAgent:
    """LangChain implementation of FieldLabellingAgentPort.

    Uses LangChain to orchestrate LLM calls for semantic label-to-box linking.
    Supports OpenAI models through LangChain abstraction.

    Configuration:
        model_name: Model to use (default: gpt-4o-mini)
        temperature: Sampling temperature (default: 0.0 for determinism)
        max_retries: Number of retries on failure (default: 3)
        confidence_threshold: Below this, mark needs_review=True
        use_fallback: If True, use proximity-based fallback when LLM fails

    The agent:
    1. Formats labels and boxes with spatial context
    2. Calls LLM with structured output
    3. Parses response into LinkedField objects
    4. Falls back to proximity matching if LLM unavailable

    Tracks token usage for cost estimation via get_cost_tracker().
    """

    model_name: str = DEFAULT_MODEL
    temperature: float = 0.0
    max_retries: int = 3
    confidence_threshold: float = 0.7
    use_fallback: bool = True
    _llm: Any = field(default=None, init=False)
    _initialized: bool = field(default=False, init=False)
    _cost_tracker: CostTracker = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Initialize LangChain components."""
        self._cost_tracker = CostTracker.create(model_name=self.model_name)
        self._initialize_llm()

    def get_cost_tracker(self) -> CostTracker:
        """Get the current cost tracker with accumulated usage.

        Returns:
            CostTracker with all LLM usage since initialization
        """
        return self._cost_tracker

    def reset_cost_tracker(self) -> None:
        """Reset the cost tracker to zero."""
        self._cost_tracker = CostTracker.create(model_name=self.model_name)

    def _track_usage(self, response: Any, operation: str) -> None:
        """Track token usage from an LLM response.

        Args:
            response: LangChain response object
            operation: Description of the operation
        """
        # Extract usage from response metadata
        input_tokens = 0
        output_tokens = 0

        if hasattr(response, "response_metadata"):
            metadata = response.response_metadata
            if isinstance(metadata, dict):
                token_usage = metadata.get("token_usage", {})
                if token_usage:
                    input_tokens = token_usage.get("prompt_tokens", 0)
                    output_tokens = token_usage.get("completion_tokens", 0)

        # For structured output, estimate if no metadata
        if input_tokens == 0 and hasattr(response, "linkages"):
            # Rough estimate for structured output
            input_tokens = 500  # Typical prompt size
            output_tokens = len(response.linkages) * 50  # Estimate per linkage

        usage = LLMUsage.create(
            model=self.model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            agent_name="FieldLabellingAgent",
            operation=operation,
        )
        self._cost_tracker = self._cost_tracker.add_llm_usage(usage)

    def _initialize_llm(self) -> None:
        """Initialize the LangChain LLM client."""
        settings = get_settings()

        if not settings.openai_api_key:
            logger.warning(
                "OPENAI_API_KEY not configured. "
                "LLM-based field labelling will fall back to proximity matching."
            )
            self._initialized = False
            return

        try:
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout=settings.openai_timeout_seconds,
                max_retries=self.max_retries,
            )
            self._initialized = True
            logger.info(f"Initialized LangChain LLM with model: {self.model_name}")
        except ImportError:
            logger.warning(
                "langchain-openai not installed. "
                "LLM-based field labelling will fall back to proximity matching."
            )
            self._initialized = False
        except Exception as e:
            logger.error(f"Failed to initialize LangChain LLM: {e}")
            self._initialized = False

    def _format_labels_for_prompt(
        self, labels: list[LabelCandidate], boxes: list[BoxCandidate]
    ) -> str:
        """Format label candidates as JSON for the prompt with spatial context.

        Includes computed nearby boxes for each label to help LLM
        understand spatial relationships.

        Args:
            labels: List of label candidates
            boxes: List of box candidates for computing nearby relationships

        Returns:
            JSON string representation of labels with spatial context
        """
        formatted = []
        for label in labels:
            nearby_boxes = self._compute_nearby_boxes(label, boxes)
            formatted.append({
                "id": label.id,
                "text": label.text,
                "position": {
                    "x": label.bbox.x,
                    "y": label.bbox.y,
                    "width": label.bbox.width,
                    "height": label.bbox.height,
                },
                "semantic_hints": label.semantic_hints,
                "confidence": label.confidence,
                "nearby_boxes": nearby_boxes,
            })
        return json.dumps(formatted, indent=2, ensure_ascii=False)

    def _format_boxes_for_prompt(
        self, boxes: list[BoxCandidate], labels: list[LabelCandidate]
    ) -> str:
        """Format box candidates as JSON for the prompt with spatial context.

        Includes computed nearby labels for each box to help LLM
        understand spatial relationships.

        Args:
            boxes: List of box candidates
            labels: List of label candidates for computing nearby relationships

        Returns:
            JSON string representation of boxes with spatial context
        """
        formatted = []
        for box in boxes:
            nearby_labels = self._compute_nearby_labels(box, labels)
            formatted.append({
                "id": box.id,
                "type": box.box_type,
                "position": {
                    "x": box.bbox.x,
                    "y": box.bbox.y,
                    "width": box.bbox.width,
                    "height": box.bbox.height,
                },
                "has_border": box.has_border,
                "neighboring_text": box.neighboring_text,
                "confidence": box.confidence,
                "nearby_labels": nearby_labels,
            })
        return json.dumps(formatted, indent=2, ensure_ascii=False)

    def _compute_nearby_boxes(
        self, label: LabelCandidate, boxes: list[BoxCandidate], max_distance: float = 200.0
    ) -> list[dict[str, Any]]:
        """Compute nearby boxes for a label with direction and distance.

        Args:
            label: The label to find nearby boxes for
            boxes: All box candidates
            max_distance: Maximum distance to consider (pixels)

        Returns:
            List of nearby box info with direction and distance
        """
        nearby = []
        label_bbox = label.bbox
        label_center_x = label_bbox.x + label_bbox.width / 2
        label_center_y = label_bbox.y + label_bbox.height / 2
        label_right = label_bbox.x + label_bbox.width
        label_bottom = label_bbox.y + label_bbox.height

        for box in boxes:
            box_bbox = box.bbox
            distance = self._calculate_distance(label_bbox, box_bbox)

            if distance <= max_distance:
                # Determine direction
                box_center_x = box_bbox.x + box_bbox.width / 2
                box_center_y = box_bbox.y + box_bbox.height / 2

                direction = self._compute_direction(
                    label_center_x, label_center_y, label_right, label_bottom,
                    box_center_x, box_center_y, box_bbox.x, box_bbox.y
                )

                nearby.append({
                    "box_id": box.id,
                    "direction": direction,
                    "distance_px": round(distance, 1),
                })

        # Sort by distance and limit to top 5 nearest
        nearby.sort(key=lambda x: x["distance_px"])
        return nearby[:5]

    def _compute_nearby_labels(
        self, box: BoxCandidate, labels: list[LabelCandidate], max_distance: float = 200.0
    ) -> list[dict[str, Any]]:
        """Compute nearby labels for a box with direction and distance.

        Args:
            box: The box to find nearby labels for
            labels: All label candidates
            max_distance: Maximum distance to consider (pixels)

        Returns:
            List of nearby label info with direction and distance
        """
        nearby = []
        box_bbox = box.bbox
        box_center_x = box_bbox.x + box_bbox.width / 2
        box_center_y = box_bbox.y + box_bbox.height / 2
        box_right = box_bbox.x + box_bbox.width
        box_bottom = box_bbox.y + box_bbox.height

        for label in labels:
            label_bbox = label.bbox
            distance = self._calculate_distance(label_bbox, box_bbox)

            if distance <= max_distance:
                # Determine direction (from box's perspective)
                label_center_x = label_bbox.x + label_bbox.width / 2
                label_center_y = label_bbox.y + label_bbox.height / 2

                # Invert direction since we want "where is label relative to box"
                direction = self._compute_direction(
                    box_center_x, box_center_y, box_right, box_bottom,
                    label_center_x, label_center_y, label_bbox.x, label_bbox.y
                )

                nearby.append({
                    "label_id": label.id,
                    "label_text": label.text[:50],  # Truncate long text
                    "direction": direction,
                    "distance_px": round(distance, 1),
                })

        # Sort by distance and limit to top 5 nearest
        nearby.sort(key=lambda x: x["distance_px"])
        return nearby[:5]

    def _compute_direction(
        self,
        from_center_x: float,
        from_center_y: float,
        from_right: float,
        from_bottom: float,
        to_center_x: float,
        to_center_y: float,
        to_left: float,
        to_top: float,
    ) -> str:
        """Compute directional relationship between two elements.

        Args:
            from_center_x, from_center_y: Center of source element
            from_right, from_bottom: Right and bottom edges of source
            to_center_x, to_center_y: Center of target element
            to_left, to_top: Left and top edges of target

        Returns:
            Direction string: "above", "below", "left", "right", or compound
        """
        # Determine primary direction based on edge distances
        horizontal = ""
        vertical = ""

        # Horizontal: is target to the left or right of source?
        if to_center_x < from_center_x - 20:
            horizontal = "left"
        elif to_center_x > from_center_x + 20:
            horizontal = "right"

        # Vertical: is target above or below source?
        if to_center_y < from_center_y - 20:
            vertical = "above"
        elif to_center_y > from_center_y + 20:
            vertical = "below"

        # Combine directions
        if vertical and horizontal:
            return f"{vertical}-{horizontal}"
        elif vertical:
            return vertical
        elif horizontal:
            return horizontal
        else:
            return "overlapping"

    def _compute_spatial_clusters(
        self, labels: list[LabelCandidate], boxes: list[BoxCandidate]
    ) -> str:
        """Compute spatial clusters of nearby elements.

        Groups labels and boxes that appear close together on the page.

        Args:
            labels: All label candidates
            boxes: All box candidates

        Returns:
            JSON string describing spatial clusters
        """
        # Simple clustering based on Y-coordinate bands
        clusters: list[dict[str, Any]] = []

        # Combine all elements with their positions
        all_elements = []
        for label in labels:
            all_elements.append({
                "type": "label",
                "id": label.id,
                "y": label.bbox.y,
                "height": label.bbox.height,
                "x": label.bbox.x,
            })
        for box in boxes:
            all_elements.append({
                "type": "box",
                "id": box.id,
                "y": box.bbox.y,
                "height": box.bbox.height,
                "x": box.bbox.x,
            })

        if not all_elements:
            return "[]"

        # Sort by Y position
        all_elements.sort(key=lambda e: e["y"])

        # Group into clusters based on Y proximity
        current_cluster: list[dict[str, Any]] = []
        cluster_y_end = 0.0

        for elem in all_elements:
            # If element is far below current cluster, start new cluster
            if current_cluster and elem["y"] > cluster_y_end + 50:
                if len(current_cluster) > 1:  # Only include clusters with multiple elements
                    clusters.append({
                        "y_range": f"{current_cluster[0]['y']:.0f}-{cluster_y_end:.0f}",
                        "labels": [e["id"] for e in current_cluster if e["type"] == "label"],
                        "boxes": [e["id"] for e in current_cluster if e["type"] == "box"],
                    })
                current_cluster = []

            current_cluster.append(elem)
            cluster_y_end = max(cluster_y_end, elem["y"] + elem["height"])

        # Add final cluster
        if len(current_cluster) > 1:
            clusters.append({
                "y_range": f"{current_cluster[0]['y']:.0f}-{cluster_y_end:.0f}",
                "labels": [e["id"] for e in current_cluster if e["type"] == "label"],
                "boxes": [e["id"] for e in current_cluster if e["type"] == "box"],
            })

        return json.dumps(clusters, indent=2, ensure_ascii=False)

    def _detect_language(self, labels: list[LabelCandidate]) -> str:
        """Detect the primary language from label text.

        Args:
            labels: Label candidates to analyze

        Returns:
            Language code: "ja" for Japanese, "en" for English, "mixed" for both
        """
        japanese_count = 0
        english_count = 0

        for label in labels:
            if self._contains_japanese(label.text):
                japanese_count += 1
            elif label.text.isascii():
                english_count += 1

        if japanese_count > english_count:
            return "ja"
        elif english_count > japanese_count:
            return "en"
        elif japanese_count > 0:
            return "mixed"
        return "unknown"

    def _get_reading_direction(self, language: str) -> str:
        """Get reading direction hint based on language.

        Args:
            language: Detected language code

        Returns:
            Reading direction description
        """
        if language == "ja":
            return "Japanese: typically left-to-right, may have vertical sections"
        elif language == "en":
            return "Western: left-to-right, top-to-bottom"
        elif language == "mixed":
            return "Mixed: consider both Japanese and Western layouts"
        return "Unknown: default to left-to-right, top-to-bottom"

    def _filter_relevant_labels(
        self,
        boxes: list[BoxCandidate],
        labels: list[LabelCandidate],
        max_labels: int = 150,
        max_distance: float = 300.0,
    ) -> list[LabelCandidate]:
        """Filter labels to only include those relevant to the boxes.

        Reduces the number of labels sent to LLM by:
        1. Only including labels within max_distance of any box
        2. Limiting total count to max_labels

        Args:
            boxes: Box candidates
            labels: All label candidates
            max_labels: Maximum number of labels to return
            max_distance: Maximum distance from any box (pixels)

        Returns:
            Filtered list of relevant labels
        """
        if not boxes or not labels:
            return labels[:max_labels]

        # Find labels that are close to at least one box
        relevant_labels: list[tuple[LabelCandidate, float]] = []

        for label in labels:
            min_distance = float("inf")
            for box in boxes:
                distance = self._calculate_distance(label.bbox, box.bbox)
                min_distance = min(min_distance, distance)

            if min_distance <= max_distance:
                relevant_labels.append((label, min_distance))

        # Sort by distance (closest first) and limit
        relevant_labels.sort(key=lambda x: x[1])

        return [label for label, _ in relevant_labels[:max_labels]]

    async def _call_llm(
        self,
        page: int,
        labels: list[LabelCandidate],
        boxes: list[BoxCandidate],
        context: dict[str, Any] | None = None,
    ) -> LinkageResponse:
        """Call the LLM to analyze labels and boxes.

        Args:
            page: Page number
            labels: Label candidates
            boxes: Box candidates
            context: Additional context

        Returns:
            LinkageResponse with field linkages

        Raises:
            RuntimeError: If LLM call fails
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        ctx = context or {}
        doc_type = ctx.get("document_type", "form")

        # Limit boxes and labels to prevent context overflow
        MAX_BOXES = 100
        MAX_LABELS = 150

        limited_boxes = boxes[:MAX_BOXES]
        # Filter labels to only include relevant ones (near boxes)
        filtered_labels = self._filter_relevant_labels(
            limited_boxes, labels, max_labels=MAX_LABELS
        )

        logger.info(
            f"LLM call with {len(filtered_labels)} labels (from {len(labels)}) "
            f"and {len(limited_boxes)} boxes (from {len(boxes)})"
        )

        # Detect language and reading direction
        language = self._detect_language(filtered_labels)
        reading_direction = self._get_reading_direction(language)

        # Compute spatial clusters for additional context
        spatial_clusters = self._compute_spatial_clusters(filtered_labels, limited_boxes)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            labels_json=self._format_labels_for_prompt(filtered_labels, limited_boxes),
            boxes_json=self._format_boxes_for_prompt(limited_boxes, filtered_labels),
            spatial_clusters=spatial_clusters,
            page=page,
            doc_type=doc_type,
            language=language,
            reading_direction=reading_direction,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]

        try:
            # Use structured output with with_structured_output
            structured_llm = self._llm.with_structured_output(LinkageResponse)
            response = await structured_llm.ainvoke(messages)

            # Track token usage
            self._track_usage(response, "link_labels_to_boxes")

            return response
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise RuntimeError(f"LLM field labelling failed: {e}") from e

    async def link_labels_to_boxes(
        self,
        page: int,
        page_image: bytes | None,
        label_candidates: list[LabelCandidate],
        box_candidates: list[BoxCandidate],
        table_candidates: list[TableCandidate],
        text_blocks: list[TextBlock],
        context: dict[str, Any] | None = None,
    ) -> tuple[list[LinkedField], list[StructureEvidence]]:
        """Link labels to field positions using LLM reasoning.

        Uses LangChain with structured output to:
        1. Build prompt with spatial context
        2. Call LLM for semantic analysis
        3. Parse structured response
        4. Generate evidence records

        Falls back to proximity-based matching if LLM is unavailable.

        Args:
            page: Page number being processed
            page_image: Rendered page image bytes (not used in text-based mode)
            label_candidates: Potential label texts with positions
            box_candidates: Detected input boxes/fields
            table_candidates: Detected table structures
            text_blocks: Native PDF text blocks
            context: Additional context

        Returns:
            Tuple of linked fields and supporting evidence
        """
        fields: list[LinkedField] = []
        evidence: list[StructureEvidence] = []

        # Try LLM-based linking first
        if self._initialized and label_candidates and box_candidates:
            try:
                response = await self._call_llm(
                    page, label_candidates, box_candidates, context
                )

                # Build lookup maps
                label_map = {l.id: l for l in label_candidates}
                box_map = {b.id: b for b in box_candidates}

                # Process linkages
                for linkage in response.linkages:
                    label = label_map.get(linkage.label_id)
                    box = box_map.get(linkage.box_id)

                    if not label or not box:
                        logger.warning(
                            f"Invalid linkage: label={linkage.label_id}, box={linkage.box_id}"
                        )
                        continue

                    field_id = f"field_{uuid4().hex[:8]}"
                    evidence_id = f"ev_{uuid4().hex[:8]}"

                    # Create evidence record
                    ev = StructureEvidence(
                        id=evidence_id,
                        kind=EvidenceKind.LLM_LINKING,
                        field_id=field_id,
                        document_id="",  # Will be set by service
                        page=page,
                        bbox=label.bbox,
                        text=label.text,
                        confidence=linkage.confidence,
                        rationale=linkage.rationale,
                    )
                    evidence.append(ev)

                    # Create linked field
                    linked_field = LinkedField(
                        id=field_id,
                        name=linkage.field_name,
                        field_type=linkage.field_type,
                        page=page,
                        bbox=box.bbox,
                        anchor_bbox=label.bbox,
                        confidence=linkage.confidence,
                        needs_review=linkage.confidence < self.confidence_threshold,
                        evidence_refs=(evidence_id,),
                        label_candidate_id=label.id,
                        box_candidate_id=box.id,
                    )
                    fields.append(linked_field)

                logger.info(
                    f"LLM linked {len(fields)} fields on page {page}, "
                    f"{len(response.unlinked_boxes)} boxes unlinked"
                )

            except Exception as e:
                logger.warning(f"LLM linking failed, falling back to proximity: {e}")
                if self.use_fallback:
                    fields, evidence = self._fallback_proximity_linking(
                        page, label_candidates, box_candidates
                    )

        elif self.use_fallback:
            # Use fallback when LLM not available
            fields, evidence = self._fallback_proximity_linking(
                page, label_candidates, box_candidates
            )

        # Process tables for additional fields
        table_fields, table_evidence = self._process_tables(
            page, table_candidates, label_candidates
        )
        fields.extend(table_fields)
        evidence.extend(table_evidence)

        return fields, evidence

    def _fallback_proximity_linking(
        self,
        page: int,
        label_candidates: list[LabelCandidate],
        box_candidates: list[BoxCandidate],
    ) -> tuple[list[LinkedField], list[StructureEvidence]]:
        """Fallback proximity-based label-to-box linking.

        Used when LLM is not available or fails.

        Args:
            page: Page number
            label_candidates: Label candidates
            box_candidates: Box candidates

        Returns:
            Tuple of linked fields and evidence
        """
        fields: list[LinkedField] = []
        evidence: list[StructureEvidence] = []

        for box in box_candidates:
            best_label = self._find_closest_label(box, label_candidates)

            if best_label:
                field_id = f"field_{uuid4().hex[:8]}"
                evidence_id = f"ev_{uuid4().hex[:8]}"

                field_type = self._infer_field_type(best_label, box)
                confidence = self._calculate_confidence(best_label, box)

                ev = StructureEvidence(
                    id=evidence_id,
                    kind=EvidenceKind.PROXIMITY,
                    field_id=field_id,
                    document_id="",
                    page=page,
                    bbox=best_label.bbox,
                    text=best_label.text,
                    confidence=confidence,
                    rationale=(
                        f"Proximity match: Label '{best_label.text}' linked to box "
                        f"(distance: {self._calculate_distance(best_label.bbox, box.bbox):.1f}px)"
                    ),
                )
                evidence.append(ev)

                linked_field = LinkedField(
                    id=field_id,
                    name=best_label.text,
                    field_type=field_type,
                    page=page,
                    bbox=box.bbox,
                    anchor_bbox=best_label.bbox,
                    confidence=confidence,
                    needs_review=confidence < self.confidence_threshold,
                    evidence_refs=(evidence_id,),
                    label_candidate_id=best_label.id,
                    box_candidate_id=box.id,
                )
                fields.append(linked_field)

        return fields, evidence

    def _find_closest_label(
        self, box: BoxCandidate, labels: list[LabelCandidate], language: str = "auto"
    ) -> LabelCandidate | None:
        """Find the best label for a box using weighted scoring.

        Uses multiple factors to determine the best match:
        - Distance (closer = better)
        - Direction (reading direction preference)
        - Semantic hints (label type matching)
        - Alignment (horizontal/vertical alignment)

        Args:
            box: Box to find label for
            labels: Available label candidates
            language: Language hint for reading direction ("ja", "en", "auto")

        Returns:
            Best matching label or None if no suitable label found
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
        distance = self._calculate_distance(label.bbox, box.bbox)
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
            box.bbox.width < 40 and box.bbox.height < 40 and
            0.7 < box.bbox.width / max(box.bbox.height, 1) < 1.5
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

    def _is_valid_label_position(self, label_bbox: BBox, box_bbox: BBox) -> bool:
        """Check if label is in valid position relative to box.

        Valid positions (typical form layouts):
        - Label above box (same column)
        - Label to the left of box (same row)
        """
        # Label is above box
        label_below_top = label_bbox.y + label_bbox.height
        if label_below_top <= box_bbox.y + 20:  # Allow some overlap
            # Check horizontal alignment
            label_center_x = label_bbox.x + label_bbox.width / 2
            box_center_x = box_bbox.x + box_bbox.width / 2
            if abs(label_center_x - box_center_x) < max(box_bbox.width, 100):
                return True

        # Label is to the left of box
        label_right = label_bbox.x + label_bbox.width
        if label_right <= box_bbox.x + 20:  # Allow some overlap
            # Check vertical alignment
            label_center_y = label_bbox.y + label_bbox.height / 2
            box_center_y = box_bbox.y + box_bbox.height / 2
            if abs(label_center_y - box_center_y) < max(box_bbox.height, 30):
                return True

        return False

    def _calculate_distance(self, bbox1: BBox, bbox2: BBox) -> float:
        """Calculate distance between two bboxes.

        Uses center-to-edge distance for proximity calculation.
        """
        # Center of bbox1
        c1x = bbox1.x + bbox1.width / 2
        c1y = bbox1.y + bbox1.height / 2

        # Nearest point on bbox2
        nearest_x = max(bbox2.x, min(c1x, bbox2.x + bbox2.width))
        nearest_y = max(bbox2.y, min(c1y, bbox2.y + bbox2.height))

        # Euclidean distance
        return ((c1x - nearest_x) ** 2 + (c1y - nearest_y) ** 2) ** 0.5

    def _calculate_confidence(
        self, label: LabelCandidate, box: BoxCandidate
    ) -> float:
        """Calculate linking confidence score.

        Stub: Based on distance and source confidence.
        TODO: Use LLM confidence from response.
        """
        distance = self._calculate_distance(label.bbox, box.bbox)

        # Distance-based confidence (closer = higher)
        distance_conf = max(0.3, 1.0 - distance / 200)

        # Combine with source confidences
        combined = (
            distance_conf * 0.5
            + label.confidence * 0.3
            + box.confidence * 0.2
        )

        return round(min(1.0, max(0.0, combined)), 2)

    def _infer_field_type(
        self, label: LabelCandidate, box: BoxCandidate
    ) -> str:
        """Infer field type from label and box characteristics.

        Stub: Uses simple heuristics.
        TODO: Use LLM for better inference.
        """
        # Check semantic hints first
        if label.semantic_hints:
            hint = label.semantic_hints[0]
            type_map = {
                "date": "date",
                "amount": "number",
                "checkbox": "checkbox",
                "signature": "signature",
                "phone": "text",
                "email": "text",
            }
            if hint in type_map:
                return type_map[hint]

        # Check box type
        if box.box_type == "checkbox":
            return "checkbox"
        if box.box_type == "signature":
            return "signature"

        # Check box dimensions for type hints
        aspect_ratio = box.bbox.width / max(box.bbox.height, 1)

        if aspect_ratio < 1.5 and box.bbox.width < 40:
            return "checkbox"

        return "text"

    def _process_tables(
        self,
        page: int,
        tables: list[TableCandidate],
        labels: list[LabelCandidate],
    ) -> tuple[list[LinkedField], list[StructureEvidence]]:
        """Process table structures for field extraction.

        Stub: Basic table header-to-cell linking.
        TODO: Full LLM-based table understanding.
        """
        fields: list[LinkedField] = []
        evidence: list[StructureEvidence] = []

        for table in tables:
            if not table.cells:
                continue

            # Find header cells
            header_cells = [c for c in table.cells if c.is_header]
            data_cells = [c for c in table.cells if not c.is_header]

            # Link headers to data cells in same column
            for data_cell in data_cells:
                header = next(
                    (h for h in header_cells if h.col == data_cell.col),
                    None,
                )
                if header and header.text:
                    field_id = f"field_{uuid4().hex[:8]}"
                    evidence_id = f"ev_{uuid4().hex[:8]}"

                    ev = StructureEvidence(
                        id=evidence_id,
                        kind=EvidenceKind.TABLE_STRUCTURE,
                        field_id=field_id,
                        document_id="",
                        page=page,
                        bbox=header.bbox,
                        text=header.text,
                        confidence=0.8,
                        rationale=(
                            f"STUB: Table header '{header.text}' linked to "
                            f"data cell at row {data_cell.row}, col {data_cell.col}"
                        ),
                    )
                    evidence.append(ev)

                    linked_field = LinkedField(
                        id=field_id,
                        name=header.text,
                        field_type="text",
                        page=page,
                        bbox=data_cell.bbox,
                        anchor_bbox=header.bbox,
                        confidence=0.8,
                        needs_review=False,
                        evidence_refs=(evidence_id,),
                        table_id=table.id,
                    )
                    fields.append(linked_field)

        return fields, evidence


# Protocol verification
def _verify_protocol() -> None:
    """Verify that LangChainFieldLabellingAgent implements the protocol."""
    agent: FieldLabellingAgentPort = LangChainFieldLabellingAgent()  # noqa: F841
