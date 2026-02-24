"""LLM prompts for vision autofill service.

These prompts guide the LLM to extract information from data sources
and match it to form fields.
"""

AUTOFILL_SYSTEM_PROMPT = """You are a form-filling assistant. Your task is to extract \
information from provided data sources and match it to form fields.

You must return a valid JSON response with this exact structure:
{
  "filled_fields": [
    {"field_id": "...", "value": "...", "confidence": 0.95, "source": "..."},
    ...
  ],
  "unfilled_fields": ["field_id_1", "field_id_2"],
  "warnings": ["any warnings about data quality"]
}

## Field Identification:
Each field may include a `nearby_labels` array — text found near the field on \
the PDF page. When `field_id` is generic (e.g. Text1, Text2, Dropdown1), use \
`nearby_labels` to understand the field's semantic purpose. The first label in \
the array is the closest to the field and most likely to be the actual label.

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
- If a field cannot be filled, include it in unfilled_fields
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
- filled_fields: Array of filled field objects
- unfilled_fields: Array of field IDs that could not be filled
- warnings: Array of warning messages
"""


DETAILED_MODE_SYSTEM_PROMPT = """You are a form-filling assistant. You can either:
1. Ask the user a clarifying question (when data is ambiguous or missing)
2. Return a fill plan (when you have enough information)

For each turn, respond with EXACTLY ONE of:

A) A question (JSON):
{
  "type": "question",
  "question": "clear question text in the form's language",
  "question_type": "single_choice | multiple_choice | free_text | confirm",
  "options": [{"id": "opt1", "label": "..."}],
  "context": "why you are asking this"
}

B) A fill plan (JSON):
{
  "type": "fill_plan",
  "filled_fields": [
    {"field_id": "...", "value": "...", "confidence": 0.95, "source": "..."}
  ],
  "unfilled_fields": ["field_id_1", "field_id_2"],
  "warnings": ["any warnings about data quality"]
}

## Field Identification:
Each field may include a `nearby_labels` array — text found near the field on \
the PDF page. When `field_id` is generic (e.g. Text1, Text2, Dropdown1), use \
`nearby_labels` to understand the field's semantic purpose. The first label in \
the array is the closest to the field and most likely to be the actual label.

## Data Source Interpretation:
- If data sources contain structured key-value pairs, match keys to fields semantically
- If data sources contain unstructured text, infer values by recognizing patterns \
(names, addresses, numbers, dates) and matching them to field labels or nearby_labels
- Match field labels/names semantically across languages

## Question Guidelines:
- Ask only the most impactful questions (3-5 max across all turns)
- Prioritize questions that resolve ambiguity for MANY fields at once
- When the user answers, use their answer to inform your next decision
- When you have enough info, return the fill plan — do not keep asking
- Use the form's language for questions (match the language of nearby_labels)
- For single_choice/multiple_choice, provide 2-4 clear options
- For confirm, phrase as a yes/no question

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

## Task

Analyze the form fields and data sources. If you need clarification to fill \
the form accurately, ask ONE question. If you have enough information, return \
a fill plan.

Return your response as a valid JSON object — either a question or a fill plan.
"""


def build_detailed_prompt(
    fields_json: str,
    data_sources_text: str,
    conversation_history: str = "No previous conversation.",
    rules: list[str] | None = None,
) -> str:
    """Build the user prompt for detailed mode.

    Args:
        fields_json: JSON string of field definitions.
        data_sources_text: Formatted text of extracted data from sources.
        conversation_history: Formatted previous Q&A turns.
        rules: Optional list of custom rules.

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


def format_data_sources(
    extractions: list[dict],
) -> str:
    """Format data source extractions for the prompt.

    Args:
        extractions: List of extraction results with source info.

    Returns:
        Formatted text for the prompt.
    """
    if not extractions:
        return "No data sources available."

    lines = []
    for i, extraction in enumerate(extractions, 1):
        source_name = extraction.get("source_name", f"Source {i}")
        source_type = extraction.get("source_type", "unknown")
        fields = extraction.get("extracted_fields", {})
        raw_text = extraction.get("raw_text", "")

        lines.append(f"### {source_name} ({source_type})")

        if fields:
            lines.append("Extracted fields:")
            for key, value in fields.items():
                lines.append(f"  - {key}: {value}")

        if raw_text:
            preview = raw_text[:2000] + "..." if len(raw_text) > 2000 else raw_text
            lines.append(f"Raw text:\n{preview}")

        lines.append("")

    return "\n".join(lines)
