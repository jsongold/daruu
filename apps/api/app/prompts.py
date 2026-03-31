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
from app.spatial import direction_score as _direction_score


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


# ---------------------------------------------------------------------------
# Private user-prompt builders
# ---------------------------------------------------------------------------

def _build_map_user(
    fields: list[FormField],
    text_blocks: list[TextBlock],
    confirmed_annotations: list[Annotation],
    top_k: int,
    heuristic_maps: list | None = None,
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
            fb = (field.bbox.x, field.bbox.y,
                  field.bbox.width, field.bbox.height)
            f_ivb = _to_ivb(fb)
            lines.append(
                f"{field.id} [{f_ivb[0]},{f_ivb[1]},{f_ivb[2]},{f_ivb[3]}] type={field.field_type.value}")

            scored: list[tuple[float, str, TextBlock]] = []
            for block in page_blocks:
                bb = (block.bbox.x, block.bbox.y,
                      block.bbox.width, block.bbox.height)
                score, direction = _direction_score(fb, bb)
                scored.append((score, direction, block))

            scored.sort(key=lambda t: t[0])
            top = scored[:top_k]

            if top:
                parts = []
                for score, direction, block in top:
                    b_ivb = _to_ivb((block.bbox.x, block.bbox.y,
                                    block.bbox.width, block.bbox.height))
                    parts.append(
                        f'"{block.text}"[{b_ivb[0]},{b_ivb[1]},{b_ivb[2]},{b_ivb[3]}] {direction}')
                lines.append(f"  candidates: {' | '.join(parts)}")
            else:
                lines.append("  candidates: (none)")

    if confirmed_annotations:
        lines.append(
            "\n## Confirmed mappings for this form (use as reference)")
        for ann in confirmed_annotations:
            if ann.label_bbox and ann.field_bbox:
                l_ivb = _to_ivb((ann.label_bbox.x, ann.label_bbox.y,
                                ann.label_bbox.width, ann.label_bbox.height))
                f_ivb = _to_ivb((ann.field_bbox.x, ann.field_bbox.y,
                                ann.field_bbox.width, ann.field_bbox.height))
                lines.append(
                    f'- "{ann.label_text}" [{l_ivb[0]},{l_ivb[1]},{l_ivb[2]},{l_ivb[3]}] '
                    f'-> {ann.field_id} [{f_ivb[0]},{f_ivb[1]},{f_ivb[2]},{f_ivb[3]}]'
                )

    if heuristic_maps:
        lines.append(
            "\n## Heuristic spatial matches (verify and correct)")
        for m in heuristic_maps:
            if m.label_text:
                lines.append(
                    f'- {m.field_id} -> "{m.label_text}" (confidence={m.confidence})')

    return "\n".join(lines)


def _build_understand_user(fields: list[FormField], text_blocks: list[TextBlock]) -> str:
    """Build user prompt for form rule extraction."""
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
    """Fill mode: compact plain-text prompt with integer indices."""

    SYSTEM = """\
Form-fill assistant for PDF forms in any language.

## Input
User provides general context about themselves or their situation as free text.
This is NOT structured data -- it is natural language describing who they are,
what they do, their circumstances, etc.
Extract relevant facts to decide how to fill each field.

## Matching
Match user context to form fields by MEANING, not by position or language.
Cross-language matching is required:
- A field labeled in one language must match user context in another language
- Use semantic_key (English snake_case) as the bridge between languages
- Example: semantic_key="full_name" matches context mentioning a person's name
  regardless of whether the input is in English, Japanese, or any other language

## Hints
Some fields include a hint (resolved from prior Q&A with the user).
The hint tells you HOW to fill the field -- follow it exactly.
Examples: specific date format, which option to select, a derived value.

## Output
Types: text(default), checkbox(true/false), radio, select, date.
Output: index:value, one per line. No JSON.
Omit fields you cannot fill from the given context.
Do not guess or fabricate values not present in the input."""

    @staticmethod
    def build(ctx: FillContext) -> tuple[Prompt, list[str]]:
        """Build compact prompt and return (prompt, index_to_field_id mapping).

        The caller must keep index_to_field_id to resolve LLM output back to field_ids.
        """
        lines = ["input"]
        for v in ctx.user_info.values():
            lines.append(v)

        lines.append("form_schema")
        index_to_field_id: list[str] = []
        for i, f in enumerate(ctx.fields):
            parts = [str(i), f.label or "", f.semantic_key or ""]
            if f.type != "text":
                parts.append(f.type)
            if f.format_rule:
                if f.type == "text":
                    parts.append("")  # placeholder for type
                parts.append(f.format_rule)
            lines.append("|".join(parts))
            index_to_field_id.append(f.field_id)

        return Prompt(system=FillPrompt.SYSTEM, user="\n".join(lines)), index_to_field_id

    @staticmethod
    def parse(content: str, index_to_field_id: list[str]) -> list[dict]:
        """Parse LLM output (index:value lines) back to [{field_id, value}]."""
        filled: list[dict] = []
        for line in content.strip().splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            idx_str, _, value = line.partition(":")
            try:
                idx = int(idx_str.strip())
            except ValueError:
                continue
            if 0 <= idx < len(index_to_field_id) and value:
                filled.append({
                    "field_id": index_to_field_id[idx],
                    "value": value.strip(),
                })
        return filled


class MapPrompt:
    SYSTEM = """You are a PDF form field identification expert.
Your task: match each form field to its most relevant text label from the provided candidates.

## Coordinate system
- Integer-Valued Binning: 0-999 grid, origin at top-left
- [x1, y1, x2, y2] where (x1,y1) = top-left corner, (x2,y2) = bottom-right corner

## Form layout patterns
- Labels are typically LEFT of or ABOVE their field
- Dense forms may have labels INSIDE or OVERLAPPING the field area
- Checkbox labels may be to the RIGHT of the checkbox

## Label vs decoration -- general principles
A label is descriptive text that tells the user WHAT to write in a field.
Decoration is visual formatting that is NOT a label:
- Single punctuation or symbols (dots, bullets, boxes, circles, dashes)
- Separator characters between field parts (e.g. dots between year/month/day)
- Selection option text that is part of the field's UI (e.g. "Yes/No", era choices)
- Parenthetical instructions or footnotes
- Row/column numbers or section markers

When the best candidate is decoration, return label=null and confidence=0.
A field with no meaningful label is better than a field with a wrong label.

## Checkbox and radio fields
- The label is the text that describes what selecting this option MEANS
- Use the descriptive text adjacent to the widget, not the widget symbol itself
- Example: "□ Married" -> label="Married", not label="□"

## Output format
Return ONLY a JSON object. No markdown, no explanation, no code fences.
{"form_name":"<official form name, e.g. I-130, W-2, or null if unknown>","results": [{"field_id":"<id>","label":"<label text or null>","semantic_key":"<snake_case>","confidence":<0-100>}, ...]}

## Top-level fields
- form_name: official form identifier if visible (e.g. "I-130", "W-2", "履歴書"), or null

## Per-field result fields
- field_id: exact field ID from input
- label: matched text (exact string from candidates), or null if no match
- semantic_key: English snake_case key describing the field's purpose
- confidence: 0-100 integer (90-100: directly adjacent; 70-89: nearby; 50-69: inferred; 0-49: weak/no match)

## Rules
- Process ALL fields. For fields with no meaningful label nearby, return label=null and confidence=0.
- For each field, return exactly one result.
- left/above labels have higher prior probability than right/below."""

    @staticmethod
    def build(ctx: MapContext) -> Prompt:
        user = _build_map_user(
            ctx.fields, ctx.text_blocks,
            ctx.confirmed_annotations, ctx.top_k,
            heuristic_maps=ctx.heuristic_maps,
        )
        return Prompt(system=MapPrompt.SYSTEM, user=user)


class RulesPrompt:
    SYSTEM = """\
You are a form analysis assistant for PDF forms.
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

CRITICAL: Every rule MUST include "field_ids" — the list of field_id values that the rule governs.
- A format rule for date fields should list all date field_ids it applies to.
- A conditional rule like "fill spouse fields only if married" should list all spouse-related field_ids.
- If a rule applies to all fields, list them all explicitly.

For each "conditional" rule also provide:
- question: the single yes/no or multiple-choice question that resolves the condition (write in the form's language)
- options: ["Yes", "No"] for yes/no conditions; list the available choices for multiple-choice

Return ONLY valid JSON. No markdown, no explanation.
{"description": "<one-sentence English summary of the form's purpose for semantic search>", "rulebook_text": "...", "rules": [{"type": "conditional", "rule_text": "...", "field_ids": ["field_abc"], "question": "...", "options": ["Yes", "No"]}, {"type": "format", "rule_text": "...", "field_ids": ["field_xyz"], "question": null, "options": []}]}

## description field
- Write a concise English summary of the form's purpose (e.g. "Petition for alien relative filed with USCIS to establish family relationship for immigration")
- This is used for semantic search to find similar forms"""

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
