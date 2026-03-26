"""Prompt builder — constructs system prompts from structured field mappings.

Takes the JSON mapping produced by the LLM meta-prompt and builds a
deterministic system prompt that combines form-specific context with
the base fill instructions from AUTOFILL_SYSTEM_PROMPT.
"""


def build_specialized_prompt(mapping: dict) -> str:
    """Build a system prompt from a structured field mapping.

    Combines the LLM-generated mapping with AUTOFILL_SYSTEM_PROMPT
    fill instructions for a complete, deterministic system prompt.

    Args:
        mapping: Structured JSON mapping from the LLM containing:
            - form_title: Form title/name
            - form_language: Language code (e.g., "ja")
            - field_labels: dict of field_id -> label
            - sections: list of section dicts with name and field_ids
            - format_rules: dict of field_id -> format spec
            - fill_rules: list of conditional fill rules

    Returns:
        Complete system prompt string.
    """
    lines: list[str] = []

    # Form identification
    form_title = mapping.get("form_title", "Unknown Form")
    form_language = mapping.get("form_language", "")
    lines.append(f"# Form: {form_title}")
    if form_language:
        lines.append(f"Language: {form_language}")
    lines.append("")

    # Field mapping table
    field_labels = mapping.get("field_labels", {})
    if field_labels:
        lines.append("## Field Mapping")
        lines.append("")
        for field_id, label in field_labels.items():
            lines.append(f"- {field_id}: {label}")
        lines.append("")

    # Key-field mappings (coordinate-based)
    key_field_mappings = mapping.get("key_field_mappings", [])
    if key_field_mappings:
        lines.append("## Data Source Key → Field Mappings")
        lines.append("")
        lines.append(
            "Use these mappings to connect data source values to form fields. "
            "Priority: these mappings > fuzzy label matching."
        )
        lines.append("")
        for m in key_field_mappings:
            source_key = m.get("source_key", "?")
            field_id = m.get("field_id")
            reasoning = m.get("reasoning", "")
            bbox = m.get("bbox", {})
            if field_id:
                label = field_labels.get(field_id, field_id)
                bbox_str = ""
                if bbox:
                    page = bbox.get("page", "?")
                    x = bbox.get("x", "?")
                    y = bbox.get("y", "?")
                    bbox_str = f" (page {page}, x={x}, y={y})"
                lines.append(
                    f"- \"{source_key}\" → {field_id}: {label}{bbox_str}"
                )
                if reasoning:
                    lines.append(f"  Reason: {reasoning}")
            else:
                lines.append(f"- \"{source_key}\" → (no matching field)")
                if reasoning:
                    lines.append(f"  Reason: {reasoning}")
        lines.append("")

    # Section structure
    sections = mapping.get("sections", [])
    if sections:
        lines.append("## Sections")
        lines.append("")
        for section in sections:
            name = section.get("name", "Unknown")
            field_ids = section.get("field_ids", [])
            lines.append(f"### {name}")
            for fid in field_ids:
                label = field_labels.get(fid, fid)
                lines.append(f"  - {fid}: {label}")
            lines.append("")

    # Format rules
    format_rules = mapping.get("format_rules", {})
    if format_rules:
        lines.append("## Format Rules")
        lines.append("")
        for field_id, rule in format_rules.items():
            label = field_labels.get(field_id, field_id)
            lines.append(f"- {field_id} ({label}): {rule}")
        lines.append("")

    # Fill rules
    fill_rules = mapping.get("fill_rules", [])
    if fill_rules:
        lines.append("## Fill Rules")
        lines.append("")
        for rule in fill_rules:
            lines.append(f"- {rule}")
        lines.append("")

    return "\n".join(lines)
