"""ContextService: single owner of LLM context assembly for Fill/Ask."""

import logging
import math

from app.models import (
    AlreadyFilledField,
    Annotation,
    BBox,
    EnrichedField,
    FieldLabelMap,
    FieldSection,
    FieldType,
    FillContext,
    FormField,
    HistoryMessage,
    Mapping,
    PageContext,
    RuleItem,
    TextBlock,
)

logger = logging.getLogger(__name__)

# Spatial thresholds (normalized 0-1 coordinates)
_SECTION_Y_THRESHOLD = 0.05  # fields within 5% vertical distance = same section
_NEARBY_TEXT_DISTANCE = 0.03  # text blocks within 3% distance
_NEARBY_TEXT_MAX = 5


def _bbox_center(bbox: BBox) -> tuple[float, float]:
    return bbox.x + bbox.width / 2, bbox.y + bbox.height / 2


def _bbox_distance(a: BBox, b: BBox) -> float:
    ax, ay = _bbox_center(a)
    bx, by = _bbox_center(b)
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def _find_nearby_text(
    field: FormField,
    text_blocks: list[TextBlock],
    used_labels: set[str],
) -> list[str]:
    """Find text blocks near a field that are not already used as labels."""
    if field.bbox is None:
        return []

    scored: list[tuple[float, str]] = []
    for block in text_blocks:
        if block.text in used_labels:
            continue
        dist = _bbox_distance(field.bbox, block.bbox)
        if dist <= _NEARBY_TEXT_DISTANCE:
            scored.append((dist, block.text))

    scored.sort(key=lambda t: t[0])
    return [text for _, text in scored[:_NEARBY_TEXT_MAX]]


def _group_into_sections(
    fields: list[EnrichedField],
    raw_fields: list[FormField],
) -> list[FieldSection]:
    """Group enriched fields into sections by y-coordinate proximity."""
    if not fields:
        return []

    bbox_map = {f.id: f.bbox for f in raw_fields if f.bbox is not None}

    indexed: list[tuple[float, EnrichedField]] = []
    for ef in fields:
        bbox = bbox_map.get(ef.field_id)
        y = bbox.y if bbox else 0.0
        indexed.append((y, ef))

    indexed.sort(key=lambda t: t[0])

    sections: list[FieldSection] = []
    current_fields: list[EnrichedField] = []
    current_y = indexed[0][0]

    for y, ef in indexed:
        if abs(y - current_y) > _SECTION_Y_THRESHOLD and current_fields:
            hint = next(
                (f.label for f in current_fields if f.label),
                None,
            )
            sections.append(FieldSection(section_hint=hint, fields=current_fields))
            current_fields = []
            current_y = y
        current_fields.append(ef)

    if current_fields:
        hint = next((f.label for f in current_fields if f.label), None)
        sections.append(FieldSection(section_hint=hint, fields=current_fields))

    return sections


class ContextService:
    """Assembles structured context for Fill/Ask LLM calls."""

    def build(
        self,
        form_fields: list[FormField],
        text_blocks: list[TextBlock],
        annotations: list[Annotation],
        field_label_maps: list[FieldLabelMap],
        mappings: list[Mapping],
        user_info: dict[str, str],
        rules: list[RuleItem],
        history: list[HistoryMessage],
        user_message: str | None = None,
    ) -> FillContext:
        map_by_field = {m.field_id: m for m in field_label_maps}
        annotation_by_field = {a.field_id: a for a in annotations}
        mapping_by_field = {m.field_id: m for m in mappings}
        used_labels = {m.label_text for m in field_label_maps if m.label_text}
        used_labels |= {a.label_text for a in annotations}

        blocks_by_page: dict[int, list[TextBlock]] = {}
        for b in text_blocks:
            blocks_by_page.setdefault(b.page, []).append(b)

        fields_by_page: dict[int, list[FormField]] = {}
        for f in form_fields:
            fields_by_page.setdefault(f.page, []).append(f)

        enriched_by_page: dict[int, list[EnrichedField]] = {}
        already_filled: list[AlreadyFilledField] = []

        for page_num, page_fields in fields_by_page.items():
            page_blocks = blocks_by_page.get(page_num, [])

            for f in page_fields:
                # C1: Exclude signature fields
                if f.field_type == FieldType.SIGNATURE:
                    continue

                flm = map_by_field.get(f.id)
                ann = annotation_by_field.get(f.id)

                # C1: Exclude no-match fields (confidence=0 and no annotation)
                if flm is None and ann is None:
                    # Still include if field has a value or a name
                    pass
                if flm and flm.confidence == 0 and ann is None:
                    continue

                label = None
                semantic_key = None
                confidence = 0
                confirmed = False

                if ann:
                    label = ann.label_text
                    confirmed = True
                if flm:
                    if flm.label_text:
                        label = label or flm.label_text
                    if flm.semantic_key:
                        semantic_key = flm.semantic_key
                    confidence = flm.confidence

                # C2: Already-filled fields go to separate section
                if f.value is not None and f.value.strip():
                    already_filled.append(AlreadyFilledField(
                        field_id=f.id,
                        label=label or f.name,
                        value=f.value,
                    ))
                    continue

                # Inferred value from mapping (annotation-based fuzzy/LLM match)
                mapping = mapping_by_field.get(f.id)
                inferred_value = mapping.inferred_value if mapping else None

                nearby = _find_nearby_text(f, page_blocks, used_labels)

                enriched = EnrichedField(
                    field_id=f.id,
                    name=f.name,
                    type=f.field_type.value,
                    label=label,
                    semantic_key=semantic_key,
                    confidence=confidence,
                    confirmed=confirmed,
                    current_value=f.value,
                    inferred_value=inferred_value,
                    nearby_text=nearby,
                )
                enriched_by_page.setdefault(page_num, []).append(enriched)

        # B1: Group into pages > sections
        pages: list[PageContext] = []
        for page_num in sorted(enriched_by_page.keys()):
            page_enriched = enriched_by_page[page_num]
            raw_page_fields = fields_by_page.get(page_num, [])
            sections = _group_into_sections(page_enriched, raw_page_fields)
            pages.append(PageContext(page=page_num, sections=sections))

        # A1: Conversation history (last 6)
        recent_history = list(history[-6:]) if history else []

        return FillContext(
            pages=pages,
            user_info=user_info,
            rules=rules,
            history=recent_history,
            already_filled=already_filled,
            user_message=user_message,
        )
