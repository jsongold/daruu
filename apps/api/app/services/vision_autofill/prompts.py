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


DETAILED_MODE_SYSTEM_PROMPT = """You are a form-filling assistant. You can either:
1. Ask the user clarifying questions (when data is ambiguous or missing)
2. Return a fill plan (when you are confident about ALL fields)

For each turn, respond with EXACTLY ONE of:

A) Questions (JSON) — ask ALL questions you need at once:
{
  "type": "questions",
  "questions": [
    {
      "id": "q1",
      "question": "clear question text in the form's language",
      "question_type": "single_choice | multiple_choice | free_text | confirm",
      "options": [{"id": "opt1", "label": "..."}],
      "context": "why you are asking this"
    }
  ]
}

Example with mixed question types (preferred — use the right type for each question):
{
  "type": "questions",
  "questions": [
    {
      "id": "q1",
      "question": "What is your gender?",
      "question_type": "single_choice",
      "options": [{"id": "male", "label": "Male"}, {"id": "female", "label": "Female"}, {"id": "other", "label": "Other"}],
      "context": "Required for the applicant information section"
    },
    {
      "id": "q2",
      "question": "Your name appears to be John Smith. Is this correct?",
      "question_type": "confirm",
      "options": [],
      "context": "Inferred from the uploaded document"
    },
    {
      "id": "q3",
      "question": "What is your current address?",
      "question_type": "free_text",
      "options": [],
      "context": "No address found in the uploaded documents"
    }
  ]
}

B) A fill plan (JSON):
{
  "type": "fill_plan",
  "filled_fields": [
    {"field_id": "...", "value": "...", "confidence": 0.95, "source": "..."}
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
- Match field labels/names semantically across languages

## Question Strategy (IMPORTANT):
- Default to ASKING questions. Only return a fill plan when you are genuinely \
confident (>= 0.8) about the values for most fields.
- Ask ALL questions you need at once in a single batch. Do NOT ask one question \
at a time — gather everything you need in one round.
- Typical forms need 3-5 questions. Ask about different categories of information \
(e.g., personal info, dates, addresses, selections) all at once.
- Prioritize questions that resolve ambiguity for MANY fields at once.
- NEVER repeat a question that appears in the conversation history. Read the \
history carefully — if a question was already asked and answered, use that answer.
- When the user answers, integrate their answers and decide: do you still have \
gaps or low confidence for remaining fields? If yes, ask another batch of NEW questions.
- Only return a fill plan when:
  (a) You are confident (>= 0.8) about most field values, OR
  (b) Further questions would not meaningfully improve accuracy, OR
  (c) You have already asked 5+ questions total — STOP asking and fill now
- Use the form's language for questions (match the language of nearby_labels).
- Give each question a unique id (q1, q2, q3, ...).
- After 2 rounds of questions, return a fill plan even if some fields have low confidence.

## Question Type Selection (CRITICAL — DO NOT default to free_text):
- single_choice: When the answer is ONE of a known set of options.
  Examples: gender, marital status, document type, yes/no with labeled options.
  ALWAYS provide 2-4 options with id and label.
- multiple_choice: When the user may select MORE THAN ONE option.
  Examples: applicable categories, languages spoken, services requested.
  ALWAYS provide 2-6 options with id and label.
- confirm: When verifying a specific value you already inferred from data sources.
  Example: "Your date of birth appears to be 1990-01-15. Is this correct?"
  Options default to Yes/No. If the user says No, they can type the correction.
- free_text: ONLY when the answer is truly open-ended with no predictable options.
  Examples: full name, address, phone number, reason/notes.

Rule: If you can enumerate the possible answers, use single_choice or multiple_choice.
      If you have a candidate value to verify, use confirm.
      Use free_text only as a last resort.

## Fill Plan Rules (same as quick mode):
- Only fill fields where you have confidence >= 0.5
- Match date formats to field type (use YYYY-MM-DD for date fields)
- For checkboxes, return "true" or "false"
- Include the source name/identifier for each filled field
"""

DETAILED_MODE_USER_PROMPT_TEMPLATE = """## Target Form Fields

{fields_json}

## Available Data Sources

{data_sources_text}

## Additional Rules

{rules_text}

## Conversation History

{conversation_history}

## Turn Info

Questions asked so far: {questions_asked}

## Task

Analyze the form fields and data sources carefully. Consider what information \
is still missing or ambiguous.

- If there are fields you cannot confidently fill (confidence < 0.8), ask ALL \
clarifying questions you need at once in a single batch. Cover different \
categories (personal info, dates, addresses, selections) together.
- NEVER repeat questions from the conversation history — check what was already asked.
- Only return a fill plan if you are confident about most field values, or if \
you have already asked enough questions (5+).
- When returning a fill plan, only include filled_fields. Do NOT include unfilled_fields.

Return your response as a valid JSON object — either questions or a fill plan.
"""


REASONING_SYSTEM_PROMPT = """You are a routing assistant for a form-filling system.
Decide: "ask" (information missing) or "fill" (enough info available).

Rules:
- If questions_asked >= 3 and data covers most fields, choose "fill".
- If the user already answered questions covering key missing info, choose "fill".
- Only choose "ask" when critical information is genuinely missing and cannot be \
inferred from the available data sources.
- When in doubt, prefer "fill" — the system can always ask more later.
"""

REASONING_USER_PROMPT_TEMPLATE = """Fields to fill: {total_fields}
Data source keys available: {data_source_keys}
Questions asked so far: {questions_asked}

Conversation summary:
{conversation_summary}

Should I ask more questions or fill the form now?"""


def build_reasoning_prompt(
    total_fields: int,
    data_source_keys: list[str],
    questions_asked: int,
    conversation_summary: str,
) -> str:
    """Build the user prompt for the reasoning pre-check.

    Args:
        total_fields: Total number of form fields to fill.
        data_source_keys: Keys available from data sources.
        questions_asked: Number of Q&A rounds completed.
        conversation_summary: Compact "Asked: ... / Answered: ..." lines.

    Returns:
        Formatted prompt string (~300-500 tokens).
    """
    return REASONING_USER_PROMPT_TEMPLATE.format(
        total_fields=total_fields,
        data_source_keys=", ".join(data_source_keys),
        questions_asked=questions_asked,
        conversation_summary=conversation_summary or "No conversation yet.",
    )


def build_detailed_prompt(
    fields_json: str,
    data_sources_text: str,
    conversation_history: str = "No previous conversation.",
    rules: list[str] | None = None,
    questions_asked: int = 0,
) -> str:
    """Build the user prompt for detailed mode.

    Args:
        fields_json: JSON string of field definitions.
        data_sources_text: Formatted text of extracted data from sources.
        conversation_history: Formatted previous Q&A turns.
        rules: Optional list of custom rules.
        questions_asked: Number of questions already asked in this session.

    Returns:
        Formatted prompt string.
    """
    rules_text = "None specified."
    if rules:
        rules_text = "\n".join(f"- {rule}" for rule in rules)

    return DETAILED_MODE_USER_PROMPT_TEMPLATE.format(
        fields_json=fields_json,
        data_sources_text=data_sources_text,
        rules_text=rules_text,
        conversation_history=conversation_history,
        questions_asked=questions_asked,
    )


def build_autofill_prompt(
    fields_json: str,
    data_sources_text: str,
    rules: list[str] | None = None,
) -> str:
    """Build the user prompt for autofill.

    Args:
        fields_json: JSON string of field definitions.
        data_sources_text: Formatted text of extracted data from sources.
        rules: Optional list of custom rules.

    Returns:
        Formatted prompt string.
    """
    rules_text = "None specified."
    if rules:
        rules_text = "\n".join(f"- {rule}" for rule in rules)

    return AUTOFILL_USER_PROMPT_TEMPLATE.format(
        fields_json=fields_json,
        data_sources_text=data_sources_text,
        rules_text=rules_text,
    )


def _format_field_value(value: Any) -> str:
    """Format an extracted field value for the prompt.

    Strings are returned as-is. Dicts and lists are serialized as compact JSON.
    Other types are converted via str().
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def format_data_sources(
    extractions: list[dict],
    max_raw_text_chars: int = 4000,
) -> str:
    """Format data source extractions for the prompt.

    Args:
        extractions: List of extraction results with source info.
        max_raw_text_chars: Maximum characters for raw text truncation.

    Returns:
        Formatted text for the prompt.
    """
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
    """Build the user prompt for LLM-based field identification.

    Uses compact JSON with abbreviated keys to minimize token usage:
    - Field: id, l (label, only when != id), t (type), p (page), b ([x,y,w,h])
    - Block: s (text), p (page), b ([x,y,w,h])

    Args:
        fields: Form field specifications.
        text_blocks: Text blocks from PDF extraction.
        raw_bbox_map: Raw AcroForm bounding boxes keyed by field name.

    Returns:
        Formatted prompt string with compact JSON.
    """
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
