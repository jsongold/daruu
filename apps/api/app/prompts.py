"""LLM prompt classes: each mode has a Prompt class with build(Context) -> Prompt."""

import json
import math

from app.models import (
    AskContext,
    Annotation,
    FillContext,
    FormField,
    MapContext,
    Prompt,
    RulesContext,
    RuleType,
    TextBlock,
)


# ---------------------------------------------------------------------------
# Spatial helpers (used by MapPrompt)
# ---------------------------------------------------------------------------

def _to_ivb(bbox_normalized: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """Convert normalized 0-1 bbox (x, y, w, h) to IVB (x1, y1, x2, y2) 0-999."""
    x, y, w, h = bbox_normalized
    x1 = max(0, min(999, int(x * 999)))
    y1 = max(0, min(999, int(y * 999)))
    x2 = max(0, min(999, int((x + w) * 999)))
    y2 = max(0, min(999, int((y + h) * 999)))
    return x1, y1, x2, y2


def _direction_score(field_bbox: tuple[float, float, float, float], label_bbox: tuple[float, float, float, float]) -> tuple[float, str]:
    """Compute spatial distance score and direction from label to field."""
    fx, fy, fw, fh = field_bbox
    lx, ly, lw, lh = label_bbox

    # Center points
    fcx, fcy = fx + fw / 2, fy + fh / 2
    lcx, lcy = lx + lw / 2, ly + lh / 2

    # Check overlap
    overlap = (lx < fx + fw and lx + lw > fx and ly < fy + fh and ly + lh > fy)
    if overlap:
        return 0.0, "overlap"

    base_dist = math.sqrt((fcx - lcx) ** 2 + (fcy - lcy) ** 2)
    dx = fcx - lcx  # positive = label is to the left of field
    dy = fcy - lcy  # positive = label is above field

    if abs(dx) >= abs(dy):
        direction = "left" if dx > 0 else "right"
    else:
        direction = "above" if dy > 0 else "below"

    multipliers = {"left": 0.8, "above": 0.9, "right": 2.0, "below": 1.5, "overlap": 0.5}
    score = base_dist * multipliers[direction]

    # Vertical alignment bonus: same row -> x0.7
    avg_height = (fh + lh) / 2
    if avg_height > 0 and abs(fcy - lcy) < avg_height * 0.5:
        score *= 0.7

    return score, direction


# ---------------------------------------------------------------------------
# Private user-prompt builders
# ---------------------------------------------------------------------------

def _build_map_user(
    fields: list[FormField],
    text_blocks: list[TextBlock],
    confirmed_annotations: list[Annotation],
    top_k: int,
) -> str:
    """Build the Map mode user prompt with spatial candidate data in IVB format."""
    pages: dict[int, list[FormField]] = {}
    for f in fields:
        pages.setdefault(f.page, []).append(f)

    blocks_by_page: dict[int, list[TextBlock]] = {}
    for b in text_blocks:
        blocks_by_page.setdefault(b.page, []).append(b)

    lines: list[str] = ["Match each field to its best candidate label.\n"]

    for page_num in sorted(pages.keys()):
        lines.append(f"--- Page {page_num} ---")
        page_blocks = blocks_by_page.get(page_num, [])

        for field in pages[page_num]:
            if field.bbox is None:
                continue
            fb = (field.bbox.x, field.bbox.y, field.bbox.width, field.bbox.height)
            f_ivb = _to_ivb(fb)
            lines.append(f"{field.id} [{f_ivb[0]},{f_ivb[1]},{f_ivb[2]},{f_ivb[3]}] type={field.field_type.value}")

            scored: list[tuple[float, str, TextBlock]] = []
            for block in page_blocks:
                bb = (block.bbox.x, block.bbox.y, block.bbox.width, block.bbox.height)
                score, direction = _direction_score(fb, bb)
                scored.append((score, direction, block))

            scored.sort(key=lambda t: t[0])
            top = scored[:top_k]

            if top:
                parts = []
                for score, direction, block in top:
                    b_ivb = _to_ivb((block.bbox.x, block.bbox.y, block.bbox.width, block.bbox.height))
                    parts.append(f'"{block.text}"[{b_ivb[0]},{b_ivb[1]},{b_ivb[2]},{b_ivb[3]}] {direction}')
                lines.append(f"  candidates: {' | '.join(parts)}")
            else:
                lines.append("  candidates: (none)")

    if confirmed_annotations:
        lines.append("\n## Confirmed mappings for this form (use as reference)")
        for ann in confirmed_annotations:
            if ann.label_bbox and ann.field_bbox:
                l_ivb = _to_ivb((ann.label_bbox.x, ann.label_bbox.y, ann.label_bbox.width, ann.label_bbox.height))
                f_ivb = _to_ivb((ann.field_bbox.x, ann.field_bbox.y, ann.field_bbox.width, ann.field_bbox.height))
                lines.append(
                    f'- "{ann.label_text}" [{l_ivb[0]},{l_ivb[1]},{l_ivb[2]},{l_ivb[3]}] '
                    f'-> {ann.field_id} [{f_ivb[0]},{f_ivb[1]},{f_ivb[2]},{f_ivb[3]}]'
                )

    return "\n".join(lines)


def _build_understand_user(fields: list[FormField], text_blocks: list[TextBlock]) -> str:
    """Build user prompt for document rule extraction."""
    field_list = [
        {"field_id": f.id, "name": f.name, "type": f.field_type.value, "page": f.page}
        for f in fields
    ]
    text_list = [
        {"text": b.text, "page": b.page}
        for b in text_blocks
    ]
    parts = [
        f"Form fields:\n{json.dumps(field_list, ensure_ascii=False)}",
        f"Visible text on the form:\n{json.dumps(text_list, ensure_ascii=False)}",
    ]
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Prompt classes
# ---------------------------------------------------------------------------

class FillPrompt:
    SYSTEM = """\
You are a form-filling assistant.

1. Apply format and calculation rules provided in "Rules".
   Examples: convert to required character type; apply date format; derive calculated values.

2. Fill fields from "User information" using semantic matching.
   Examples: name/full_name -> name field; address -> address field; dob/birth_date -> date of birth field.

3. If "User response to previous question" is provided, use it to fill conditional fields.
   Example: user confirmed spouse exists -> fill spouse name fields from user_info.

Return ONLY valid JSON. No markdown.
{"fields": [{"field_id": "<id>", "value": "<val>"}]}"""

    @staticmethod
    def build(ctx: FillContext) -> Prompt:
        user = json.dumps(ctx.model_dump(mode="json"), ensure_ascii=False)
        return Prompt(system=FillPrompt.SYSTEM, user=user)


class MapPrompt:
    SYSTEM = """You are a Japanese PDF form field identification expert.
Your task: match each form field to its most relevant text label from the provided candidates.

## Coordinate system
- Integer-Valued Binning: 0-999 grid, origin at top-left
- [x1, y1, x2, y2] where (x1,y1) = top-left corner, (x2,y2) = bottom-right corner

## Japanese form layout patterns
- Labels are typically LEFT of or ABOVE their field
- Dense forms may have labels INSIDE or OVERLAPPING the field area
- Common label patterns: 氏名, フリガナ, 住所, 生年月日, 電話番号, etc.
- Checkbox labels may be to the RIGHT of the checkbox

## Output format
Return ONLY a JSON object with a "results" key. No markdown, no explanation, no code fences.
{"results": [{"field_id":"<id>","label":"<label text or null>","semantic_key":"<snake_case>","confidence":<0-100>}, ...]}

## Fields
- field_id: exact field ID from input
- label: matched text (exact string from candidates), or null if no match
- semantic_key: English snake_case key describing the field's purpose
- confidence: 0-100 integer (90-100: directly adjacent; 70-89: nearby; 50-69: inferred; 0-49: weak/no match)

## Rules
- Process ALL fields. Never skip a field.
- For each field, return exactly one result.
- left/above labels have higher prior probability than right/below."""

    @staticmethod
    def build(ctx: MapContext) -> Prompt:
        user = _build_map_user(ctx.fields, ctx.text_blocks, ctx.confirmed_annotations, ctx.top_k)
        return Prompt(system=MapPrompt.SYSTEM, user=user)


class RulesPrompt:
    SYSTEM = """\
You are a document analysis assistant for PDF forms.
Analyze the form's fields and visible text to extract all filling rules and instructions.

## Part 1: Full rulebook (natural language)

Write a complete, human-readable Markdown rulebook for this form.
- Write in the same language as the form
- Organize into sections: Format Rules, Conditional Rules, Calculation Rules
- Be thorough: include all constraints, date formats, allowed values, mandatory fields, and conditional logic

## Part 2: Structured rules (for the fill/ask pipeline)

Classify each rule into one of:
- "conditional": applies only when a user-specific condition holds (e.g., "fill only if married")
- "format": specifies how to write a value (e.g., all caps, date format YYYY/MM/DD)
- "calculation": value is derived from other fields or given data

For each "conditional" rule also provide:
- question: the single yes/no or multiple-choice question that resolves the condition (write in the form's language)
- options: ["Yes", "No"] for yes/no conditions; list the available choices for multiple-choice

Return ONLY valid JSON. No markdown, no explanation.
{"rulebook_text": "...", "rules": [{"type": "conditional", "rule_text": "...", "question": "...", "options": ["Yes", "No"]}, {"type": "format", "rule_text": "...", "question": null, "options": []}]}"""

    @staticmethod
    def build(ctx: RulesContext) -> Prompt:
        user = _build_understand_user(ctx.fields, ctx.text_blocks)
        return Prompt(system=RulesPrompt.SYSTEM, user=user)


class AskPrompt:
    SYSTEM = ""

    @staticmethod
    def build(ctx: AskContext) -> Prompt:
        questions = [
            {"question": r.question, "options": list(r.options)}
            for r in ctx.rules
            if r.type == RuleType.CONDITIONAL and r.question
        ]
        return Prompt(system="", user=json.dumps({"questions": questions}, ensure_ascii=False))
