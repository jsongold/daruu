"""FieldEnricher implementations for form field label identification.

Strategy pattern: each implementation encapsulates its own enrichment
logic — no ``if llm`` branching in the builder.

- DirectionalFieldEnricher: directional matching (left/above/right)
- LLMFieldEnricher: LLM-based with compact JSON, proximity pre-filter,
  and page-by-page parallel calls
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from dataclasses import dataclass
from typing import Any, Protocol

from app.domain.models.form_context import FormFieldSpec, LabelCandidate
from app.models.common import BBox
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)

_LLM_PROXIMITY_RADIUS = 200.0

# DirectionalFieldEnricher constants
_DIR_MAX_DISTANCE = 50.0
_DIR_Y_TOL = 15.0
_DIR_ABOVE_X_TOL = 80.0
_MIN_TEXT_LEN = 2
_MAX_LABEL_CANDIDATES = 3


class FieldEnricher(Protocol):
    """Protocol for enriching form fields with label candidates."""

    async def enrich(
        self,
        document_id: str,
        fields: tuple[FormFieldSpec, ...],
    ) -> tuple[FormFieldSpec, ...]: ...


@dataclass(frozen=True)
class NearbyLabel:
    """A text block found directionally near a form field."""

    text: str
    direction: str  # "left" | "above" | "right"
    distance: float  # pt


def compute_directional_labels(
    raw_bbox: BBox,
    text_blocks: list[dict[str, Any]],
    *,
    max_distance: float = _DIR_MAX_DISTANCE,
    y_tolerance: float = _DIR_Y_TOL,
    above_x_tolerance: float = _DIR_ABOVE_X_TOL,
    min_text_length: int = _MIN_TEXT_LEN,
) -> list[NearbyLabel]:
    """Find text blocks directionally near a field (left/above/right).

    Direction rules:
    - Left: block right edge <= field left edge, Y-center diff < y_tolerance
    - Above: block bottom edge <= field top edge, X-center diff < above_x_tolerance
    - Right: block left edge >= field right edge, Y-center diff < y_tolerance

    Args:
        raw_bbox: Field bounding box in PDF points.
        text_blocks: Text blocks with text, page, bbox=[x, y, width, height].
        max_distance: Maximum edge-to-edge distance in points.
        y_tolerance: Maximum Y-center difference for left/right matching.
        above_x_tolerance: Maximum X-center difference for above matching.
        min_text_length: Minimum text length to consider (filters noise).

    Returns:
        List of NearbyLabel sorted by distance (closest first).
    """
    field_left = raw_bbox.x
    field_top = raw_bbox.y
    field_right = raw_bbox.x + raw_bbox.width
    field_cx = raw_bbox.x + raw_bbox.width / 2
    field_cy = raw_bbox.y + raw_bbox.height / 2
    field_page = raw_bbox.page

    results: list[NearbyLabel] = []

    for block in text_blocks:
        text = block.get("text", "")
        if not text or not text.strip():
            continue
        text = text.strip()
        if len(text) < min_text_length:
            continue

        block_page = block.get("page")
        if field_page is not None and block_page is not None and field_page != block_page:
            continue

        bbox = block.get("bbox")
        if not bbox or len(bbox) < 4:
            continue

        block_x, block_y, block_w, block_h = bbox[0], bbox[1], bbox[2], bbox[3]
        block_right = block_x + block_w
        block_bottom = block_y + block_h
        block_cx = block_x + block_w / 2
        block_cy = block_y + block_h / 2

        y_center_diff = abs(field_cy - block_cy)

        # Left: block is to the left of field
        if block_right <= field_left and y_center_diff < y_tolerance:
            dist = field_left - block_right
            if dist <= max_distance:
                results.append(NearbyLabel(text=text, direction="left", distance=dist))
                continue

        # Above: block is above the field
        if block_bottom <= field_top:
            x_center_diff = abs(field_cx - block_cx)
            if x_center_diff < above_x_tolerance:
                dist = field_top - block_bottom
                if dist <= max_distance:
                    results.append(NearbyLabel(text=text, direction="above", distance=dist))
                    continue

        # Right: block is to the right of field
        if block_x >= field_right and y_center_diff < y_tolerance:
            dist = block_x - field_right
            if dist <= max_distance:
                results.append(NearbyLabel(text=text, direction="right", distance=dist))

    results.sort(key=lambda r: r.distance)
    return results


class DirectionalFieldEnricher:
    """Enrich fields with nearby PDF text labels using directional matching.

    Uses directional rules (left/above/right) instead of non-directional
    center-to-center distance, avoiding misidentification of text below
    fields as labels.

    Uses raw AcroForm field coordinates from the backend (PDF points)
    instead of the frontend's normalized 0-1 coordinates.
    """

    def __init__(self, document_service: DocumentService) -> None:
        self._document_service = document_service

    async def enrich(
        self,
        document_id: str,
        fields: tuple[FormFieldSpec, ...],
    ) -> tuple[FormFieldSpec, ...]:
        return self._enrich_fields_directionally(document_id, fields)

    def _enrich_fields_directionally(
        self,
        document_id: str,
        fields: tuple[FormFieldSpec, ...],
    ) -> tuple[FormFieldSpec, ...]:
        field_pages = sorted({f.page for f in fields if f.page is not None})

        try:
            text_blocks = self._document_service.extract_text_blocks(
                document_id, pages=field_pages or None
            )
        except Exception as e:
            logger.warning(f"Failed to extract text blocks for label enrichment: {e}")
            return fields

        if not text_blocks:
            return fields

        raw_bbox_map: dict[str, BBox] = {}
        try:
            acroform_response = self._document_service.get_acroform_fields(document_id)
            if acroform_response:
                for af in acroform_response.fields:
                    if af.bbox:
                        raw_bbox_map[af.field_name] = af.bbox
        except Exception as e:
            logger.warning(f"Failed to get AcroForm fields for label enrichment: {e}")

        enriched: list[FormFieldSpec] = []
        for field in fields:
            raw_bbox = raw_bbox_map.get(field.field_id)
            if not raw_bbox:
                enriched.append(field)
                continue

            nearby = compute_directional_labels(raw_bbox, text_blocks)
            if nearby:
                seen_texts: set[str] = set()
                candidates: list[LabelCandidate] = []
                for label in nearby:
                    if label.text in seen_texts:
                        continue
                    seen_texts.add(label.text)
                    confidence = max(0.0, 1.0 - label.distance / _DIR_MAX_DISTANCE)
                    candidates.append(LabelCandidate(
                        text=label.text,
                        confidence=round(confidence, 3),
                        page=raw_bbox.page,
                    ))
                    if len(candidates) >= _MAX_LABEL_CANDIDATES:
                        break
                enriched.append(
                    field.model_copy(update={"label_candidates": tuple(candidates)})
                )
            else:
                enriched.append(field)

        return tuple(enriched)


class LLMFieldEnricher:
    """Enrich fields with LLM-based label identification.

    Optimizations over the naive single-call approach:
    1. Pre-filter text blocks by proximity (~200pt radius per field)
    2. Compact JSON serialization (abbreviated keys, no indent)
    3. Page-by-page parallel LLM calls via asyncio.gather()
    """

    def __init__(
        self,
        llm_client: Any,
        document_service: DocumentService,
    ) -> None:
        self._llm_client = llm_client
        self._document_service = document_service

    async def enrich(
        self,
        document_id: str,
        fields: tuple[FormFieldSpec, ...],
    ) -> tuple[FormFieldSpec, ...]:
        raw_bbox_map: dict[str, dict[str, Any]] = {}
        try:
            acroform_response = self._document_service.get_acroform_fields(document_id)
            if acroform_response:
                for af in acroform_response.fields:
                    if af.bbox:
                        raw_bbox_map[af.field_name] = {
                            "x": af.bbox.x,
                            "y": af.bbox.y,
                            "width": af.bbox.width,
                            "height": af.bbox.height,
                            "page": af.bbox.page,
                        }
        except Exception as e:
            logger.warning(f"Failed to get AcroForm fields for field enrichment: {e}")

        # Group fields by page for parallel processing
        page_groups: dict[int, list[FormFieldSpec]] = {}
        for field in fields:
            if field.page is not None:
                page_groups.setdefault(field.page, []).append(field)

        from app.services.vision_autofill.prompts import (
            FIELD_IDENTIFICATION_SYSTEM_PROMPT,
            build_field_identification_prompt,
        )

        async def _enrich_page(
            page: int,
            page_fields: list[FormFieldSpec],
        ) -> dict[str, list[LabelCandidate]]:
            """Run LLM enrichment for a single page's fields."""
            try:
                page_blocks = self._document_service.extract_text_blocks_for_page(
                    document_id, page
                )
            except Exception as e:
                logger.warning(
                    "Failed to extract text blocks for page %s: %s", page, e
                )
                return {}

            if not page_blocks:
                return {}

            # Pre-filter to blocks near any field on this page
            nearby_blocks = _prefilter_blocks(page_fields, page_blocks, raw_bbox_map)
            if not nearby_blocks:
                return {}

            user_prompt = build_field_identification_prompt(
                tuple(page_fields), nearby_blocks, raw_bbox_map
            )

            logger.info(
                "Enriching page %s: %d fields, %d blocks",
                page, len(page_fields), len(nearby_blocks),
            )

            try:
                response = await self._llm_client.complete(
                    messages=[
                        {"role": "system", "content": FIELD_IDENTIFICATION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                result = json.loads(response.content)
            except Exception as e:
                logger.warning(
                    "Field enrichment LLM failed for page %s: %s", page, e
                )
                return {}

            label_map: dict[str, list[LabelCandidate]] = {}
            for item in result.get("field_labels", []):
                fid = item.get("field_id", "")
                label_text = item.get("identified_label", "")
                confidence = float(item.get("confidence", 0.0))
                if fid and label_text:
                    label_map.setdefault(fid, []).append(
                        LabelCandidate(
                            text=label_text,
                            confidence=min(max(confidence, 0.0), 1.0),
                            page=page,
                        )
                    )
            return label_map

        # Fire parallel LLM calls — one per page
        page_items = list(page_groups.items())
        page_results = await asyncio.gather(
            *(_enrich_page(page, pfields) for page, pfields in page_items)
        )

        # Merge results from all pages
        merged_labels: dict[str, list[LabelCandidate]] = {}
        for page_label_map in page_results:
            for fid, candidates in page_label_map.items():
                merged_labels.setdefault(fid, []).extend(candidates)

        enriched: list[FormFieldSpec] = []
        for field in fields:
            candidates = merged_labels.get(field.field_id)
            if candidates:
                enriched.append(
                    field.model_copy(update={"label_candidates": tuple(candidates)})
                )
            else:
                enriched.append(field)

        return tuple(enriched)


def _prefilter_blocks(
    fields: list[FormFieldSpec],
    page_blocks: list[dict[str, Any]],
    raw_bbox_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pre-filter text blocks to those within proximity radius of any field.

    Blocks are already page-scoped, so no page filtering needed.
    Only keeps blocks within _LLM_PROXIMITY_RADIUS of at least one field center.
    """
    field_centers: list[tuple[float, float]] = []
    for field in fields:
        bbox = raw_bbox_map.get(field.field_id)
        if bbox:
            cx = bbox["x"] + bbox["width"] / 2
            cy = bbox["y"] + bbox["height"] / 2
            field_centers.append((cx, cy))

    if not field_centers:
        return page_blocks

    nearby: list[dict[str, Any]] = []
    for block in page_blocks:
        text = block.get("text", "")
        if not text or not text.strip():
            continue
        bbox = block.get("bbox")
        if not bbox or len(bbox) < 4:
            continue

        block_cx = bbox[0] + bbox[2] / 2
        block_cy = bbox[1] + bbox[3] / 2

        for fcx, fcy in field_centers:
            dist = math.sqrt((fcx - block_cx) ** 2 + (fcy - block_cy) ** 2)
            if dist <= _LLM_PROXIMITY_RADIUS:
                nearby.append(block)
                break

    return nearby
