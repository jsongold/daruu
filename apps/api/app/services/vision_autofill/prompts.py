"""LLM prompts for vision autofill service.

These prompts guide the LLM to extract information from data sources
and match it to form fields.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domain.models.form_context import FormFieldSpec

AUTOFILL_SYSTEM_PROMPT = """You are a form-filling assistant. Your task is to extract \
information from provided data sources and match it to form fields.

You must return a valid JSON response with this exact structure:
{
  "filled_fields": [
    {"field_id": "...", "value": "...", "confidence": 0.95, "source": "..."},
    ...
  ],
  "warnings": ["any warnings about data quality"]
}

IMPORTANT: Only include filled_fields and warnings. Do NOT include unfilled_fields — \
any field not in filled_fields is automatically treated as unfilled.

## Field Identification:
Each field may include a `nearby_labels` array — text found near the field on \
the PDF page. When `field_id` is generic (e.g. Text1, Text2, Dropdown1), use \
`nearby_labels` to understand the field's semantic purpose. The first label in \
the array is the closest to the field and most likely to be the actual label.

## Compact Fields:
The prompt may contain an "Other Fields" section with compact one-line entries.
Only fill these if you find a clear, high-confidence match in the data sources.
Include any filled compact fields in your filled_fields response using their field_id.

## Data Source Interpretation:
- If data sources contain structured key-value pairs, match keys to fields semantically
- If data sources contain unstructured text, infer values by recognizing patterns \
(names, addresses, numbers, dates) and matching them to field labels or nearby_labels
- Match field labels/names semantically across languages — e.g. a field labeled \
"Name" should match data labeled "氏名", "Nom", or "नाम"

## Important Rules:
- Only fill fields where you have confidence >= 0.5
- Match date formats to field type (use YYYY-MM-DD for date fields)
- For checkboxes, return "true" or "false"
- Include the source name/identifier for each filled field
- Add warnings for ambiguous or uncertain matches

## Response Guidelines:
- confidence >= 0.9: Exact match found in data
- confidence 0.7-0.9: Strong match with minor inference
- confidence 0.5-0.7: Reasonable inference from context
- confidence < 0.5: Do not fill (add to unfilled_fields)
"""

AUTOFILL_USER_PROMPT_TEMPLATE = """## Target Form Fields

Here are the form fields that need to be filled:

{fields_json}

## Available Data Sources

Here is the extracted information from user-provided data sources:

{data_sources_text}

## Additional Rules

{rules_text}

## Task

Extract information from the data sources and fill in as many form fields as possible.
Match field labels/names semantically - e.g., "Full Name" should match data labeled \
"Name" or "Applicant Name".

Return your response as a valid JSON object with:
- filled_fields: Array of filled field objects (only fields you can fill)
- warnings: Array of warning messages (if any)

Do NOT include unfilled_fields — omit fields you cannot fill.
"""


REFILL_USER_PROMPT_TEMPLATE = """## Target Form Fields

{fields_json}

## Available Data Sources

{data_sources_text}

## User-Provided Answers (HIGH CONFIDENCE — use these first)

{answers_text}

## Additional Rules

{rules_text}

## Task

Fill ALL fields. Priority: user answers > data sources.
Match field labels/names semantically across languages.
Return filled_fields and warnings only.
Do NOT include unfilled_fields — omit fields you cannot fill.
"""


def build_refill_prompt(
    fields_json: str,
    data_sources_text: str,
    answers_text: str,
    rules: list[str] | None = None,
) -> str:
    """Build the user prompt for re-filling with user answers."""
    rules_text = "None specified."
    if rules:
        rules_text = "\n".join(f"- {rule}" for rule in rules)

    return REFILL_USER_PROMPT_TEMPLATE.format(
        fields_json=fields_json,
        data_sources_text=data_sources_text,
        answers_text=answers_text,
        rules_text=rules_text,
    )


def build_autofill_prompt(
    fields_json: str,
    data_sources_text: str,
    rules: list[str] | None = None,
) -> str:
    """Build the user prompt for autofill."""
    rules_text = "None specified."
    if rules:
        rules_text = "\n".join(f"- {rule}" for rule in rules)

    return AUTOFILL_USER_PROMPT_TEMPLATE.format(
        fields_json=fields_json,
        data_sources_text=data_sources_text,
        rules_text=rules_text,
    )


def _format_field_value(value: Any) -> str:
    """Format an extracted field value for the prompt."""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def format_data_sources(
    extractions: list[dict],
    max_raw_text_chars: int = 4000,
) -> str:
    """Format data source extractions for the prompt."""
    if not extractions:
        return "No data sources available."

    lines: list[str] = []
    for i, extraction in enumerate(extractions, 1):
        source_name = extraction.get("source_name", f"Source {i}")
        source_type = extraction.get("source_type", "unknown")
        fields = extraction.get("extracted_fields", {})
        raw_text = extraction.get("raw_text", "")

        lines.append(f"### {source_name} ({source_type})")

        if fields:
            lines.append("Extracted fields:")
            for key, value in fields.items():
                lines.append(f"  - {key}: {_format_field_value(value)}")

        if raw_text:
            preview = (
                raw_text[:max_raw_text_chars] + "..."
                if len(raw_text) > max_raw_text_chars
                else raw_text
            )
            lines.append(f"Raw text:\n{preview}")

        lines.append("")

    return "\n".join(lines)


# =============================================================================
# Field Identification Prompts (LLM-based strategy)
# =============================================================================

FIELD_IDENTIFICATION_SYSTEM_PROMPT = """You are a PDF form field identification assistant. \
Your task is to identify the semantic label for each form field based on its position \
relative to nearby text blocks on the PDF page.

You will receive:
1. A list of form fields (compact JSON)
2. A list of text blocks extracted from the PDF (compact JSON)

Field keys: id=field_id, l=label (only present when different from id), t=type, p=page, b=[x,y,w,h]
Text block keys: s=text, p=page, b=[x,y,w,h]

For each field, determine which text block is most likely its label by analyzing:
- Proximity: Labels are usually directly left of, above, or very close to their field
- Semantic relevance: The text should describe what the field expects (e.g., "Name", "Date of Birth")
- Page context: Only consider text on the same page as the field

Return a JSON object with this exact structure:
{
  "field_labels": [
    {
      "field_id": "Text1",
      "identified_label": "法人名",
      "confidence": 0.9,
      "reasoning": "Text '法人名' is 5pt left of the field on page 1"
    }
  ]
}

Rules:
- confidence >= 0.8: Text is clearly the label (directly adjacent)
- confidence 0.5-0.8: Likely the label (nearby, semantically relevant)
- confidence < 0.5: Do not include — omit the field from the response
- If no suitable label is found for a field, omit it from the response
"""


def build_field_identification_prompt(
    fields: tuple[FormFieldSpec, ...],
    text_blocks: list[dict[str, Any]],
    raw_bbox_map: dict[str, dict[str, Any]],
) -> str:
    """Build the user prompt for LLM-based field identification."""
    fields_data = []
    for field in fields:
        entry: dict[str, Any] = {"id": field.field_id}
        if field.label != field.field_id:
            entry["l"] = field.label
        entry["t"] = field.field_type
        entry["p"] = field.page
        bbox = raw_bbox_map.get(field.field_id)
        if bbox:
            entry["b"] = [
                int(bbox["x"]),
                int(bbox["y"]),
                int(bbox["width"]),
                int(bbox["height"]),
            ]
        fields_data.append(entry)

    blocks_data = []
    for block in text_blocks:
        text = block.get("text", "")
        if not text or not text.strip():
            continue
        block_entry: dict[str, Any] = {"s": text.strip()}
        block_entry["p"] = block.get("page")
        raw_bbox = block.get("bbox")
        if raw_bbox and len(raw_bbox) >= 4:
            block_entry["b"] = [
                int(raw_bbox[0]),
                int(raw_bbox[1]),
                int(raw_bbox[2]),
                int(raw_bbox[3]),
            ]
        blocks_data.append(block_entry)

    fields_json = json.dumps(fields_data, ensure_ascii=False, separators=(",", ":"))
    blocks_json = json.dumps(blocks_data, ensure_ascii=False, separators=(",", ":"))

    return (
        "## Form Fields\n\n"
        f"```json\n{fields_json}\n```\n\n"
        "## PDF Text Blocks\n\n"
        f"```json\n{blocks_json}\n```\n\n"
        "Identify the label for each form field based on proximity and context."
    )
