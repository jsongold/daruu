"""Conversation models for Agent Chat UI.

Based on PRD: docs/prd/agent-chat-ui.md
These models define the API contracts for the conversation system.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConversationStatus(str, Enum):
    """Status of a conversation."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    ERROR = "error"


class MessageRole(str, Enum):
    """Role of a message sender."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class AgentStage(str, Enum):
    """Current stage of agent processing."""

    IDLE = "idle"
    ANALYZING = "analyzing"
    CONFIRMING = "confirming"
    MAPPING = "mapping"
    FILLING = "filling"
    REVIEWING = "reviewing"
    COMPLETE = "complete"
    ERROR = "error"


# ============================================
# Request Models
# ============================================


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""

    title: str | None = Field(None, description="Optional title (auto-generated if not provided)")

    model_config = {"frozen": True}


class SendMessageRequest(BaseModel):
    """Request to send a message (text only, files via multipart)."""

    content: str = Field(..., min_length=1, max_length=10000, description="Message text content")

    model_config = {"frozen": True}


class ApprovePreviewRequest(BaseModel):
    """Request to approve a preview."""

    message_id: str = Field(..., description="ID of the approval message to approve")

    model_config = {"frozen": True}


# ============================================
# Response Models
# ============================================


class Attachment(BaseModel):
    """An attachment on a message."""

    id: str = Field(..., description="Unique attachment ID")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    ref: str = Field(..., description="Storage reference URL")
    document_id: str | None = Field(None, description="Linked document ID if processed")

    model_config = {"frozen": True}


class Message(BaseModel):
    """A message in a conversation."""

    id: str = Field(..., description="Unique message ID")
    role: MessageRole = Field(..., description="Message sender role")
    content: str = Field(..., description="Message text content")
    thinking: str | None = Field(None, description="Agent's internal reasoning")
    preview_ref: str | None = Field(None, description="Preview image URL")
    approval_required: bool = Field(default=False, description="Whether approval is needed")
    approval_status: ApprovalStatus | None = Field(
        None, description="Approval status if applicable"
    )
    attachments: list[Attachment] = Field(default_factory=list, description="Message attachments")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"frozen": True}


class Conversation(BaseModel):
    """A conversation with agent."""

    id: str = Field(..., description="Unique conversation ID")
    status: ConversationStatus = Field(..., description="Current status")
    title: str | None = Field(None, description="Conversation title")
    form_document_id: str | None = Field(None, description="Form document ID")
    source_document_ids: list[str] = Field(default_factory=list, description="Source document IDs")
    filled_pdf_ref: str | None = Field(None, description="Filled PDF storage reference")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"frozen": True}


class ConversationSummary(BaseModel):
    """Summary of a conversation for list views."""

    id: str = Field(..., description="Unique conversation ID")
    status: ConversationStatus = Field(..., description="Current status")
    title: str | None = Field(None, description="Conversation title")
    last_message_preview: str | None = Field(None, description="Preview of last message")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"frozen": True}


class ConversationWithMessages(BaseModel):
    """Conversation with recent messages."""

    conversation: Conversation = Field(..., description="Conversation details")
    messages: list[Message] = Field(default_factory=list, description="Recent messages")

    model_config = {"frozen": True}


class ConversationListResponse(BaseModel):
    """Paginated list of conversations."""

    items: list[ConversationSummary] = Field(..., description="Conversation summaries")
    next_cursor: str | None = Field(None, description="Cursor for next page")

    model_config = {"frozen": True}


class MessageListResponse(BaseModel):
    """Paginated list of messages."""

    items: list[Message] = Field(..., description="Messages")
    has_more: bool = Field(..., description="Whether more messages exist")

    model_config = {"frozen": True}


# ============================================
# SSE Event Models
# ============================================


class SSEEventType(str, Enum):
    """Types of SSE events."""

    CONNECTED = "connected"
    THINKING = "thinking"
    MESSAGE = "message"
    PREVIEW = "preview"
    APPROVAL = "approval"
    STAGE_CHANGE = "stage_change"
    ERROR = "error"
    COMPLETE = "complete"


class SSEConnectedData(BaseModel):
    """Data for 'connected' event."""

    conversation_id: str = Field(..., description="Connected conversation ID")

    model_config = {"frozen": True}


class SSEThinkingData(BaseModel):
    """Data for 'thinking' event."""

    stage: AgentStage = Field(..., description="Current agent stage")
    message: str = Field(..., description="Status message")

    model_config = {"frozen": True}


class SSEMessageData(BaseModel):
    """Data for 'message' event."""

    id: str = Field(..., description="Message ID")
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")

    model_config = {"frozen": True}


class SSEPreviewData(BaseModel):
    """Data for 'preview' event."""

    message_id: str = Field(..., description="Related message ID")
    preview_ref: str = Field(..., description="Preview image URL")

    model_config = {"frozen": True}


class SSEApprovalData(BaseModel):
    """Data for 'approval' event."""

    message_id: str = Field(..., description="Approval message ID")
    fields_to_approve: list[str] = Field(
        default_factory=list, description="Field IDs needing approval"
    )

    model_config = {"frozen": True}


class SSEStageChangeData(BaseModel):
    """Data for 'stage_change' event."""

    previous_stage: AgentStage = Field(..., description="Previous stage")
    new_stage: AgentStage = Field(..., description="New stage")

    model_config = {"frozen": True}


class SSEErrorData(BaseModel):
    """Data for 'error' event."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")

    model_config = {"frozen": True}


# ============================================
# Error Models
# ============================================


class ErrorCode(str, Enum):
    """Standard error codes."""

    # Client errors (4xx)
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    TOO_MANY_FILES = "TOO_MANY_FILES"
    CONVERSATION_NOT_FOUND = "CONVERSATION_NOT_FOUND"
    CONVERSATION_COMPLETED = "CONVERSATION_COMPLETED"
    RATE_LIMITED = "RATE_LIMITED"

    # Agent errors (5xx)
    AGENT_TIMEOUT = "AGENT_TIMEOUT"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    FILL_FAILED = "FILL_FAILED"
    LLM_ERROR = "LLM_ERROR"


ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.INVALID_FILE_TYPE: "Only PDF and image files are supported",
    ErrorCode.FILE_TOO_LARGE: "File exceeds 50MB limit",
    ErrorCode.TOO_MANY_FILES: "Maximum 5 files per message",
    ErrorCode.CONVERSATION_NOT_FOUND: "Conversation not found",
    ErrorCode.CONVERSATION_COMPLETED: "Cannot modify completed conversation",
    ErrorCode.RATE_LIMITED: "Too many requests, please slow down",
    ErrorCode.AGENT_TIMEOUT: "Agent took too long to respond",
    ErrorCode.EXTRACTION_FAILED: "Could not extract data from document",
    ErrorCode.FILL_FAILED: "Could not fill the form",
    ErrorCode.LLM_ERROR: "AI service temporarily unavailable",
}


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: ErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable message")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
    retry_after: int | None = Field(None, ge=0, description="Seconds before retry")

    model_config = {"frozen": True}


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail = Field(..., description="Error details")

    model_config = {"frozen": True}


# ============================================
# Agent State Models
# ============================================


class DetectedDocument(BaseModel):
    """A document detected by the agent."""

    document_id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    document_type: str = Field(..., description="Detected type: form, source")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    page_count: int = Field(..., ge=1, description="Number of pages")
    preview_ref: str | None = Field(None, description="Preview image URL")

    model_config = {"frozen": True}


class AgentState(BaseModel):
    """Current state of agent for a conversation.

    Cached in Redis, persisted to DB.
    """

    conversation_id: str = Field(..., description="Conversation ID")
    current_stage: AgentStage = Field(
        default=AgentStage.IDLE, description="Current processing stage"
    )
    detected_documents: list[DetectedDocument] = Field(
        default_factory=list, description="Documents detected"
    )
    form_fields: list[dict[str, Any]] = Field(
        default_factory=list, description="Detected form fields"
    )
    extracted_values: list[dict[str, Any]] = Field(
        default_factory=list, description="Extracted field values"
    )
    pending_questions: list[dict[str, Any]] = Field(
        default_factory=list, description="Questions for user"
    )
    last_error: str | None = Field(None, description="Last error message")
    retry_count: int = Field(default=0, ge=0, description="Retry attempt count")
    last_activity: datetime = Field(..., description="Last activity timestamp")

    model_config = {"frozen": True}
