"""Edit models for Agent Chat UI Phase 3.

These models define the API contracts for the edit and undo/redo system.
All models are immutable (frozen=True) for data integrity.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ============================================
# Bbox Model
# ============================================


class BboxData(BaseModel):
    """Bounding box data for a field position.

    Coordinates are normalized (0-1 range) relative to page dimensions.
    """

    x: float = Field(..., ge=0, le=1, description="X coordinate (0-1)")
    y: float = Field(..., ge=0, le=1, description="Y coordinate (0-1)")
    width: float = Field(..., ge=0, le=1, description="Width (0-1)")
    height: float = Field(..., ge=0, le=1, description="Height (0-1)")
    page: int = Field(..., ge=1, description="Page number (1-indexed)")

    model_config = {"frozen": True}


# ============================================
# Core Edit Models
# ============================================


class FieldEdit(BaseModel):
    """A single field edit operation.

    Represents one edit to a form field, storing both old and new values
    for undo/redo support. Also supports bbox changes for field positioning.
    """

    field_id: str = Field(..., description="ID of the field being edited")
    old_value: str | None = Field(None, description="Previous value (None if new)")
    new_value: str = Field(..., description="New value after edit")
    bbox_id: str | None = Field(None, description="Link to template bounding box")
    old_bbox: BboxData | None = Field(None, description="Previous bbox (None if unchanged)")
    new_bbox: BboxData | None = Field(None, description="New bbox after edit (None if unchanged)")
    timestamp: datetime = Field(..., description="When the edit was made")

    model_config = {"frozen": True}


class EditHistory(BaseModel):
    """Edit history for a conversation.

    Maintains a list of edits with a current index pointer for undo/redo.
    The current_index points to the last applied edit (0-based).
    When -1, no edits have been applied (initial state).
    """

    conversation_id: str = Field(..., description="Conversation this history belongs to")
    edits: list[FieldEdit] = Field(default_factory=list, description="List of all edits")
    current_index: int = Field(
        default=-1,
        ge=-1,
        description="Index of last applied edit (-1 means no edits applied)",
    )

    model_config = {"frozen": True}

    @property
    def can_undo(self) -> bool:
        """Check if there are edits that can be undone."""
        return self.current_index >= 0

    @property
    def can_redo(self) -> bool:
        """Check if there are edits that can be redone."""
        return self.current_index < len(self.edits) - 1


# ============================================
# Request Models
# ============================================


class EditRequest(BaseModel):
    """Request to edit a single field.

    Used for both chat-based edits ("change [field] to [value]")
    and inline edits (direct field value changes).
    """

    field_id: str = Field(..., min_length=1, description="ID of the field to edit")
    value: str = Field(..., description="New value for the field")
    source: Literal["chat", "inline"] = Field(
        default="chat",
        description="How the edit was initiated",
    )
    bbox: BboxData | None = Field(
        default=None,
        description="Optional bbox update for field position",
    )

    model_config = {"frozen": True}


class BatchEditRequest(BaseModel):
    """Request to edit multiple fields at once.

    Useful for bulk operations or when AI extracts multiple values.
    """

    edits: list[EditRequest] = Field(
        ...,
        min_length=1,
        description="List of edits to apply",
    )

    model_config = {"frozen": True}


class FieldValueUpdate(BaseModel):
    """Request body for PATCH field endpoint."""

    value: str = Field(..., description="New value for the field")
    source: Literal["chat", "inline"] = Field(
        default="inline",
        description="How the edit was initiated",
    )
    bbox: BboxData | None = Field(
        default=None,
        description="Optional bbox update for field position",
    )

    model_config = {"frozen": True}


# ============================================
# Response Models
# ============================================


class EditResponse(BaseModel):
    """Response after applying an edit.

    Contains both the edit details and a human-readable message.
    """

    success: bool = Field(..., description="Whether the edit was successful")
    field_id: str = Field(..., description="ID of the edited field")
    old_value: str | None = Field(None, description="Previous value")
    new_value: str = Field(..., description="New value after edit")
    message: str = Field(..., description="Human-readable message (e.g., 'Updated [field] to [value]')")

    model_config = {"frozen": True}


class BatchEditResponse(BaseModel):
    """Response after applying multiple edits."""

    success: bool = Field(..., description="Whether all edits were successful")
    results: list[EditResponse] = Field(..., description="Individual edit results")
    summary: str = Field(..., description="Summary message (e.g., 'Updated 5 fields.')")

    model_config = {"frozen": True}


class UndoRedoResponse(BaseModel):
    """Response after undo or redo operation.

    Provides details about what was reverted and current state.
    """

    action: Literal["undo", "redo"] = Field(..., description="The action that was performed")
    edits_reverted: list[FieldEdit] = Field(
        default_factory=list,
        description="Edits that were undone/redone",
    )
    can_undo: bool = Field(..., description="Whether more undos are possible")
    can_redo: bool = Field(..., description="Whether more redos are possible")

    model_config = {"frozen": True}


class FieldValue(BaseModel):
    """Current value of a field."""

    field_id: str = Field(..., description="ID of the field")
    value: str | None = Field(None, description="Current value (None if not set)")
    source: Literal["extracted", "chat", "inline", "default"] | None = Field(
        None,
        description="How the value was set",
    )
    last_modified: datetime | None = Field(None, description="When value was last changed")
    bbox: BboxData | None = Field(None, description="Current bounding box position")

    model_config = {"frozen": True}


class FieldValuesResponse(BaseModel):
    """Response containing all field values for a conversation."""

    conversation_id: str = Field(..., description="Conversation ID")
    fields: list[FieldValue] = Field(default_factory=list, description="All field values")
    can_undo: bool = Field(default=False, description="Whether undo is available")
    can_redo: bool = Field(default=False, description="Whether redo is available")

    model_config = {"frozen": True}


class EditHistoryResponse(BaseModel):
    """Response containing the edit history for a conversation."""

    conversation_id: str = Field(..., description="Conversation ID")
    history: EditHistory = Field(..., description="Full edit history")
    total_edits: int = Field(..., ge=0, description="Total number of edits in history")

    model_config = {"frozen": True}


# ============================================
# Error Codes for Edit Operations
# ============================================


class EditErrorCode:
    """Error codes specific to edit operations."""

    FIELD_NOT_FOUND = "FIELD_NOT_FOUND"
    EDIT_FAILED = "EDIT_FAILED"
    NOTHING_TO_UNDO = "NOTHING_TO_UNDO"
    NOTHING_TO_REDO = "NOTHING_TO_REDO"
    INVALID_FIELD_ID = "INVALID_FIELD_ID"
    BATCH_PARTIAL_FAILURE = "BATCH_PARTIAL_FAILURE"


# ============================================
# Internal State Models (for repository use)
# ============================================


class FieldState(BaseModel):
    """Internal state of a field.

    Used by the repository to track current field values and bounding box.
    """

    field_id: str = Field(..., description="ID of the field")
    current_value: str | None = Field(None, description="Current value")
    source: Literal["extracted", "chat", "inline", "default"] | None = Field(
        None,
        description="How the value was set",
    )
    last_modified: datetime | None = Field(None, description="When value was last changed")
    bbox: BboxData | None = Field(None, description="Current bounding box position")

    model_config = {"frozen": True}
