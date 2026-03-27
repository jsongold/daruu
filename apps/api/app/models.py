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
    model_config = {"frozen": True}


class TextBlock(BaseModel):
    id: str
    text: str
    bbox: BBox
    page: int
    model_config = {"frozen": True}


class Form(BaseModel):
    id: str
    document_id: str
    fields: list[FormField] = Field(default_factory=list)
    page_count: int = 1
    model_config = {"frozen": True}


class Annotation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    document_id: str
    label_text: str
    label_bbox: BBox
    label_page: int = 1
    field_id: str
    field_name: str
    field_bbox: BBox | None = None
    field_page: int = 1
    created_at: datetime | None = None
    model_config = {"frozen": True}


class Mapping(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
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


class ContextWindow(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    document_id: str | None = None
    form: Form | None = None
    user_info: UserInfo = Field(default_factory=UserInfo)
    annotations: list[Annotation] = Field(default_factory=list)
    mappings: list[Mapping] = Field(default_factory=list)
    mode: Mode = Mode.PREVIEW
    history: list[HistoryMessage] = Field(default_factory=list)
    rules: Rules = Field(default_factory=Rules)
    rulebook_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = {"frozen": True}


# --- Request / Response DTOs ---

class UploadDocumentResponse(BaseModel):
    document_id: str
    form: Form


class PagePreviewResponse(BaseModel):
    document_id: str
    page: int
    image_url: str


class FieldsResponse(BaseModel):
    document_id: str
    fields: list[FormField]
    text_blocks: list[TextBlock]
    page_count: int = 1


class CreateSessionRequest(BaseModel):
    document_id: str
    user_info: UserInfo = Field(default_factory=UserInfo)
    rules: Rules = Field(default_factory=Rules)


class CreateAnnotationRequest(BaseModel):
    document_id: str
    label_text: str
    label_bbox: BBox
    label_page: int = 1
    field_id: str
    field_name: str
    field_bbox: BBox | None = None
    field_page: int = 1


class FieldLabelMap(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    document_id: str
    field_id: str
    field_name: str
    label_text: str | None = None
    semantic_key: str | None = None
    confidence: int = 0
    source: str = "auto"
    created_at: datetime | None = None
    model_config = {"frozen": True}


class MapResult(BaseModel):
    document_id: str
    maps: list[FieldLabelMap]


class RunMappingRequest(BaseModel):
    session_id: str


class FillRequest(BaseModel):
    session_id: str
    user_message: str | None = None  # for Ask mode responses


class FillEvent(BaseModel):
    event: str  # "mode_change" | "field_filled" | "ask" | "done" | "error"
    data: dict[str, Any]
