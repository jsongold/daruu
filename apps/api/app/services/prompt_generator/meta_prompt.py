"""Meta-prompt for generating form-specific field mappings via LLM.

The meta-prompt instructs the LLM to analyze form fields with their
spatial context (nearby_labels) and PDF text, then produce a structured
JSON mapping of field_ids to semantic labels, sections, and rules.
"""

from __future__ import annotations

from typing import Any

from app.domain.models.form_context import FormContext

PROMPT_GENERATION_SYSTEM_PROMPT = """\
You are a PDF form analysis expert. Your task is to analyze a PDF form's \
field structure and produce:
1. A semantic label for every field_id
2. Explicit coordinate-based mappings from data source keys to form fields

## Your Output

Return a valid JSON object with this exact structure:
{
  "form_title": "Form title in the form's language",
  "form_language": "ja",
  "field_labels": {
    "Text1": "Semantic label for Text1",
    "Text2": "Semantic label for Text2",
    "Dropdown1": "Semantic label for Dropdown1"
  },
  "key_field_mappings": [
    {
      "source_key": "氏名",
      "field_id": "Text6",
      "bbox": {"page": 1, "x": 150, "y": 300},
      "reasoning": "nearby_label '氏名' directly above field"
    }
  ],
  "sections": [
    {"name": "Section name", "field_ids": ["Text1", "Text2"]}
  ],
  "format_rules": {
    "Text9-1": "12-digit number, no hyphens",
    "Dropdown1": "Options: value1|value2|value3"
  },
  "fill_rules": [
    "Conditional rule extracted from the form text"
  ]
}

## Key-Field Mapping Rules (CRITICAL)

The `key_field_mappings` array is the MOST IMPORTANT output. For every \
data source key provided, you MUST find the best matching field_id based on:

1. **Coordinate proximity**: Match the data source key to the field whose \
nearby_label or semantic label best matches, using the field's bbox \
(page, x, y) to resolve ambiguity when multiple fields share similar labels.
2. **Directional labels**: nearby_labels indicate text physically near \
the field on the PDF. A nearby_label matching a data source key is the \
strongest signal.
3. **One-to-many**: A single data source key may map to multiple fields \
(e.g. a name split across family_name + given_name fields). Include \
separate entries for each.
4. **Format splitting**: If a data source value needs to be split across \
fields (e.g. date → year/month/day dropdowns, phone → area/number), \
list each target field with a note in `reasoning`.

Include ALL data source keys in `key_field_mappings`, even if no good \
match exists (set field_id to null with reasoning explaining why).

## Guidelines

- Use the form's own language for labels, section names, and rules.
- Every field_id from the input MUST appear in `field_labels`.
- Use `nearby_labels` (directional text near each field) as the primary \
signal for label identification.
- When nearby_labels are ambiguous, use the field's position (bbox) and \
the surrounding PDF text blocks to disambiguate.
- Include format constraints in `format_rules` when evident (digit counts, \
date formats, dropdown options).
- Extract conditional fill rules from the PDF text (instructions, footnotes).

## Output Format

Return ONLY the JSON object. Do not wrap it in markdown code blocks \
or add any preamble.\
"""


def build_prompt_generation_user_prompt(
    context: FormContext,
    text_blocks: list[dict[str, Any]],
    similar_prompts: list[str] | None = None,
) -> str:
    """Build the user prompt for the prompt generation LLM call.

    Includes per-field spatial context (nearby_labels, bbox, type) and
    the full PDF text blocks for rule extraction.

    Args:
        context: FormContext with fields and their label_candidates.
        text_blocks: Raw text blocks extracted from the PDF.
        similar_prompts: Previously generated prompts for similar forms
            (used as few-shot examples).

    Returns:
        User prompt string for the meta-prompt LLM call.
    """
    lines: list[str] = []

    # Section 1: Fields with spatial context
    lines.append("## Form Fields\n")
    for field in context.fields:
        lines.append(f"Field: {field.field_id}")
        lines.append(f"  type: {field.field_type}")

        if field.page is not None:
            bbox_parts = []
            if field.x is not None and field.y is not None:
                bbox_parts.append(f"page={field.page}, x={field.x:.0f}, y={field.y:.0f}")
            if field.width is not None and field.height is not None:
                bbox_parts.append(f"w={field.width:.0f}, h={field.height:.0f}")
            if bbox_parts:
                lines.append(f"  bbox: {', '.join(bbox_parts)}")

        if field.label_candidates:
            for lc in field.label_candidates:
                direction = "nearby"
                if hasattr(lc, "direction"):
                    direction = lc.direction
                lines.append(f'  nearby_labels ({direction}): "{lc.text}"')

        if field.label and field.label != field.field_id:
            lines.append(f'  current_label: "{field.label}"')

        lines.append("")

    # Section 2: Data source keys (for key-field mapping)
    if context.data_sources:
        lines.append("## Data Source Keys (map these to fields)\n")
        for ds in context.data_sources:
            lines.append(f"Source: {ds.source_name} ({ds.source_type})")
            if ds.extracted_fields:
                for key, value in ds.extracted_fields.items():
                    # Show key and a truncated value as hint
                    val_preview = str(value)[:80] if value else ""
                    lines.append(f'  - key: "{key}" (value: "{val_preview}")')
            lines.append("")

    # Section 3: PDF text blocks (for rule extraction)
    lines.append("## PDF Text Content\n")
    for block in text_blocks:
        text = block.get("text", "").strip()
        if not text:
            continue
        page = block.get("page", "?")
        lines.append(f"[page {page}] {text}")
    lines.append("")

    # Section 4: Similar prompts as few-shot examples
    if similar_prompts:
        lines.append("## Reference: Similar Form Prompts\n")
        lines.append(
            "Below are prompts generated for similar forms. "
            "Use them as reference for structure and style.\n"
        )
        for i, prompt in enumerate(similar_prompts, 1):
            lines.append(f"--- Similar Prompt {i} ---")
            lines.append(prompt)
            lines.append("--- End ---\n")

    return "\n".join(lines)
