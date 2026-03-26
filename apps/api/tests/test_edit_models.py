"""Tests for Edit model validation and serialization.

Tests all edit-related models from app.models.edit module.
Validates field validation, frozen behavior, enums, and serialization.
Phase 3: Edit & Adjust feature.
"""

from datetime import datetime, timezone

import pytest
from app.models.edit import (
    BatchEditRequest,
    BatchEditResponse,
    EditErrorCode,
    EditHistory,
    EditHistoryResponse,
    EditRequest,
    EditResponse,
    FieldEdit,
    FieldState,
    FieldValue,
    FieldValuesResponse,
    FieldValueUpdate,
    UndoRedoResponse,
)
from pydantic import ValidationError


class TestFieldEdit:
    """Tests for FieldEdit model."""

    def test_valid_field_edit(self) -> None:
        """Test creating a valid field edit."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-123",
            old_value="John",
            new_value="Jane",
            timestamp=now,
        )
        assert edit.field_id == "field-123"
        assert edit.old_value == "John"
        assert edit.new_value == "Jane"
        assert edit.timestamp == now

    def test_field_edit_without_old_value(self) -> None:
        """Test edit for new field (no previous value)."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-456",
            new_value="New Value",
            timestamp=now,
        )
        assert edit.old_value is None
        assert edit.new_value == "New Value"

    def test_field_edit_with_bbox_id(self) -> None:
        """Test edit with bounding box reference."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-789",
            new_value="Value",
            bbox_id="bbox-001",
            timestamp=now,
        )
        assert edit.bbox_id == "bbox-001"

    def test_field_edit_requires_field_id(self) -> None:
        """Test that field_id is required."""
        with pytest.raises(ValidationError):
            FieldEdit(
                new_value="Value",
                timestamp=datetime.now(timezone.utc),
            )

    def test_field_edit_requires_new_value(self) -> None:
        """Test that new_value is required."""
        with pytest.raises(ValidationError):
            FieldEdit(
                field_id="field-123",
                timestamp=datetime.now(timezone.utc),
            )

    def test_field_edit_requires_timestamp(self) -> None:
        """Test that timestamp is required."""
        with pytest.raises(ValidationError):
            FieldEdit(
                field_id="field-123",
                new_value="Value",
            )

    def test_field_edit_is_frozen(self) -> None:
        """Test that FieldEdit is immutable."""
        edit = FieldEdit(
            field_id="field-123",
            new_value="Value",
            timestamp=datetime.now(timezone.utc),
        )
        with pytest.raises(ValidationError):
            edit.new_value = "Modified"  # type: ignore


class TestEditHistory:
    """Tests for EditHistory model."""

    def test_empty_history(self) -> None:
        """Test creating empty history."""
        history = EditHistory(conversation_id="conv-123")
        assert history.conversation_id == "conv-123"
        assert history.edits == []
        assert history.current_index == -1

    def test_history_with_edits(self) -> None:
        """Test history with edit entries."""
        now = datetime.now(timezone.utc)
        edit1 = FieldEdit(
            field_id="field-1",
            new_value="value1",
            timestamp=now,
        )
        edit2 = FieldEdit(
            field_id="field-2",
            new_value="value2",
            timestamp=now,
        )

        history = EditHistory(
            conversation_id="conv-456",
            edits=[edit1, edit2],
            current_index=1,
        )
        assert len(history.edits) == 2
        assert history.current_index == 1

    def test_history_can_undo_at_first_edit(self) -> None:
        """Test can_undo when at first edit (index 0)."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-1",
            new_value="value",
            timestamp=now,
        )
        history = EditHistory(
            conversation_id="conv-123",
            edits=[edit],
            current_index=0,
        )
        assert history.can_undo is True
        assert history.can_redo is False

    def test_history_can_redo_after_undo(self) -> None:
        """Test can_redo after undo (index moved back)."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-1",
            new_value="value",
            timestamp=now,
        )
        # After undo, index is -1 (before any edits)
        history = EditHistory(
            conversation_id="conv-123",
            edits=[edit],
            current_index=-1,
        )
        assert history.can_undo is False
        assert history.can_redo is True

    def test_history_both_undo_and_redo(self) -> None:
        """Test when both undo and redo are available."""
        now = datetime.now(timezone.utc)
        edits = [
            FieldEdit(field_id=f"field-{i}", new_value=f"value{i}", timestamp=now) for i in range(3)
        ]
        # At index 1 (middle)
        history = EditHistory(
            conversation_id="conv-123",
            edits=edits,
            current_index=1,
        )
        assert history.can_undo is True
        assert history.can_redo is True

    def test_history_empty_cannot_undo_or_redo(self) -> None:
        """Test empty history cannot undo or redo."""
        history = EditHistory(conversation_id="conv-123")
        assert history.can_undo is False
        assert history.can_redo is False

    def test_history_current_index_validation(self) -> None:
        """Test current_index has minimum of -1."""
        with pytest.raises(ValidationError):
            EditHistory(
                conversation_id="conv-123",
                current_index=-2,
            )

    def test_history_is_frozen(self) -> None:
        """Test that history is immutable."""
        history = EditHistory(conversation_id="conv-123")
        with pytest.raises(ValidationError):
            history.current_index = 5  # type: ignore


class TestEditRequest:
    """Tests for EditRequest model."""

    def test_valid_edit_request(self) -> None:
        """Test creating valid edit request."""
        request = EditRequest(field_id="field-123", value="New Value")
        assert request.field_id == "field-123"
        assert request.value == "New Value"
        assert request.source == "chat"  # default

    def test_edit_request_inline_source(self) -> None:
        """Test edit request with inline source."""
        request = EditRequest(
            field_id="field-456",
            value="Inline Edit",
            source="inline",
        )
        assert request.source == "inline"

    def test_edit_request_requires_field_id(self) -> None:
        """Test that field_id is required."""
        with pytest.raises(ValidationError):
            EditRequest(value="Test")

    def test_edit_request_empty_field_id_fails(self) -> None:
        """Test that empty field_id is rejected."""
        with pytest.raises(ValidationError):
            EditRequest(field_id="", value="Test")

    def test_edit_request_requires_value(self) -> None:
        """Test that value is required."""
        with pytest.raises(ValidationError):
            EditRequest(field_id="field-123")

    def test_edit_request_is_frozen(self) -> None:
        """Test that request is immutable."""
        request = EditRequest(field_id="field-123", value="Test")
        with pytest.raises(ValidationError):
            request.value = "Modified"  # type: ignore


class TestFieldValueUpdate:
    """Tests for FieldValueUpdate model."""

    def test_valid_field_value_update(self) -> None:
        """Test creating valid field value update."""
        update = FieldValueUpdate(value="New Value")
        assert update.value == "New Value"
        assert update.source == "inline"  # default

    def test_field_value_update_chat_source(self) -> None:
        """Test update with chat source."""
        update = FieldValueUpdate(value="Chat Edit", source="chat")
        assert update.source == "chat"

    def test_field_value_update_requires_value(self) -> None:
        """Test that value is required."""
        with pytest.raises(ValidationError):
            FieldValueUpdate()

    def test_field_value_update_is_frozen(self) -> None:
        """Test that update is immutable."""
        update = FieldValueUpdate(value="Test")
        with pytest.raises(ValidationError):
            update.value = "Modified"  # type: ignore


class TestBatchEditRequest:
    """Tests for BatchEditRequest model."""

    def test_valid_batch_request(self) -> None:
        """Test creating valid batch edit request."""
        edits = [
            EditRequest(field_id="field-1", value="Value 1"),
            EditRequest(field_id="field-2", value="Value 2"),
        ]
        request = BatchEditRequest(edits=edits)
        assert len(request.edits) == 2

    def test_batch_requires_at_least_one_edit(self) -> None:
        """Test that batch requires at least one edit."""
        with pytest.raises(ValidationError):
            BatchEditRequest(edits=[])

    def test_batch_is_frozen(self) -> None:
        """Test that batch request is immutable."""
        edits = [EditRequest(field_id="field-1", value="Value")]
        request = BatchEditRequest(edits=edits)
        with pytest.raises(ValidationError):
            request.edits = []  # type: ignore


class TestEditResponse:
    """Tests for EditResponse model."""

    def test_success_response(self) -> None:
        """Test successful edit response."""
        response = EditResponse(
            success=True,
            field_id="field-123",
            old_value="old",
            new_value="new",
            message="Updated field to new",
        )
        assert response.success is True
        assert response.field_id == "field-123"
        assert response.old_value == "old"
        assert response.new_value == "new"
        assert response.message == "Updated field to new"

    def test_response_serialization(self) -> None:
        """Test response serializes to JSON correctly."""
        response = EditResponse(
            success=True,
            field_id="field-123",
            new_value="test",
            message="Done",
        )
        json_data = response.model_dump_json()
        assert "field-123" in json_data
        assert "true" in json_data.lower()

    def test_response_is_frozen(self) -> None:
        """Test that response is immutable."""
        response = EditResponse(
            success=True,
            field_id="field-123",
            new_value="test",
            message="Done",
        )
        with pytest.raises(ValidationError):
            response.success = False  # type: ignore


class TestBatchEditResponse:
    """Tests for BatchEditResponse model."""

    def test_valid_batch_response(self) -> None:
        """Test creating valid batch edit response."""
        results = [
            EditResponse(
                success=True,
                field_id="field-1",
                new_value="v1",
                message="Done",
            ),
            EditResponse(
                success=True,
                field_id="field-2",
                new_value="v2",
                message="Done",
            ),
        ]
        response = BatchEditResponse(
            success=True,
            results=results,
            summary="Updated 2 fields.",
        )
        assert response.success is True
        assert len(response.results) == 2
        assert response.summary == "Updated 2 fields."

    def test_batch_response_is_frozen(self) -> None:
        """Test that batch response is immutable."""
        response = BatchEditResponse(
            success=True,
            results=[],
            summary="No changes",
        )
        with pytest.raises(ValidationError):
            response.success = False  # type: ignore


class TestUndoRedoResponse:
    """Tests for UndoRedoResponse model."""

    def test_undo_response(self) -> None:
        """Test successful undo response."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-123",
            old_value="old",
            new_value="new",
            timestamp=now,
        )
        response = UndoRedoResponse(
            action="undo",
            edits_reverted=[edit],
            can_undo=False,
            can_redo=True,
        )
        assert response.action == "undo"
        assert len(response.edits_reverted) == 1
        assert response.can_undo is False
        assert response.can_redo is True

    def test_redo_response(self) -> None:
        """Test successful redo response."""
        response = UndoRedoResponse(
            action="redo",
            edits_reverted=[],
            can_undo=True,
            can_redo=False,
        )
        assert response.action == "redo"
        assert response.can_undo is True
        assert response.can_redo is False

    def test_response_is_frozen(self) -> None:
        """Test that response is immutable."""
        response = UndoRedoResponse(
            action="undo",
            can_undo=True,
            can_redo=False,
        )
        with pytest.raises(ValidationError):
            response.can_undo = False  # type: ignore


class TestFieldValue:
    """Tests for FieldValue model."""

    def test_field_value_with_value(self) -> None:
        """Test field value with value set."""
        now = datetime.now(timezone.utc)
        fv = FieldValue(
            field_id="field-123",
            value="Test Value",
            source="extracted",
            last_modified=now,
        )
        assert fv.field_id == "field-123"
        assert fv.value == "Test Value"
        assert fv.source == "extracted"
        assert fv.last_modified == now

    def test_field_value_empty(self) -> None:
        """Test field value without value."""
        fv = FieldValue(field_id="field-456")
        assert fv.value is None
        assert fv.source is None
        assert fv.last_modified is None

    def test_field_value_is_frozen(self) -> None:
        """Test that field value is immutable."""
        fv = FieldValue(field_id="field-123")
        with pytest.raises(ValidationError):
            fv.value = "Modified"  # type: ignore


class TestFieldValuesResponse:
    """Tests for FieldValuesResponse model."""

    def test_empty_fields_response(self) -> None:
        """Test response with no fields."""
        response = FieldValuesResponse(
            conversation_id="conv-123",
        )
        assert response.conversation_id == "conv-123"
        assert response.fields == []
        assert response.can_undo is False
        assert response.can_redo is False

    def test_response_with_fields(self) -> None:
        """Test response with fields and undo/redo state."""
        fields = [
            FieldValue(field_id="field-1", value="v1"),
            FieldValue(field_id="field-2", value="v2"),
        ]
        response = FieldValuesResponse(
            conversation_id="conv-456",
            fields=fields,
            can_undo=True,
            can_redo=False,
        )
        assert len(response.fields) == 2
        assert response.can_undo is True
        assert response.can_redo is False

    def test_response_is_frozen(self) -> None:
        """Test that response is immutable."""
        response = FieldValuesResponse(conversation_id="conv-123")
        with pytest.raises(ValidationError):
            response.can_undo = True  # type: ignore


class TestFieldState:
    """Tests for FieldState model (internal state)."""

    def test_valid_field_state(self) -> None:
        """Test creating valid field state."""
        now = datetime.now(timezone.utc)
        state = FieldState(
            field_id="field-123",
            current_value="Current",
            source="inline",
            last_modified=now,
        )
        assert state.field_id == "field-123"
        assert state.current_value == "Current"
        assert state.source == "inline"
        assert state.last_modified == now

    def test_field_state_empty(self) -> None:
        """Test field state with no value."""
        state = FieldState(field_id="field-456")
        assert state.current_value is None
        assert state.source is None

    def test_field_state_is_frozen(self) -> None:
        """Test that field state is immutable."""
        state = FieldState(field_id="field-123")
        with pytest.raises(ValidationError):
            state.current_value = "Modified"  # type: ignore


class TestEditHistoryResponse:
    """Tests for EditHistoryResponse model."""

    def test_empty_history_response(self) -> None:
        """Test response with empty history."""
        history = EditHistory(conversation_id="conv-123")
        response = EditHistoryResponse(
            conversation_id="conv-123",
            history=history,
            total_edits=0,
        )
        assert response.conversation_id == "conv-123"
        assert response.total_edits == 0
        assert len(response.history.edits) == 0

    def test_history_response_with_edits(self) -> None:
        """Test response with edits in history."""
        now = datetime.now(timezone.utc)
        edits = [
            FieldEdit(field_id=f"field-{i}", new_value=f"v{i}", timestamp=now) for i in range(3)
        ]
        history = EditHistory(
            conversation_id="conv-456",
            edits=edits,
            current_index=2,
        )
        response = EditHistoryResponse(
            conversation_id="conv-456",
            history=history,
            total_edits=3,
        )
        assert response.total_edits == 3
        assert len(response.history.edits) == 3

    def test_total_edits_validation(self) -> None:
        """Test total_edits cannot be negative."""
        history = EditHistory(conversation_id="conv-123")
        with pytest.raises(ValidationError):
            EditHistoryResponse(
                conversation_id="conv-123",
                history=history,
                total_edits=-1,
            )

    def test_response_is_frozen(self) -> None:
        """Test that response is immutable."""
        history = EditHistory(conversation_id="conv-123")
        response = EditHistoryResponse(
            conversation_id="conv-123",
            history=history,
            total_edits=0,
        )
        with pytest.raises(ValidationError):
            response.total_edits = 5  # type: ignore


class TestEditErrorCode:
    """Tests for EditErrorCode constants."""

    def test_field_error_codes(self) -> None:
        """Test field-related error codes exist."""
        assert EditErrorCode.FIELD_NOT_FOUND == "FIELD_NOT_FOUND"
        assert EditErrorCode.INVALID_FIELD_ID == "INVALID_FIELD_ID"

    def test_edit_error_codes(self) -> None:
        """Test edit-related error codes exist."""
        assert EditErrorCode.EDIT_FAILED == "EDIT_FAILED"
        assert EditErrorCode.BATCH_PARTIAL_FAILURE == "BATCH_PARTIAL_FAILURE"

    def test_undo_redo_error_codes(self) -> None:
        """Test undo/redo error codes exist."""
        assert EditErrorCode.NOTHING_TO_UNDO == "NOTHING_TO_UNDO"
        assert EditErrorCode.NOTHING_TO_REDO == "NOTHING_TO_REDO"


class TestModelSerialization:
    """Tests for model serialization/deserialization."""

    def test_field_edit_roundtrip(self) -> None:
        """Test FieldEdit serialization roundtrip."""
        now = datetime.now(timezone.utc)
        original = FieldEdit(
            field_id="field-123",
            old_value="old",
            new_value="new",
            timestamp=now,
        )
        json_data = original.model_dump()
        restored = FieldEdit.model_validate(json_data)
        assert restored.field_id == original.field_id
        assert restored.old_value == original.old_value
        assert restored.new_value == original.new_value

    def test_edit_history_roundtrip(self) -> None:
        """Test EditHistory serialization roundtrip."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-1",
            new_value="value",
            timestamp=now,
        )
        original = EditHistory(
            conversation_id="conv-123",
            edits=[edit],
            current_index=0,
        )
        json_data = original.model_dump()
        restored = EditHistory.model_validate(json_data)
        assert restored.conversation_id == original.conversation_id
        assert restored.current_index == original.current_index
        assert len(restored.edits) == 1

    def test_batch_edit_request_roundtrip(self) -> None:
        """Test BatchEditRequest serialization roundtrip."""
        original = BatchEditRequest(
            edits=[
                EditRequest(field_id="field-1", value="v1"),
                EditRequest(field_id="field-2", value="v2"),
            ],
        )
        json_data = original.model_dump()
        restored = BatchEditRequest.model_validate(json_data)
        assert len(restored.edits) == 2

    def test_undo_redo_response_roundtrip(self) -> None:
        """Test UndoRedoResponse serialization roundtrip."""
        original = UndoRedoResponse(
            action="undo",
            edits_reverted=[],
            can_undo=True,
            can_redo=False,
        )
        json_data = original.model_dump()
        restored = UndoRedoResponse.model_validate(json_data)
        assert restored.action == original.action
        assert restored.can_undo == original.can_undo
        assert restored.can_redo == original.can_redo
