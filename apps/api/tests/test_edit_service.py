"""Tests for Edit Service operations.

Tests the EditService business logic with mocked repository.
Validates apply_edit, undo, redo, batch edits, and error handling.
Phase 3: Edit & Adjust feature.
"""

from datetime import datetime, timezone
from typing import Any

import pytest
from app.models.edit import (
    BatchEditRequest,
    EditHistory,
    EditRequest,
    FieldEdit,
    FieldState,
    FieldValue,
)


class MockEditRepository:
    """Mock edit repository for service tests."""

    def __init__(self) -> None:
        self._histories: dict[str, EditHistory] = {}
        self._field_states: dict[str, dict[str, FieldState]] = {}
        self._calls: list[dict[str, Any]] = []

    def record_call(self, method: str, **kwargs: Any) -> None:
        """Record method calls for verification."""
        self._calls.append({"method": method, **kwargs})

    def save_edit(self, conversation_id: str, edit: FieldEdit) -> FieldEdit:
        self.record_call("save_edit", conversation_id=conversation_id, edit=edit)

        history = self._histories.get(
            conversation_id,
            EditHistory(conversation_id=conversation_id),
        )

        current_edits = list(history.edits[: history.current_index + 1])
        current_edits.append(edit)

        self._histories[conversation_id] = EditHistory(
            conversation_id=conversation_id,
            edits=current_edits,
            current_index=len(current_edits) - 1,
        )

        if conversation_id not in self._field_states:
            self._field_states[conversation_id] = {}

        self._field_states[conversation_id][edit.field_id] = FieldState(
            field_id=edit.field_id,
            current_value=edit.new_value,
            source="inline",
            last_modified=edit.timestamp,
        )

        return edit

    def get_history(self, conversation_id: str) -> EditHistory:
        self.record_call("get_history", conversation_id=conversation_id)
        return self._histories.get(
            conversation_id,
            EditHistory(conversation_id=conversation_id),
        )

    def undo(self, conversation_id: str) -> list[FieldEdit] | None:
        self.record_call("undo", conversation_id=conversation_id)

        history = self._histories.get(conversation_id)
        if history is None or not history.can_undo:
            return None

        edit_to_undo = history.edits[history.current_index]

        self._histories[conversation_id] = EditHistory(
            conversation_id=conversation_id,
            edits=history.edits,
            current_index=history.current_index - 1,
        )

        if conversation_id in self._field_states:
            self._field_states[conversation_id][edit_to_undo.field_id] = FieldState(
                field_id=edit_to_undo.field_id,
                current_value=edit_to_undo.old_value,
                source="default",
                last_modified=datetime.now(timezone.utc),
            )

        return [edit_to_undo]

    def redo(self, conversation_id: str) -> list[FieldEdit] | None:
        self.record_call("redo", conversation_id=conversation_id)

        history = self._histories.get(conversation_id)
        if history is None or not history.can_redo:
            return None

        edit_to_redo = history.edits[history.current_index + 1]

        self._histories[conversation_id] = EditHistory(
            conversation_id=conversation_id,
            edits=history.edits,
            current_index=history.current_index + 1,
        )

        if conversation_id in self._field_states:
            self._field_states[conversation_id][edit_to_redo.field_id] = FieldState(
                field_id=edit_to_redo.field_id,
                current_value=edit_to_redo.new_value,
                source="inline",
                last_modified=datetime.now(timezone.utc),
            )

        return [edit_to_redo]

    def clear_history(self, conversation_id: str) -> None:
        self.record_call("clear_history", conversation_id=conversation_id)
        self._histories.pop(conversation_id, None)
        self._field_states.pop(conversation_id, None)

    def get_field_value(self, conversation_id: str, field_id: str) -> FieldState | None:
        self.record_call("get_field_value", conversation_id=conversation_id, field_id=field_id)
        conv_states = self._field_states.get(conversation_id, {})
        return conv_states.get(field_id)

    def get_all_field_values(self, conversation_id: str) -> list[FieldState]:
        self.record_call("get_all_field_values", conversation_id=conversation_id)
        return list(self._field_states.get(conversation_id, {}).values())

    def set_field_value(self, conversation_id: str, field_state: FieldState) -> FieldState:
        self.record_call(
            "set_field_value",
            conversation_id=conversation_id,
            field_state=field_state,
        )
        if conversation_id not in self._field_states:
            self._field_states[conversation_id] = {}
        self._field_states[conversation_id][field_state.field_id] = field_state
        return field_state


class MockConversationRepository:
    """Mock conversation repository for existence checks."""

    def __init__(self) -> None:
        self._conversations: set[str] = set()

    def add_conversation(self, conv_id: str) -> None:
        self._conversations.add(conv_id)

    def get(self, conversation_id: str) -> dict | None:
        if conversation_id in self._conversations:
            return {"id": conversation_id, "status": "active"}
        return None


class MockFieldRepository:
    """Mock field repository for field validation."""

    def __init__(self) -> None:
        self._fields: dict[str, dict[str, Any]] = {}

    def add_field(self, conv_id: str, field_id: str, editable: bool = True) -> None:
        if conv_id not in self._fields:
            self._fields[conv_id] = {}
        self._fields[conv_id][field_id] = {
            "id": field_id,
            "editable": editable,
            "value": None,
        }

    def get_field(self, conv_id: str, field_id: str) -> dict | None:
        return self._fields.get(conv_id, {}).get(field_id)

    def is_editable(self, conv_id: str, field_id: str) -> bool:
        field = self.get_field(conv_id, field_id)
        return field is not None and field.get("editable", True)


class EditService:
    """Simple EditService for testing.

    In real implementation, this would be in app/services/edit/.
    """

    def __init__(
        self,
        edit_repo: MockEditRepository,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        self._edit_repo = edit_repo
        self._conv_repo = conv_repo
        self._field_repo = field_repo

    def apply_edit(
        self,
        conversation_id: str,
        request: EditRequest,
    ) -> dict[str, Any]:
        """Apply a single field edit."""
        # Check conversation exists
        if self._conv_repo.get(conversation_id) is None:
            return {
                "success": False,
                "error_code": "CONVERSATION_NOT_FOUND",
                "error_message": "Conversation not found",
            }

        # Check field exists
        field = self._field_repo.get_field(conversation_id, request.field_id)
        if field is None:
            return {
                "success": False,
                "error_code": "FIELD_NOT_FOUND",
                "error_message": f"Field {request.field_id} not found",
            }

        # Check field is editable
        if not self._field_repo.is_editable(conversation_id, request.field_id):
            return {
                "success": False,
                "error_code": "FIELD_NOT_EDITABLE",
                "error_message": f"Field {request.field_id} is not editable",
            }

        # Get old value
        old_state = self._edit_repo.get_field_value(conversation_id, request.field_id)
        old_value = old_state.current_value if old_state else None

        # Create and save edit
        edit = FieldEdit(
            field_id=request.field_id,
            old_value=old_value,
            new_value=request.value,
            timestamp=datetime.now(timezone.utc),
        )
        self._edit_repo.save_edit(conversation_id, edit)

        # Get updated history for can_undo/can_redo
        history = self._edit_repo.get_history(conversation_id)

        return {
            "success": True,
            "field_id": request.field_id,
            "old_value": old_value,
            "new_value": request.value,
            "can_undo": history.can_undo,
            "can_redo": history.can_redo,
            "message": f"Updated {request.field_id} to {request.value}",
        }

    def apply_batch_edits(
        self,
        conversation_id: str,
        request: BatchEditRequest,
    ) -> dict[str, Any]:
        """Apply multiple field edits."""
        # Check conversation exists
        if self._conv_repo.get(conversation_id) is None:
            return {
                "success": False,
                "error_code": "CONVERSATION_NOT_FOUND",
                "error_message": "Conversation not found",
                "results": [],
            }

        results = []
        all_success = True

        for edit_request in request.edits:
            result = self.apply_edit(conversation_id, edit_request)
            results.append(result)
            if not result["success"]:
                all_success = False

        return {
            "success": all_success,
            "results": results,
            "summary": f"Updated {sum(1 for r in results if r['success'])} of {len(results)} fields",
        }

    def undo(self, conversation_id: str) -> dict[str, Any]:
        """Undo the last edit."""
        if self._conv_repo.get(conversation_id) is None:
            return {
                "success": False,
                "error_code": "CONVERSATION_NOT_FOUND",
                "error_message": "Conversation not found",
            }

        reverted = self._edit_repo.undo(conversation_id)
        if reverted is None:
            return {
                "success": False,
                "error_code": "NOTHING_TO_UNDO",
                "error_message": "No edits to undo",
            }

        history = self._edit_repo.get_history(conversation_id)

        return {
            "success": True,
            "action": "undo",
            "edits_reverted": reverted,
            "can_undo": history.can_undo,
            "can_redo": history.can_redo,
        }

    def redo(self, conversation_id: str) -> dict[str, Any]:
        """Redo the last undone edit."""
        if self._conv_repo.get(conversation_id) is None:
            return {
                "success": False,
                "error_code": "CONVERSATION_NOT_FOUND",
                "error_message": "Conversation not found",
            }

        redone = self._edit_repo.redo(conversation_id)
        if redone is None:
            return {
                "success": False,
                "error_code": "NOTHING_TO_REDO",
                "error_message": "No edits to redo",
            }

        history = self._edit_repo.get_history(conversation_id)

        return {
            "success": True,
            "action": "redo",
            "edits_reverted": redone,
            "can_undo": history.can_undo,
            "can_redo": history.can_redo,
        }

    def get_field_value(self, conversation_id: str, field_id: str) -> dict[str, Any] | None:
        """Get current value of a field."""
        if self._conv_repo.get(conversation_id) is None:
            return None

        state = self._edit_repo.get_field_value(conversation_id, field_id)
        if state is None:
            return None

        return {
            "field_id": state.field_id,
            "value": state.current_value,
            "source": state.source,
            "last_modified": state.last_modified,
        }

    def get_all_field_values(self, conversation_id: str) -> dict[str, Any]:
        """Get all field values for a conversation."""
        if self._conv_repo.get(conversation_id) is None:
            return {
                "success": False,
                "error_code": "CONVERSATION_NOT_FOUND",
                "fields": [],
            }

        states = self._edit_repo.get_all_field_values(conversation_id)
        history = self._edit_repo.get_history(conversation_id)

        return {
            "success": True,
            "conversation_id": conversation_id,
            "fields": [
                FieldValue(
                    field_id=s.field_id,
                    value=s.current_value,
                    source=s.source,
                    last_modified=s.last_modified,
                )
                for s in states
            ],
            "can_undo": history.can_undo,
            "can_redo": history.can_redo,
        }


@pytest.fixture
def edit_repo() -> MockEditRepository:
    return MockEditRepository()


@pytest.fixture
def conv_repo() -> MockConversationRepository:
    return MockConversationRepository()


@pytest.fixture
def field_repo() -> MockFieldRepository:
    return MockFieldRepository()


@pytest.fixture
def edit_service(
    edit_repo: MockEditRepository,
    conv_repo: MockConversationRepository,
    field_repo: MockFieldRepository,
) -> EditService:
    return EditService(edit_repo, conv_repo, field_repo)


class TestApplyEdit:
    """Tests for apply_edit operation."""

    def test_apply_edit_updates_field_value(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test that apply_edit updates field value."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")

        request = EditRequest(field_id="name", value="John Doe")
        result = edit_service.apply_edit("conv-001", request)

        assert result["success"] is True
        assert result["new_value"] == "John Doe"
        assert result["field_id"] == "name"

    def test_apply_edit_records_to_history(
        self,
        edit_service: EditService,
        edit_repo: MockEditRepository,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test that apply_edit creates history record."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")

        request = EditRequest(field_id="name", value="John Doe")
        edit_service.apply_edit("conv-001", request)

        # Check save_edit was called
        save_calls = [c for c in edit_repo._calls if c["method"] == "save_edit"]
        assert len(save_calls) == 1
        assert save_calls[0]["edit"].new_value == "John Doe"

    def test_apply_edit_returns_old_value(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test that apply_edit returns the previous value."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")

        # First edit
        request1 = EditRequest(field_id="name", value="First")
        edit_service.apply_edit("conv-001", request1)

        # Second edit should return "First" as old value
        request2 = EditRequest(field_id="name", value="Second")
        result = edit_service.apply_edit("conv-001", request2)

        assert result["old_value"] == "First"
        assert result["new_value"] == "Second"

    def test_apply_edit_conversation_not_found(
        self,
        edit_service: EditService,
    ) -> None:
        """Test error when conversation doesn't exist."""
        request = EditRequest(field_id="name", value="Value")
        result = edit_service.apply_edit("non-existent", request)

        assert result["success"] is False
        assert result["error_code"] == "CONVERSATION_NOT_FOUND"

    def test_apply_edit_field_not_found(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
    ) -> None:
        """Test error when field doesn't exist."""
        conv_repo.add_conversation("conv-001")

        request = EditRequest(field_id="non-existent", value="Value")
        result = edit_service.apply_edit("conv-001", request)

        assert result["success"] is False
        assert result["error_code"] == "FIELD_NOT_FOUND"

    def test_apply_edit_field_not_editable(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test error when field is not editable."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "readonly", editable=False)

        request = EditRequest(field_id="readonly", value="Value")
        result = edit_service.apply_edit("conv-001", request)

        assert result["success"] is False
        assert result["error_code"] == "FIELD_NOT_EDITABLE"


class TestApplyBatchEdits:
    """Tests for apply_batch_edits operation."""

    def test_apply_batch_edits_handles_multiple_fields(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test batch edit updates multiple fields."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")
        field_repo.add_field("conv-001", "email")
        field_repo.add_field("conv-001", "phone")

        request = BatchEditRequest(
            edits=[
                EditRequest(field_id="name", value="John"),
                EditRequest(field_id="email", value="john@example.com"),
                EditRequest(field_id="phone", value="555-1234"),
            ]
        )

        result = edit_service.apply_batch_edits("conv-001", request)

        assert result["success"] is True
        assert len(result["results"]) == 3
        assert all(r["success"] for r in result["results"])
        assert "3 of 3" in result["summary"]

    def test_apply_batch_edits_partial_failure(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test batch edit with some fields failing."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")
        # "email" field doesn't exist

        request = BatchEditRequest(
            edits=[
                EditRequest(field_id="name", value="John"),
                EditRequest(field_id="email", value="john@example.com"),
            ]
        )

        result = edit_service.apply_batch_edits("conv-001", request)

        assert result["success"] is False
        assert result["results"][0]["success"] is True
        assert result["results"][1]["success"] is False
        assert "1 of 2" in result["summary"]


class TestUndo:
    """Tests for undo operation."""

    def test_undo_reverts_last_edit(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test that undo reverts the last edit."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")

        # Apply edit
        request = EditRequest(field_id="name", value="New Value")
        edit_service.apply_edit("conv-001", request)

        # Undo
        result = edit_service.undo("conv-001")

        assert result["success"] is True
        assert result["action"] == "undo"
        assert len(result["edits_reverted"]) == 1
        assert result["edits_reverted"][0].new_value == "New Value"

    def test_undo_nothing_to_undo(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
    ) -> None:
        """Test undo with no edits returns error."""
        conv_repo.add_conversation("conv-001")

        result = edit_service.undo("conv-001")

        assert result["success"] is False
        assert result["error_code"] == "NOTHING_TO_UNDO"

    def test_undo_conversation_not_found(
        self,
        edit_service: EditService,
    ) -> None:
        """Test undo with non-existent conversation."""
        result = edit_service.undo("non-existent")

        assert result["success"] is False
        assert result["error_code"] == "CONVERSATION_NOT_FOUND"


class TestRedo:
    """Tests for redo operation."""

    def test_redo_re_applies_edit(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test that redo re-applies an undone edit."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")

        # Apply and undo
        request = EditRequest(field_id="name", value="New Value")
        edit_service.apply_edit("conv-001", request)
        edit_service.undo("conv-001")

        # Redo
        result = edit_service.redo("conv-001")

        assert result["success"] is True
        assert result["action"] == "redo"
        assert len(result["edits_reverted"]) == 1
        assert result["edits_reverted"][0].new_value == "New Value"

    def test_redo_nothing_to_redo(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test redo when nothing to redo."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")

        # Apply edit without undo
        request = EditRequest(field_id="name", value="Value")
        edit_service.apply_edit("conv-001", request)

        result = edit_service.redo("conv-001")

        assert result["success"] is False
        assert result["error_code"] == "NOTHING_TO_REDO"


class TestGetFieldValue:
    """Tests for get_field_value operation."""

    def test_get_field_value_returns_current_value(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test getting current field value."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")

        request = EditRequest(field_id="name", value="John Doe")
        edit_service.apply_edit("conv-001", request)

        result = edit_service.get_field_value("conv-001", "name")

        assert result is not None
        assert result["value"] == "John Doe"

    def test_get_field_value_not_found(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
    ) -> None:
        """Test getting non-existent field value returns None."""
        conv_repo.add_conversation("conv-001")

        result = edit_service.get_field_value("conv-001", "non-existent")

        assert result is None


class TestGetAllFieldValues:
    """Tests for get_all_field_values operation."""

    def test_get_all_field_values(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test getting all field values."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")
        field_repo.add_field("conv-001", "email")

        edit_service.apply_edit("conv-001", EditRequest(field_id="name", value="John"))
        edit_service.apply_edit("conv-001", EditRequest(field_id="email", value="john@example.com"))

        result = edit_service.get_all_field_values("conv-001")

        assert result["success"] is True
        assert len(result["fields"]) == 2

    def test_get_all_field_values_empty(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
    ) -> None:
        """Test getting fields when none exist."""
        conv_repo.add_conversation("conv-001")

        result = edit_service.get_all_field_values("conv-001")

        assert result["success"] is True
        assert len(result["fields"]) == 0


class TestUndoRedoCanFlags:
    """Tests for can_undo and can_redo flags in responses."""

    def test_can_undo_after_edit(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test can_undo is True after edit."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")

        request = EditRequest(field_id="name", value="Value")
        result = edit_service.apply_edit("conv-001", request)

        assert result["can_undo"] is True
        assert result["can_redo"] is False

    def test_can_redo_after_undo(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test can_redo is True after undo."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")

        edit_service.apply_edit("conv-001", EditRequest(field_id="name", value="V"))
        result = edit_service.undo("conv-001")

        assert result["can_undo"] is False
        assert result["can_redo"] is True

    def test_both_flags_in_middle(
        self,
        edit_service: EditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test both flags can be True when in middle of history."""
        conv_repo.add_conversation("conv-001")
        field_repo.add_field("conv-001", "name")

        edit_service.apply_edit("conv-001", EditRequest(field_id="name", value="V1"))
        edit_service.apply_edit("conv-001", EditRequest(field_id="name", value="V2"))
        result = edit_service.undo("conv-001")

        assert result["can_undo"] is True
        assert result["can_redo"] is True
