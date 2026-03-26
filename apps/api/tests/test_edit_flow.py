"""Integration tests for complete Edit workflow.

Tests end-to-end edit scenarios including:
- Create conversation -> Fill form -> Edit field -> Verify change
- Undo/Redo sequences
- Chat command edits vs inline edits
Phase 3: Edit & Adjust feature.
"""

from datetime import datetime, timezone
from typing import Any

import pytest
from app.models.edit import (
    EditHistory,
    FieldEdit,
    FieldState,
)


class MockEditRepository:
    """Mock repository for integration tests."""

    def __init__(self) -> None:
        self._histories: dict[str, EditHistory] = {}
        self._field_states: dict[str, dict[str, FieldState]] = {}

    def save_edit(self, conversation_id: str, edit: FieldEdit) -> FieldEdit:
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
        return self._histories.get(
            conversation_id,
            EditHistory(conversation_id=conversation_id),
        )

    def undo(self, conversation_id: str) -> list[FieldEdit] | None:
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

    def get_field_value(self, conversation_id: str, field_id: str) -> FieldState | None:
        return self._field_states.get(conversation_id, {}).get(field_id)


class MockConversationRepository:
    """Mock conversation repository for integration tests."""

    def __init__(self) -> None:
        self._conversations: dict[str, dict] = {}

    def create(self, title: str = "Test Conversation") -> dict:
        conv_id = f"conv-{len(self._conversations) + 1:03d}"
        conv = {
            "id": conv_id,
            "title": title,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
        }
        self._conversations[conv_id] = conv
        return conv

    def get(self, conversation_id: str) -> dict | None:
        return self._conversations.get(conversation_id)


class MockFieldRepository:
    """Mock field repository for integration tests."""

    def __init__(self) -> None:
        self._fields: dict[str, dict[str, dict]] = {}

    def add_field(
        self,
        conv_id: str,
        field_id: str,
        name: str,
        editable: bool = True,
        value: str | None = None,
    ) -> dict:
        if conv_id not in self._fields:
            self._fields[conv_id] = {}

        field = {
            "id": field_id,
            "name": name,
            "editable": editable,
            "value": value,
        }
        self._fields[conv_id][field_id] = field
        return field

    def get_field(self, conv_id: str, field_id: str) -> dict | None:
        return self._fields.get(conv_id, {}).get(field_id)

    def set_field_value(self, conv_id: str, field_id: str, value: str) -> None:
        if conv_id in self._fields and field_id in self._fields[conv_id]:
            self._fields[conv_id][field_id]["value"] = value


class IntegrationEditService:
    """Integration service combining all repositories."""

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
        field_id: str,
        value: str,
        source: str = "inline",
    ) -> dict[str, Any]:
        conv = self._conv_repo.get(conversation_id)
        if conv is None:
            return {"success": False, "error": "CONVERSATION_NOT_FOUND"}

        field = self._field_repo.get_field(conversation_id, field_id)
        if field is None:
            return {"success": False, "error": "FIELD_NOT_FOUND"}

        if not field.get("editable", True):
            return {"success": False, "error": "FIELD_NOT_EDITABLE"}

        old_state = self._edit_repo.get_field_value(conversation_id, field_id)
        old_value = old_state.current_value if old_state else field.get("value")

        edit = FieldEdit(
            field_id=field_id,
            old_value=old_value,
            new_value=value,
            timestamp=datetime.now(timezone.utc),
        )

        self._edit_repo.save_edit(conversation_id, edit)
        self._field_repo.set_field_value(conversation_id, field_id, value)

        history = self._edit_repo.get_history(conversation_id)

        return {
            "success": True,
            "field_id": field_id,
            "old_value": old_value,
            "new_value": value,
            "source": source,
            "can_undo": history.can_undo,
            "can_redo": history.can_redo,
        }

    def undo(self, conversation_id: str) -> dict[str, Any]:
        conv = self._conv_repo.get(conversation_id)
        if conv is None:
            return {"success": False, "error": "CONVERSATION_NOT_FOUND"}

        reverted = self._edit_repo.undo(conversation_id)
        if reverted is None:
            return {"success": False, "error": "NOTHING_TO_UNDO"}

        for edit in reverted:
            self._field_repo.set_field_value(conversation_id, edit.field_id, edit.old_value or "")

        history = self._edit_repo.get_history(conversation_id)

        return {
            "success": True,
            "action": "undo",
            "edits_reverted": reverted,
            "can_undo": history.can_undo,
            "can_redo": history.can_redo,
        }

    def redo(self, conversation_id: str) -> dict[str, Any]:
        conv = self._conv_repo.get(conversation_id)
        if conv is None:
            return {"success": False, "error": "CONVERSATION_NOT_FOUND"}

        redone = self._edit_repo.redo(conversation_id)
        if redone is None:
            return {"success": False, "error": "NOTHING_TO_REDO"}

        for edit in redone:
            self._field_repo.set_field_value(conversation_id, edit.field_id, edit.new_value)

        history = self._edit_repo.get_history(conversation_id)

        return {
            "success": True,
            "action": "redo",
            "edits_reverted": redone,
            "can_undo": history.can_undo,
            "can_redo": history.can_redo,
        }

    def get_field_value(self, conversation_id: str, field_id: str) -> str | None:
        field = self._field_repo.get_field(conversation_id, field_id)
        if field is None:
            return None

        state = self._edit_repo.get_field_value(conversation_id, field_id)
        if state:
            return state.current_value
        return field.get("value")


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
def service(
    edit_repo: MockEditRepository,
    conv_repo: MockConversationRepository,
    field_repo: MockFieldRepository,
) -> IntegrationEditService:
    return IntegrationEditService(edit_repo, conv_repo, field_repo)


class TestCompleteWorkflow:
    """Test complete edit workflows."""

    def test_create_fill_edit_verify(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test: Create conversation -> Fill form -> Edit field -> Verify."""
        # 1. Create conversation
        conv = conv_repo.create("Tax Form")
        conv_id = conv["id"]

        # 2. Add form fields with initial values (simulating form fill)
        field_repo.add_field(conv_id, "name", "Full Name", value="John Doe")
        field_repo.add_field(conv_id, "ssn", "Social Security", value="123-45-6789")
        field_repo.add_field(conv_id, "address", "Address", value="123 Main St")

        # 3. Edit a field
        result = service.apply_edit(conv_id, "name", "Jane Doe")

        assert result["success"] is True
        assert result["old_value"] == "John Doe"
        assert result["new_value"] == "Jane Doe"

        # 4. Verify the change
        current_value = service.get_field_value(conv_id, "name")
        assert current_value == "Jane Doe"

    def test_edit_undo_verify_reverted(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test: Edit -> Undo -> Verify reverted."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "email", "Email", value="old@example.com")

        # Edit
        service.apply_edit(conv_id, "email", "new@example.com")
        assert service.get_field_value(conv_id, "email") == "new@example.com"

        # Undo
        result = service.undo(conv_id)
        assert result["success"] is True
        assert result["action"] == "undo"

        # Verify reverted
        assert service.get_field_value(conv_id, "email") == "old@example.com"

    def test_edit_undo_redo_verify_restored(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test: Edit -> Undo -> Redo -> Verify restored."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "phone", "Phone", value="555-1234")

        # Edit
        service.apply_edit(conv_id, "phone", "555-5678")

        # Undo
        service.undo(conv_id)
        assert service.get_field_value(conv_id, "phone") == "555-1234"

        # Redo
        result = service.redo(conv_id)
        assert result["success"] is True
        assert result["action"] == "redo"

        # Verify restored
        assert service.get_field_value(conv_id, "phone") == "555-5678"

    def test_multiple_edits_undo_multiple_verify_batch_revert(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test: Multiple edits -> Undo multiple -> Verify batch revert."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "f1", "Field 1", value="Original 1")
        field_repo.add_field(conv_id, "f2", "Field 2", value="Original 2")
        field_repo.add_field(conv_id, "f3", "Field 3", value="Original 3")

        # Multiple edits
        service.apply_edit(conv_id, "f1", "Edited 1")
        service.apply_edit(conv_id, "f2", "Edited 2")
        service.apply_edit(conv_id, "f3", "Edited 3")

        # Verify all edited
        assert service.get_field_value(conv_id, "f1") == "Edited 1"
        assert service.get_field_value(conv_id, "f2") == "Edited 2"
        assert service.get_field_value(conv_id, "f3") == "Edited 3"

        # Undo all three
        service.undo(conv_id)  # Reverts f3
        service.undo(conv_id)  # Reverts f2
        service.undo(conv_id)  # Reverts f1

        # Verify all reverted
        assert service.get_field_value(conv_id, "f1") == "Original 1"
        assert service.get_field_value(conv_id, "f2") == "Original 2"
        assert service.get_field_value(conv_id, "f3") == "Original 3"


class TestChatCommandEdit:
    """Test chat command edits (source="chat")."""

    def test_chat_command_edit(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test edit initiated via chat command."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "name", "Name", value="Original")

        # Chat command: "change name to New Name"
        result = service.apply_edit(conv_id, "name", "New Name", source="chat")

        assert result["success"] is True
        assert result["source"] == "chat"
        assert result["new_value"] == "New Name"


class TestInlineEdit:
    """Test inline edits (source="inline")."""

    def test_inline_edit(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test edit initiated via inline field editor."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "address", "Address", value="123 Main St")

        # User clicks field and types new value
        result = service.apply_edit(conv_id, "address", "456 Oak Ave", source="inline")

        assert result["success"] is True
        assert result["source"] == "inline"
        assert result["new_value"] == "456 Oak Ave"


class TestUndoRedoFlags:
    """Test can_undo and can_redo flags throughout workflow."""

    def test_flags_throughout_workflow(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test undo/redo flags at each step of workflow."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "field", "Field", value="Original")

        # Initial state: nothing to undo or redo
        # (We need to make an edit to check flags)

        # First edit
        r1 = service.apply_edit(conv_id, "field", "V1")
        assert r1["can_undo"] is True
        assert r1["can_redo"] is False

        # Second edit
        r2 = service.apply_edit(conv_id, "field", "V2")
        assert r2["can_undo"] is True
        assert r2["can_redo"] is False

        # Undo once
        r3 = service.undo(conv_id)
        assert r3["can_undo"] is True  # Can still undo V1
        assert r3["can_redo"] is True  # Can redo V2

        # Undo again
        r4 = service.undo(conv_id)
        assert r4["can_undo"] is False  # No more to undo
        assert r4["can_redo"] is True  # Can redo V1 and V2

        # Redo once
        r5 = service.redo(conv_id)
        assert r5["can_undo"] is True
        assert r5["can_redo"] is True

        # Redo again
        r6 = service.redo(conv_id)
        assert r6["can_undo"] is True
        assert r6["can_redo"] is False  # Back at the end


class TestEdgeCase:
    """Test edge cases in edit workflow."""

    def test_edit_same_field_multiple_times(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test editing the same field multiple times."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "name", "Name", value="Original")

        values = ["First", "Second", "Third", "Fourth"]
        for value in values:
            service.apply_edit(conv_id, "name", value)

        assert service.get_field_value(conv_id, "name") == "Fourth"

        # Undo back to "Second"
        service.undo(conv_id)  # Fourth -> Third
        service.undo(conv_id)  # Third -> Second

        assert service.get_field_value(conv_id, "name") == "Second"

    def test_new_edit_clears_redo_stack(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test that new edit after undo clears redo stack."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "field", "Field")

        # Create some history
        service.apply_edit(conv_id, "field", "V1")
        service.apply_edit(conv_id, "field", "V2")

        # Undo one
        service.undo(conv_id)
        assert service.get_field_value(conv_id, "field") == "V1"

        # Make a new edit (different path)
        r = service.apply_edit(conv_id, "field", "V3")
        assert r["can_redo"] is False  # Redo stack should be cleared

        # Verify can't redo to V2 anymore
        result = service.redo(conv_id)
        assert result["success"] is False

    def test_undo_empty_history(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test undo on conversation with no edits."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "field", "Field", value="Original")

        result = service.undo(conv_id)

        assert result["success"] is False
        assert result["error"] == "NOTHING_TO_UNDO"

    def test_redo_without_undo(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test redo when nothing has been undone."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "field", "Field")

        service.apply_edit(conv_id, "field", "Value")

        result = service.redo(conv_id)

        assert result["success"] is False
        assert result["error"] == "NOTHING_TO_REDO"

    def test_edit_nonexistent_conversation(
        self,
        service: IntegrationEditService,
    ) -> None:
        """Test edit on non-existent conversation."""
        result = service.apply_edit("nonexistent", "field", "value")

        assert result["success"] is False
        assert result["error"] == "CONVERSATION_NOT_FOUND"

    def test_edit_nonexistent_field(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
    ) -> None:
        """Test edit on non-existent field."""
        conv = conv_repo.create()
        conv_id = conv["id"]

        result = service.apply_edit(conv_id, "nonexistent", "value")

        assert result["success"] is False
        assert result["error"] == "FIELD_NOT_FOUND"

    def test_edit_readonly_field(
        self,
        service: IntegrationEditService,
        conv_repo: MockConversationRepository,
        field_repo: MockFieldRepository,
    ) -> None:
        """Test edit on read-only field."""
        conv = conv_repo.create()
        conv_id = conv["id"]
        field_repo.add_field(conv_id, "readonly", "Read Only", editable=False, value="Fixed")

        result = service.apply_edit(conv_id, "readonly", "New Value")

        assert result["success"] is False
        assert result["error"] == "FIELD_NOT_EDITABLE"
