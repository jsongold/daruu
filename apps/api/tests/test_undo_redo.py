"""Tests for Undo/Redo stack edge cases.

Tests edge cases and complex scenarios for the undo/redo system:
- Empty history behavior
- Redo without undo
- New edit clears redo stack
- Max history limit (if implemented)
- Concurrent edits (simulated)
- Multiple edits to same field
Phase 3: Edit & Adjust feature.
"""

from datetime import datetime, timedelta, timezone

import pytest
from app.models.edit import FieldEdit


class UndoRedoStack:
    """Minimal undo/redo stack implementation for testing.

    Demonstrates the undo/redo algorithm:
    - current_index points to the last applied edit
    - Undo decrements index, reverts that edit
    - Redo increments index, re-applies that edit
    - New edits clear everything after current_index
    """

    def __init__(self, max_size: int = 100) -> None:
        self._edits: list[FieldEdit] = []
        self._current_index: int = -1
        self._max_size: int = max_size

    @property
    def can_undo(self) -> bool:
        return self._current_index >= 0

    @property
    def can_redo(self) -> bool:
        return self._current_index < len(self._edits) - 1

    @property
    def undo_count(self) -> int:
        return self._current_index + 1

    @property
    def redo_count(self) -> int:
        return len(self._edits) - self._current_index - 1

    @property
    def size(self) -> int:
        return len(self._edits)

    def push(self, edit: FieldEdit) -> None:
        """Add a new edit, clearing redo stack."""
        # Clear redo stack
        self._edits = self._edits[: self._current_index + 1]

        # Enforce max size
        if len(self._edits) >= self._max_size:
            self._edits.pop(0)
            self._current_index -= 1

        self._edits.append(edit)
        self._current_index = len(self._edits) - 1

    def undo(self) -> FieldEdit | None:
        """Undo the last edit."""
        if not self.can_undo:
            return None

        edit = self._edits[self._current_index]
        self._current_index -= 1
        return edit

    def redo(self) -> FieldEdit | None:
        """Redo the last undone edit."""
        if not self.can_redo:
            return None

        self._current_index += 1
        return self._edits[self._current_index]

    def clear(self) -> None:
        """Clear all history."""
        self._edits = []
        self._current_index = -1

    def get_edit(self, index: int) -> FieldEdit | None:
        """Get edit at specific index."""
        if 0 <= index < len(self._edits):
            return self._edits[index]
        return None


@pytest.fixture
def stack() -> UndoRedoStack:
    """Create a fresh undo/redo stack."""
    return UndoRedoStack()


@pytest.fixture
def small_stack() -> UndoRedoStack:
    """Create a stack with small max size for limit testing."""
    return UndoRedoStack(max_size=5)


def make_edit(field_id: str, old_value: str | None, new_value: str) -> FieldEdit:
    """Helper to create FieldEdit objects."""
    return FieldEdit(
        field_id=field_id,
        old_value=old_value,
        new_value=new_value,
        timestamp=datetime.now(timezone.utc),
    )


class TestUndoEmptyHistory:
    """Tests for undo on empty history."""

    def test_undo_empty_returns_none(self, stack: UndoRedoStack) -> None:
        """Test that undo on empty stack returns None."""
        result = stack.undo()
        assert result is None

    def test_undo_empty_can_undo_false(self, stack: UndoRedoStack) -> None:
        """Test that can_undo is False on empty stack."""
        assert stack.can_undo is False

    def test_multiple_undo_empty(self, stack: UndoRedoStack) -> None:
        """Test multiple undos on empty stack all return None."""
        for _ in range(5):
            assert stack.undo() is None

    def test_undo_count_empty(self, stack: UndoRedoStack) -> None:
        """Test undo_count is 0 on empty stack."""
        assert stack.undo_count == 0


class TestRedoWithoutUndo:
    """Tests for redo when nothing has been undone."""

    def test_redo_empty_returns_none(self, stack: UndoRedoStack) -> None:
        """Test redo on empty stack returns None."""
        result = stack.redo()
        assert result is None

    def test_redo_after_push_returns_none(self, stack: UndoRedoStack) -> None:
        """Test redo right after push returns None (nothing to redo)."""
        stack.push(make_edit("field", None, "value"))
        result = stack.redo()
        assert result is None

    def test_can_redo_false_without_undo(self, stack: UndoRedoStack) -> None:
        """Test can_redo is False when nothing undone."""
        stack.push(make_edit("field", None, "value"))
        assert stack.can_redo is False

    def test_redo_count_zero_without_undo(self, stack: UndoRedoStack) -> None:
        """Test redo_count is 0 when nothing undone."""
        stack.push(make_edit("field", None, "value"))
        assert stack.redo_count == 0


class TestNewEditClearsRedoStack:
    """Tests for new edit clearing the redo stack."""

    def test_new_edit_after_undo_clears_redo(self, stack: UndoRedoStack) -> None:
        """Test that new edit after undo clears redo stack."""
        stack.push(make_edit("f", None, "v1"))
        stack.push(make_edit("f", "v1", "v2"))

        stack.undo()  # Back to v1
        assert stack.can_redo is True

        stack.push(make_edit("f", "v1", "v3"))  # New path
        assert stack.can_redo is False

    def test_new_edit_removes_future_edits(self, stack: UndoRedoStack) -> None:
        """Test that new edit removes edits that were after current position."""
        stack.push(make_edit("f", None, "v1"))
        stack.push(make_edit("f", "v1", "v2"))
        stack.push(make_edit("f", "v2", "v3"))

        stack.undo()  # v3 -> v2
        stack.undo()  # v2 -> v1

        # Add new edit from v1
        stack.push(make_edit("f", "v1", "v4"))

        # Only 2 edits should remain: v1 and v4
        assert stack.size == 2
        assert stack.get_edit(0).new_value == "v1"
        assert stack.get_edit(1).new_value == "v4"

    def test_cannot_redo_to_original_after_new_edit(self, stack: UndoRedoStack) -> None:
        """Test cannot redo to original path after diverging."""
        stack.push(make_edit("f", None, "original_v1"))
        stack.push(make_edit("f", "original_v1", "original_v2"))

        stack.undo()

        # Diverge
        stack.push(make_edit("f", "original_v1", "new_path"))

        # Try to redo - should fail
        result = stack.redo()
        assert result is None


class TestMaxHistoryLimit:
    """Tests for maximum history limit enforcement."""

    def test_exceeding_max_removes_oldest(self, small_stack: UndoRedoStack) -> None:
        """Test that exceeding max size removes oldest edit."""
        # Stack has max_size=5
        for i in range(7):
            small_stack.push(make_edit("f", f"v{i}" if i > 0 else None, f"v{i + 1}"))

        # Should only have 5 edits
        assert small_stack.size == 5

        # Oldest should be v3->v4 (not v1->v2)
        oldest = small_stack.get_edit(0)
        assert oldest.old_value == "v2"
        assert oldest.new_value == "v3"

    def test_max_limit_maintains_undo_redo_integrity(self, small_stack: UndoRedoStack) -> None:
        """Test that history limit doesn't break undo/redo."""
        for i in range(10):
            small_stack.push(make_edit("f", f"v{i}" if i > 0 else None, f"v{i + 1}"))

        # Should still be able to undo 5 times
        for _ in range(5):
            assert small_stack.undo() is not None

        # Should not be able to undo anymore
        assert small_stack.undo() is None

    def test_max_limit_with_undo_redo_cycle(self, small_stack: UndoRedoStack) -> None:
        """Test max limit with undo/redo operations mixed in."""
        # Fill to limit
        for i in range(5):
            small_stack.push(make_edit("f", f"v{i}" if i > 0 else None, f"v{i + 1}"))

        assert small_stack.size == 5

        # Undo 2
        small_stack.undo()
        small_stack.undo()

        # Add 3 new (should clear redo and add, potentially removing old)
        for i in range(5, 8):
            small_stack.push(make_edit("f", f"v{i}", f"v{i + 1}"))

        # Check we're still at or under limit
        assert small_stack.size <= 5


class TestConcurrentEdits:
    """Tests for concurrent edit scenarios (simulated with timestamps)."""

    def test_edits_maintain_order(self, stack: UndoRedoStack) -> None:
        """Test that edits are stored in chronological order."""
        now = datetime.now(timezone.utc)

        edits = [
            FieldEdit(field_id="f", old_value=None, new_value="v1", timestamp=now),
            FieldEdit(
                field_id="f", old_value="v1", new_value="v2", timestamp=now + timedelta(seconds=1)
            ),
            FieldEdit(
                field_id="f", old_value="v2", new_value="v3", timestamp=now + timedelta(seconds=2)
            ),
        ]

        for edit in edits:
            stack.push(edit)

        # Verify order
        for i, edit in enumerate(edits):
            assert stack.get_edit(i).timestamp == edit.timestamp

    def test_rapid_edits_all_recorded(self, stack: UndoRedoStack) -> None:
        """Test that rapid successive edits are all recorded."""
        now = datetime.now(timezone.utc)

        for i in range(10):
            edit = FieldEdit(
                field_id="field",
                old_value=f"v{i}" if i > 0 else None,
                new_value=f"v{i + 1}",
                timestamp=now + timedelta(milliseconds=i),
            )
            stack.push(edit)

        assert stack.size == 10

    def test_interleaved_field_edits(self, stack: UndoRedoStack) -> None:
        """Test edits to different fields interleaved."""
        stack.push(make_edit("field_a", None, "a1"))
        stack.push(make_edit("field_b", None, "b1"))
        stack.push(make_edit("field_a", "a1", "a2"))
        stack.push(make_edit("field_b", "b1", "b2"))

        # Undo should work in reverse order regardless of field
        e1 = stack.undo()
        assert e1.field_id == "field_b" and e1.new_value == "b2"

        e2 = stack.undo()
        assert e2.field_id == "field_a" and e2.new_value == "a2"


class TestEditSameFieldMultipleTimes:
    """Tests for editing the same field repeatedly."""

    def test_multiple_edits_same_field_all_recorded(self, stack: UndoRedoStack) -> None:
        """Test that multiple edits to same field are all recorded."""
        values = ["First", "Second", "Third", "Fourth", "Fifth"]

        for i, value in enumerate(values):
            old = values[i - 1] if i > 0 else None
            stack.push(make_edit("name", old, value))

        assert stack.size == 5

    def test_undo_through_same_field_edits(self, stack: UndoRedoStack) -> None:
        """Test undoing through multiple edits to same field."""
        stack.push(make_edit("name", None, "A"))
        stack.push(make_edit("name", "A", "B"))
        stack.push(make_edit("name", "B", "C"))

        # Undo to each previous value
        e1 = stack.undo()
        assert e1.old_value == "B"  # Was C, reverted to B

        e2 = stack.undo()
        assert e2.old_value == "A"  # Was B, reverted to A

        e3 = stack.undo()
        assert e3.old_value is None  # Was A, reverted to None

    def test_redo_through_same_field_edits(self, stack: UndoRedoStack) -> None:
        """Test redoing through multiple edits to same field."""
        stack.push(make_edit("name", None, "A"))
        stack.push(make_edit("name", "A", "B"))
        stack.push(make_edit("name", "B", "C"))

        # Undo all
        stack.undo()
        stack.undo()
        stack.undo()

        # Redo each
        e1 = stack.redo()
        assert e1.new_value == "A"

        e2 = stack.redo()
        assert e2.new_value == "B"

        e3 = stack.redo()
        assert e3.new_value == "C"


class TestComplexUndoRedoSequences:
    """Tests for complex undo/redo sequences."""

    def test_alternating_undo_redo(self, stack: UndoRedoStack) -> None:
        """Test alternating undo and redo operations."""
        stack.push(make_edit("f", None, "v1"))
        stack.push(make_edit("f", "v1", "v2"))
        stack.push(make_edit("f", "v2", "v3"))

        # Alternating pattern
        stack.undo()  # v3 -> v2
        stack.redo()  # v2 -> v3
        stack.undo()  # v3 -> v2
        stack.undo()  # v2 -> v1
        stack.redo()  # v1 -> v2

        assert stack.undo_count == 2
        assert stack.redo_count == 1

    def test_undo_all_then_redo_all(self, stack: UndoRedoStack) -> None:
        """Test undoing everything then redoing everything."""
        for i in range(5):
            stack.push(make_edit("f", f"v{i}" if i > 0 else None, f"v{i + 1}"))

        # Undo all
        while stack.can_undo:
            stack.undo()

        assert stack.undo_count == 0
        assert stack.redo_count == 5

        # Redo all
        while stack.can_redo:
            stack.redo()

        assert stack.undo_count == 5
        assert stack.redo_count == 0

    def test_partial_undo_then_new_edit(self, stack: UndoRedoStack) -> None:
        """Test partial undo followed by new edit."""
        stack.push(make_edit("f", None, "v1"))
        stack.push(make_edit("f", "v1", "v2"))
        stack.push(make_edit("f", "v2", "v3"))
        stack.push(make_edit("f", "v3", "v4"))

        # Undo 2
        stack.undo()
        stack.undo()

        # At v2, add new path
        stack.push(make_edit("f", "v2", "v5"))

        # Should have v1, v2, v5
        assert stack.size == 3
        assert stack.get_edit(2).new_value == "v5"


class TestClearHistory:
    """Tests for clearing history."""

    def test_clear_empties_stack(self, stack: UndoRedoStack) -> None:
        """Test that clear removes all edits."""
        for i in range(5):
            stack.push(make_edit("f", f"v{i}" if i > 0 else None, f"v{i + 1}"))

        stack.clear()

        assert stack.size == 0
        assert stack.can_undo is False
        assert stack.can_redo is False

    def test_clear_resets_index(self, stack: UndoRedoStack) -> None:
        """Test that clear resets current index."""
        stack.push(make_edit("f", None, "v1"))
        stack.clear()

        assert stack.undo_count == 0
        assert stack.redo_count == 0

    def test_operations_after_clear(self, stack: UndoRedoStack) -> None:
        """Test that stack works normally after clear."""
        stack.push(make_edit("f", None, "old"))
        stack.clear()

        stack.push(make_edit("f", None, "new"))
        assert stack.size == 1
        assert stack.can_undo is True

        result = stack.undo()
        assert result.new_value == "new"
