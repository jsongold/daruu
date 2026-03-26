"""Data models for prompt generation results and caching."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptGenerationResult:
    """Result of generating a form-specific system prompt."""

    specialized_prompt: str  # Built from mapping
    field_mapping: dict[str, str]  # field_id -> label (from LLM)
    form_title: str | None
    sections: list[dict] | None
    format_rules: dict[str, str] | None
    fill_rules: list[str] | None
    key_field_mappings: tuple[dict, ...] | None  # source_key -> field_id with bbox
    generation_time_ms: int
    model_used: str
    validation_passed: bool  # All field_ids present in field_labels?
    missing_field_ids: tuple[str, ...]  # field_ids missing from validation


@dataclass(frozen=True)
class PromptCacheEntry:
    """Cached prompt for a specific form structure."""

    form_hash: str
    specialized_prompt: str
    field_count: int
    created_at: str  # ISO 8601
    form_title: str | None
