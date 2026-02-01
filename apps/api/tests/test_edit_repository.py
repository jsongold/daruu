"""Tests for Edit Repository operations.

Tests the EditRepository protocol contract with mock implementations.
Validates save, get, undo, redo, and clear operations.
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
    """Mock implementation of EditRepository for testing.

    Follows immutable patterns - all operations return new objects.
    """

    def __init__(self) -> None:
        """Initialize with empty storage."""
        self._histories: dict[str, EditHistory] = {}
        self._field_states: dict[str, dict[str, FieldState]] = {}

    def save_edit(
        self,
        conversation_id: str,
        edit: FieldEdit,
    ) -> FieldEdit:
        """Save a new edit to the history."""
        history = self._histories.get(conversation_id)

        if history is None:
            history = EditHistory(conversation_id=conversation_id)

        # Clear redo stack (edits after current_index) and add new edit
        current_edits = list(history.edits[: history.current_index + 1])
        current_edits.append(edit)

        new_history = EditHistory(
            conversation_id=conversation_id,
            edits=current_edits,
            current_index=len(current_edits) - 1,
        )
        self._histories[conversation_id] = new_history

        # Update field state
        if conversation_id not in self._field_states:
            self._field_states[conversation_id] = {}

        new_state = FieldState(
            field_id=edit.field_id,
            current_value=edit.new_value,
            source="inline" if edit.old_value is None else "chat",
            last_modified=edit.timestamp,
        )
        self._field_states[conversation_id][edit.field_id] = new_state

        return edit

    def get_history(self, conversation_id: str) -> EditHistory:
        """Get the edit history for a conversation."""
        return self._histories.get(
            conversation_id,
            EditHistory(conversation_id=conversation_id),
        )

    def undo(self, conversation_id: str) -> list[FieldEdit] | None:
        """Undo the last edit."""
        history = self._histories.get(conversation_id)

        if history is None or not history.can_undo:
            return None

        # Get the edit to undo
        edit_to_undo = history.edits[history.current_index]

        # Update history with decremented index
        new_history = EditHistory(
            conversation_id=conversation_id,
            edits=history.edits,
            current_index=history.current_index - 1,
        )
        self._histories[conversation_id] = new_history

        # Update field state to old value
        if conversation_id in self._field_states:
            old_state = FieldState(
                field_id=edit_to_undo.field_id,
                current_value=edit_to_undo.old_value,
                source="default" if edit_to_undo.old_value is None else "inline",
                last_modified=datetime.now(timezone.utc),
            )
            self._field_states[conversation_id][edit_to_undo.field_id] = old_state

        return [edit_to_undo]

    def redo(self, conversation_id: str) -> list[FieldEdit] | None:
        """Redo the last undone edit."""
        history = self._histories.get(conversation_id)

        if history is None or not history.can_redo:
            return None

        # Get the edit to redo
        edit_to_redo = history.edits[history.current_index + 1]

        # Update history with incremented index
        new_history = EditHistory(
            conversation_id=conversation_id,
            edits=history.edits,
            current_index=history.current_index + 1,
        )
        self._histories[conversation_id] = new_history

        # Update field state to new value
        if conversation_id in self._field_states:
            new_state = FieldState(
                field_id=edit_to_redo.field_id,
                current_value=edit_to_redo.new_value,
                source="inline",
                last_modified=datetime.now(timezone.utc),
            )
            self._field_states[conversation_id][edit_to_redo.field_id] = new_state

        return [edit_to_redo]

    def clear_history(self, conversation_id: str) -> None:
        """Clear all edit history for a conversation."""
        if conversation_id in self._histories:
            del self._histories[conversation_id]
        if conversation_id in self._field_states:
            del self._field_states[conversation_id]

    def get_field_value(
        self,
        conversation_id: str,
        field_id: str,
    ) -> FieldState | None:
        """Get the current value of a specific field."""
        conv_states = self._field_states.get(conversation_id, {})
        return conv_states.get(field_id)

    def get_all_field_values(
        self,
        conversation_id: str,
    ) -> list[FieldState]:
        """Get all current field values for a conversation."""
        conv_states = self._field_states.get(conversation_id, {})
        return list(conv_states.values())

    def set_field_value(
        self,
        conversation_id: str,
        field_state: FieldState,
    ) -> FieldState:
        """Set or update a field value."""
        if conversation_id not in self._field_states:
            self._field_states[conversation_id] = {}
        self._field_states[conversation_id][field_state.field_id] = field_state
        return field_state


@pytest.fixture
def edit_repo() -> MockEditRepository:
    """Create a fresh mock edit repository."""
    return MockEditRepository()


class TestSaveEdit:
    """Tests for save_edit operation."""

    def test_save_edit_creates_record(self, edit_repo: MockEditRepository) -> None:
        """Test that save_edit creates a new edit record."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-123",
            old_value=None,
            new_value="John Doe",
            timestamp=now,
        )

        result = edit_repo.save_edit("conv-001", edit)

        assert result.field_id == "field-123"
        assert result.new_value == "John Doe"

        history = edit_repo.get_history("conv-001")
        assert len(history.edits) == 1
        assert history.current_index == 0

    def test_save_multiple_edits(self, edit_repo: MockEditRepository) -> None:
        """Test saving multiple edits to the same conversation."""
        now = datetime.now(timezone.utc)

        edit1 = FieldEdit(
            field_id="field-1",
            new_value="Value 1",
            timestamp=now,
        )
        edit2 = FieldEdit(
            field_id="field-2",
            new_value="Value 2",
            timestamp=now,
        )

        edit_repo.save_edit("conv-001", edit1)
        edit_repo.save_edit("conv-001", edit2)

        history = edit_repo.get_history("conv-001")
        assert len(history.edits) == 2
        assert history.current_index == 1

    def test_save_edit_updates_field_state(self, edit_repo: MockEditRepository) -> None:
        """Test that save_edit updates the field state."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="name",
            old_value="Old Name",
            new_value="New Name",
            timestamp=now,
        )

        edit_repo.save_edit("conv-001", edit)

        state = edit_repo.get_field_value("conv-001", "name")
        assert state is not None
        assert state.current_value == "New Name"


class TestGetHistory:
    """Tests for get_history operation."""

    def test_get_history_returns_all_edits(self, edit_repo: MockEditRepository) -> None:
        """Test that get_history returns all edits."""
        now = datetime.now(timezone.utc)

        for i in range(5):
            edit = FieldEdit(
                field_id=f"field-{i}",
                new_value=f"value-{i}",
                timestamp=now,
            )
            edit_repo.save_edit("conv-001", edit)

        history = edit_repo.get_history("conv-001")
        assert len(history.edits) == 5
        assert history.current_index == 4

    def test_get_history_empty_returns_default(self, edit_repo: MockEditRepository) -> None:
        """Test that non-existent conversation returns empty history."""
        history = edit_repo.get_history("non-existent")
        assert history.conversation_id == "non-existent"
        assert len(history.edits) == 0
        assert history.current_index == -1


class TestUndo:
    """Tests for undo operation."""

    def test_undo_moves_index_back(self, edit_repo: MockEditRepository) -> None:
        """Test that undo decrements the current index."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-1",
            old_value="original",
            new_value="edited",
            timestamp=now,
        )
        edit_repo.save_edit("conv-001", edit)

        # Should be at index 0
        history_before = edit_repo.get_history("conv-001")
        assert history_before.current_index == 0

        # Undo
        result = edit_repo.undo("conv-001")
        assert result is not None
        assert len(result) == 1
        assert result[0].field_id == "field-1"

        # Should be at index -1
        history_after = edit_repo.get_history("conv-001")
        assert history_after.current_index == -1

    def test_undo_returns_reverted_edits(self, edit_repo: MockEditRepository) -> None:
        """Test that undo returns the edit that was undone."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="name",
            old_value="John",
            new_value="Jane",
            timestamp=now,
        )
        edit_repo.save_edit("conv-001", edit)

        result = edit_repo.undo("conv-001")

        assert result is not None
        assert result[0].old_value == "John"
        assert result[0].new_value == "Jane"

    def test_undo_at_start_returns_none(self, edit_repo: MockEditRepository) -> None:
        """Test that undo returns None when at start of history."""
        result = edit_repo.undo("conv-001")
        assert result is None

    def test_undo_updates_field_state(self, edit_repo: MockEditRepository) -> None:
        """Test that undo reverts field state to old value."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="name",
            old_value="John",
            new_value="Jane",
            timestamp=now,
        )
        edit_repo.save_edit("conv-001", edit)

        edit_repo.undo("conv-001")

        state = edit_repo.get_field_value("conv-001", "name")
        assert state is not None
        assert state.current_value == "John"

    def test_multiple_undos(self, edit_repo: MockEditRepository) -> None:
        """Test multiple consecutive undos."""
        now = datetime.now(timezone.utc)

        for i in range(3):
            edit = FieldEdit(
                field_id="field",
                old_value=f"v{i}" if i > 0 else None,
                new_value=f"v{i + 1}",
                timestamp=now,
            )
            edit_repo.save_edit("conv-001", edit)

        # Undo all 3
        for i in range(3):
            result = edit_repo.undo("conv-001")
            assert result is not None

        # Fourth undo should fail
        result = edit_repo.undo("conv-001")
        assert result is None


class TestRedo:
    """Tests for redo operation."""

    def test_redo_moves_index_forward(self, edit_repo: MockEditRepository) -> None:
        """Test that redo increments the current index."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-1",
            old_value="original",
            new_value="edited",
            timestamp=now,
        )
        edit_repo.save_edit("conv-001", edit)
        edit_repo.undo("conv-001")

        # Should be at index -1
        history_before = edit_repo.get_history("conv-001")
        assert history_before.current_index == -1

        # Redo
        result = edit_repo.redo("conv-001")
        assert result is not None
        assert len(result) == 1

        # Should be at index 0
        history_after = edit_repo.get_history("conv-001")
        assert history_after.current_index == 0

    def test_redo_at_end_returns_none(self, edit_repo: MockEditRepository) -> None:
        """Test that redo returns None when at end of history."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-1",
            new_value="value",
            timestamp=now,
        )
        edit_repo.save_edit("conv-001", edit)

        # Already at the end, should fail
        result = edit_repo.redo("conv-001")
        assert result is None

    def test_redo_empty_history_returns_none(self, edit_repo: MockEditRepository) -> None:
        """Test that redo returns None on empty history."""
        result = edit_repo.redo("conv-001")
        assert result is None

    def test_redo_updates_field_state(self, edit_repo: MockEditRepository) -> None:
        """Test that redo re-applies the field value."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="name",
            old_value="John",
            new_value="Jane",
            timestamp=now,
        )
        edit_repo.save_edit("conv-001", edit)
        edit_repo.undo("conv-001")

        # Verify undo worked
        state = edit_repo.get_field_value("conv-001", "name")
        assert state.current_value == "John"

        # Redo
        edit_repo.redo("conv-001")

        state = edit_repo.get_field_value("conv-001", "name")
        assert state.current_value == "Jane"


class TestClearHistory:
    """Tests for clear_history operation."""

    def test_clear_history_removes_all(self, edit_repo: MockEditRepository) -> None:
        """Test that clear_history removes all edits."""
        now = datetime.now(timezone.utc)

        for i in range(5):
            edit = FieldEdit(
                field_id=f"field-{i}",
                new_value=f"value-{i}",
                timestamp=now,
            )
            edit_repo.save_edit("conv-001", edit)

        edit_repo.clear_history("conv-001")

        history = edit_repo.get_history("conv-001")
        assert len(history.edits) == 0
        assert history.current_index == -1

    def test_clear_history_removes_field_states(self, edit_repo: MockEditRepository) -> None:
        """Test that clear_history also removes field states."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="field-1",
            new_value="value",
            timestamp=now,
        )
        edit_repo.save_edit("conv-001", edit)

        edit_repo.clear_history("conv-001")

        states = edit_repo.get_all_field_values("conv-001")
        assert len(states) == 0

    def test_clear_history_nonexistent_conversation(self, edit_repo: MockEditRepository) -> None:
        """Test that clearing non-existent conversation doesn't error."""
        # Should not raise
        edit_repo.clear_history("non-existent")


class TestFieldValueOperations:
    """Tests for field value get/set operations."""

    def test_get_field_value_returns_state(self, edit_repo: MockEditRepository) -> None:
        """Test getting a specific field's value."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(
            field_id="name",
            new_value="John Doe",
            timestamp=now,
        )
        edit_repo.save_edit("conv-001", edit)

        state = edit_repo.get_field_value("conv-001", "name")
        assert state is not None
        assert state.field_id == "name"
        assert state.current_value == "John Doe"

    def test_get_field_value_nonexistent_returns_none(self, edit_repo: MockEditRepository) -> None:
        """Test getting non-existent field returns None."""
        state = edit_repo.get_field_value("conv-001", "non-existent")
        assert state is None

    def test_get_all_field_values(self, edit_repo: MockEditRepository) -> None:
        """Test getting all field values for a conversation."""
        now = datetime.now(timezone.utc)

        for i in range(3):
            edit = FieldEdit(
                field_id=f"field-{i}",
                new_value=f"value-{i}",
                timestamp=now,
            )
            edit_repo.save_edit("conv-001", edit)

        states = edit_repo.get_all_field_values("conv-001")
        assert len(states) == 3

    def test_set_field_value_directly(self, edit_repo: MockEditRepository) -> None:
        """Test setting field value without going through edit history."""
        now = datetime.now(timezone.utc)
        state = FieldState(
            field_id="direct-field",
            current_value="Direct Value",
            source="extracted",
            last_modified=now,
        )

        result = edit_repo.set_field_value("conv-001", state)

        assert result.current_value == "Direct Value"

        fetched = edit_repo.get_field_value("conv-001", "direct-field")
        assert fetched is not None
        assert fetched.current_value == "Direct Value"


class TestNewEditClearsRedoStack:
    """Tests for new edit clearing redo stack behavior."""

    def test_new_edit_clears_redo_stack(self, edit_repo: MockEditRepository) -> None:
        """Test that new edit after undo clears the redo stack."""
        now = datetime.now(timezone.utc)

        # Add two edits
        edit1 = FieldEdit(field_id="f1", new_value="v1", timestamp=now)
        edit2 = FieldEdit(field_id="f2", new_value="v2", timestamp=now)
        edit_repo.save_edit("conv-001", edit1)
        edit_repo.save_edit("conv-001", edit2)

        # Undo one
        edit_repo.undo("conv-001")

        history_mid = edit_repo.get_history("conv-001")
        assert history_mid.current_index == 0
        assert len(history_mid.edits) == 2  # Still has both

        # Add new edit - should clear redo stack
        edit3 = FieldEdit(field_id="f3", new_value="v3", timestamp=now)
        edit_repo.save_edit("conv-001", edit3)

        history_after = edit_repo.get_history("conv-001")
        # Should only have edit1 and edit3
        assert len(history_after.edits) == 2
        assert history_after.current_index == 1
        assert history_after.edits[0].field_id == "f1"
        assert history_after.edits[1].field_id == "f3"

    def test_redo_not_available_after_new_edit(self, edit_repo: MockEditRepository) -> None:
        """Test that redo is not available after new edit."""
        now = datetime.now(timezone.utc)

        edit1 = FieldEdit(field_id="f1", new_value="v1", timestamp=now)
        edit_repo.save_edit("conv-001", edit1)
        edit_repo.undo("conv-001")

        history_after_undo = edit_repo.get_history("conv-001")
        assert history_after_undo.can_redo is True

        # Add new edit
        edit2 = FieldEdit(field_id="f2", new_value="v2", timestamp=now)
        edit_repo.save_edit("conv-001", edit2)

        history_after_new_edit = edit_repo.get_history("conv-001")
        assert history_after_new_edit.can_redo is False


class TestEditSameFieldMultipleTimes:
    """Tests for editing the same field multiple times."""

    def test_edit_same_field_multiple_times(self, edit_repo: MockEditRepository) -> None:
        """Test editing the same field creates separate history entries."""
        now = datetime.now(timezone.utc)

        values = ["First", "Second", "Third"]
        for i, value in enumerate(values):
            edit = FieldEdit(
                field_id="name",
                old_value=values[i - 1] if i > 0 else None,
                new_value=value,
                timestamp=now,
            )
            edit_repo.save_edit("conv-001", edit)

        history = edit_repo.get_history("conv-001")
        assert len(history.edits) == 3

        state = edit_repo.get_field_value("conv-001", "name")
        assert state.current_value == "Third"

    def test_undo_same_field_edits(self, edit_repo: MockEditRepository) -> None:
        """Test undoing multiple edits to the same field."""
        now = datetime.now(timezone.utc)

        # Three edits to same field
        for i, value in enumerate(["A", "B", "C"]):
            edit = FieldEdit(
                field_id="letter",
                old_value=["", "A", "B"][i] if i > 0 else None,
                new_value=value,
                timestamp=now,
            )
            edit_repo.save_edit("conv-001", edit)

        # Undo all three
        edit_repo.undo("conv-001")  # C -> B
        state = edit_repo.get_field_value("conv-001", "letter")
        assert state.current_value == "B"

        edit_repo.undo("conv-001")  # B -> A
        state = edit_repo.get_field_value("conv-001", "letter")
        assert state.current_value == "A"

        edit_repo.undo("conv-001")  # A -> None
        state = edit_repo.get_field_value("conv-001", "letter")
        assert state.current_value is None


class TestCanUndoCanRedo:
    """Tests for can_undo and can_redo properties."""

    def test_can_undo_can_redo_initial_state(self, edit_repo: MockEditRepository) -> None:
        """Test can_undo/can_redo on empty history."""
        history = edit_repo.get_history("conv-001")
        assert history.can_undo is False
        assert history.can_redo is False

    def test_can_undo_after_one_edit(self, edit_repo: MockEditRepository) -> None:
        """Test can_undo is True after one edit."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(field_id="f1", new_value="v1", timestamp=now)
        edit_repo.save_edit("conv-001", edit)

        history = edit_repo.get_history("conv-001")
        assert history.can_undo is True
        assert history.can_redo is False

    def test_can_redo_after_undo(self, edit_repo: MockEditRepository) -> None:
        """Test can_redo is True after undo."""
        now = datetime.now(timezone.utc)
        edit = FieldEdit(field_id="f1", new_value="v1", timestamp=now)
        edit_repo.save_edit("conv-001", edit)
        edit_repo.undo("conv-001")

        history = edit_repo.get_history("conv-001")
        assert history.can_undo is False
        assert history.can_redo is True

    def test_can_undo_and_redo_in_middle(self, edit_repo: MockEditRepository) -> None:
        """Test both available when in middle of history."""
        now = datetime.now(timezone.utc)

        edit1 = FieldEdit(field_id="f1", new_value="v1", timestamp=now)
        edit2 = FieldEdit(field_id="f2", new_value="v2", timestamp=now)
        edit_repo.save_edit("conv-001", edit1)
        edit_repo.save_edit("conv-001", edit2)
        edit_repo.undo("conv-001")

        history = edit_repo.get_history("conv-001")
        assert history.can_undo is True
        assert history.can_redo is True
