"""Domain models for the simple form annotation and fill app."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Mode(str, Enum):
    PREVIEW = "preview"
    EDIT = "edit"
    ANNOTATE = "annotate"
    MAP = "map"
    FILL = "fill"
    ASK = "ask"
    RULES = "rules"


class FieldType(str, Enum):
    TEXT = "text"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SELECT = "select"
    DATE = "date"
    SIGNATURE = "signature"
    NAME = "name"
    ADDRESS = "address"
    UNKNOWN = "unknown"


class BBox(BaseModel):
    x: float
    y: float
    width: float
    height: float
    model_config = {"frozen": True}


class FormField(BaseModel):
    id: str
    name: str
    field_type: FieldType = FieldType.TEXT
    bbox: BBox | None = None
    page: int = 1
    value: str | None = None
    options: list[str] = Field(default_factory=list)
    model_config = {"frozen": True}


class TextBlock(BaseModel):
    id: str
    text: str
    bbox: BBox
    page: int
    model_config = {"frozen": True}


class Segment(BaseModel):
    id: str
    title: str | None = None
    bbox: BBox
    page: int
    field_ids: list[str] = Field(default_factory=list)
    text_block_ids: list[str] = Field(default_factory=list)
    model_config = {"frozen": True}


class SegmentationResponse(BaseModel):
    form_id: str
    method: str
    segments: list[Segment]


class Form(BaseModel):
    id: str
    form_id: str
    fields: list[FormField] = Field(default_factory=list)
    page_count: int = 1
    model_config = {"frozen": True}


class Annotation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    form_id: str
    label_text: str
    label_bbox: BBox
    label_page: int = 1
    field_id: str
    field_name: str
    field_bbox: BBox | None = None
    field_page: int = 1
    created_at: datetime | None = None
    model_config = {"frozen": True}


class AnnotationOperation(str, Enum):
    ADDED = "added"
    REMOVED = "removed"


class AnnotationEntry(BaseModel):
    """One row in the form_annotation_pairs changelog table."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    form_id: str
    pair_id: str
    operation: AnnotationOperation
    role: str  # 'label'|'field'
    value: str
    bbox: BBox | None = None
    page: int = 1
    field_id: str | None = None
    created_at: datetime | None = None
    model_config = {"frozen": True}


class Mapping(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    annotation_id: str
    field_id: str
    inferred_value: str | None = None
    confidence: float = 0.0
    reason: str = ""
    created_at: datetime | None = None
    model_config = {"frozen": True}


class UserInfo(BaseModel):
    data: dict[str, str] = Field(default_factory=dict)
    model_config = {"frozen": True}


class Prompt(BaseModel):
    system: str
    user: str
    model_config = {"frozen": True}


class RuleType(str, Enum):
    CONDITIONAL = "conditional"
    FORMAT = "format"
    CALCULATION = "calculation"


class RuleItem(BaseModel):
    type: RuleType
    rule_text: str
    field_ids: list[str] = Field(default_factory=list)
    question: str | None = None
    options: list[str] = Field(default_factory=list)
    model_config = {"frozen": True}


class Rules(BaseModel):
    items: list[RuleItem] = Field(default_factory=list)
    model_config = {"frozen": True}


class HistoryMessage(BaseModel):
    role: str  # "user" | "agent"
    content: str
    model_config = {"frozen": True}


class Message(BaseModel):
    id: str
    conversation_id: str
    role: str  # "user" | "agent" | "system"
    content: str
    created_at: datetime | None = None
    model_config = {"frozen": True}


class PromptLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    conversation_id: str
    message_id: str | None = None
    type: str  # "map" | "understand" | "fill" | "mapping_fallback"
    prompt_template: str  # class name: "MapPrompt" | "RulesPrompt" | "FillPrompt" | "inline"
    model: str
    system_chars: int = 0
    user_chars: int = 0
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime | None = None
    model_config = {"frozen": True}


class PromptRaw(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    prompt_log_id: str
    system_prompt: str = ""
    user_prompt: str = ""
    created_at: datetime | None = None
    model_config = {"frozen": True}


class ContextWindow(BaseModel):
    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    form_id: str | None = None
    form: Form | None = None
    user_info: UserInfo = Field(default_factory=UserInfo)
    annotations: list[Annotation] = Field(default_factory=list)
    mappings: list[Mapping] = Field(default_factory=list)
    mode: Mode = Mode.PREVIEW
    history: list[HistoryMessage] = Field(default_factory=list)
    rules: Rules = Field(default_factory=Rules)
    form_values: dict[str, str] = Field(default_factory=dict)
    ask_answers: dict[str, str] = Field(default_factory=dict)
    rulebook_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = {"frozen": True}


# --- Request / Response DTOs ---

class UploadFormResponse(BaseModel):
    form_id: str
    form: Form


class PagePreviewResponse(BaseModel):
    form_id: str
    page: int
    image_url: str


class FieldsResponse(BaseModel):
    form_id: str
    fields: list[FormField]
    text_blocks: list[TextBlock]
    page_count: int = 1


class CreateConversationRequest(BaseModel):
    form_id: str | None = None
    user_info: UserInfo = Field(default_factory=UserInfo)
    rules: Rules = Field(default_factory=Rules)


class CreateAnnotationRequest(BaseModel):
    form_id: str
    label_text: str
    label_bbox: BBox
    label_page: int = 1
    field_id: str
    field_name: str
    field_bbox: BBox | None = None
    field_page: int = 1


class FieldLabelMap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    form_id: str
    field_id: str
    field_name: str
    label_text: str | None = None
    semantic_key: str | None = None
    confidence: int = 0
    source: str = "auto"
    inferred_field_type: str | None = None
    created_at: datetime | None = None
    model_config = {"frozen": True}


class MapRun(BaseModel):
    created_at: datetime
    field_count: int
    identified_count: int
    model_config = {"frozen": True}


class EnrichedField(BaseModel):
    field_id: str
    name: str
    type: str
    label: str | None = None
    semantic_key: str | None = None
    confidence: int = 0
    confirmed: bool = False
    current_value: str | None = None
    inferred_value: str | None = None
    nearby_text: list[str] = Field(default_factory=list)
    model_config = {"frozen": True}


class FieldSection(BaseModel):
    section_hint: str | None = None
    fields: list[EnrichedField] = Field(default_factory=list)
    model_config = {"frozen": True}


class PageContext(BaseModel):
    page: int
    sections: list[FieldSection] = Field(default_factory=list)
    model_config = {"frozen": True}


class AlreadyFilledField(BaseModel):
    field_id: str
    label: str | None = None
    value: str
    model_config = {"frozen": True}


class FillField(BaseModel):
    """A field that has been approved for filling (rules already resolved)."""
    field_id: str
    label: str | None = None
    semantic_key: str | None = None
    type: str = "text"
    options: list[str] = Field(default_factory=list)
    segment_title: str | None = None
    model_config = {"frozen": True}


class FillContext(BaseModel):
    fields: list[FillField] = Field(default_factory=list)
    user_info: dict[str, str] = Field(default_factory=dict)
    general_rules: list[RuleItem] = Field(default_factory=list)
    form_rules: list[RuleItem] = Field(default_factory=list)
    ask_answers: dict[str, str] = Field(default_factory=dict)
    model_config = {"frozen": True}


class MapContext(BaseModel):
    fields: list[FormField] = Field(default_factory=list)
    text_blocks: list[TextBlock] = Field(default_factory=list)
    confirmed_annotations: list[Annotation] = Field(default_factory=list)
    heuristic_maps: list[FieldLabelMap] = Field(default_factory=list)
    segments: list[Segment] = Field(default_factory=list)
    top_k: int = 7
    model_config = {"frozen": True}


class RulesContext(BaseModel):
    fields: list[FormField] = Field(default_factory=list)
    text_blocks: list[TextBlock] = Field(default_factory=list)
    general_rules: list[RuleItem] = Field(default_factory=list)
    model_config = {"frozen": True}


class AskContext(BaseModel):
    rules: list[RuleItem] = Field(default_factory=list)
    model_config = {"frozen": True}


class FormSchemaField(BaseModel):
    """One field entry in the form_schema JSONB array."""
    field_id: str
    field_name: str
    field_type: str = "text"
    bbox: BBox | None = None
    page: int = 1
    default_value: str | None = None
    label_text: str | None = None
    label_source: str | None = None  # 'annotation' | 'map_auto' | 'map_manual' | 'pdf_extract'
    label_bbox: BBox | None = None
    label_page: int | None = None
    semantic_key: str | None = None
    confidence: int = 0
    is_confirmed: bool = False
    options: list[str] = Field(default_factory=list)
    segment_id: str | None = None
    segment_title: str | None = None
    model_config = {"frozen": True}


class GeneralRules(BaseModel):
    """Reusable rules scoped by country and/or category."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    country: str = "GLOBAL"
    category: str = "GLOBAL"
    rules: list[RuleItem] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = {"frozen": True}


class FormRules(BaseModel):
    """Global form rules (one row per form)."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    form_id: str
    description: str | None = None
    rulebook_text: str | None = None
    rules: list[RuleItem] = Field(default_factory=list)
    message_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = {"frozen": True}


class FormSchema(BaseModel):
    """Top-level form schema: form_name + field array + FK to form_rules."""
    form_id: str
    form_name: str | None = None
    form_rules_id: str | None = None
    fields: list[FormSchemaField] = Field(default_factory=list)
    model_config = {"frozen": True}


class FormSchemaRow(BaseModel):
    """DB row model for form_schema table."""
    id: str
    form_id: str
    form_name: str | None = None
    form_rules_id: str | None = None
    fields: list[FormSchemaField] = Field(default_factory=list, alias="schema")
    embedding: list[float] | None = None
    message_id: str | None = None
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = {"frozen": True, "populate_by_name": True}


class MapResult(BaseModel):
    form_id: str
    maps: list[FieldLabelMap]


class RunMappingRequest(BaseModel):
    conversation_id: str


class FillRequest(BaseModel):
    conversation_id: str
    ask_answers: dict[str, str] | None = None  # resolved question -> answer pairs


class FillEvent(BaseModel):
    event: str  # "mode_change" | "field_filled" | "ask" | "done" | "error"
    data: dict[str, Any]
