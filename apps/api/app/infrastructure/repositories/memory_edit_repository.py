"""In-memory implementation of EditRepository.

This is an in-memory adapter for the EditRepository port.
Suitable for MVP development and testing. In production, swap for
a database-backed implementation (e.g., SupabaseEditRepository).

The implementation uses a stack-based approach for undo/redo:
- edits: list of all edits ever made
- current_index: pointer to the last applied edit
- Undo: decrement current_index
- Redo: increment current_index
- New edit after undo: truncate redo stack and append

Thread-safety note: This implementation is safe for single-process use.
For multi-process deployments, use a database-backed implementation.
"""

from datetime import datetime, timezone

from app.models.edit import EditHistory, FieldEdit, FieldState
from app.repositories import EditRepository


class MemoryEditRepository:
    """In-memory implementation of EditRepository.

    Stores edit histories and field values in dictionaries.
    Uses immutable patterns for all update operations.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        # Edit histories keyed by conversation_id
        self._histories: dict[str, EditHistory] = {}
        # Field values keyed by conversation_id -> field_id
        self._field_values: dict[str, dict[str, FieldState]] = {}

    def _ensure_history(self, conversation_id: str) -> EditHistory:
        """Ensure a history exists for the conversation."""
        if conversation_id not in self._histories:
            self._histories[conversation_id] = EditHistory(
                conversation_id=conversation_id,
                edits=[],
                current_index=-1,
            )
        return self._histories[conversation_id]

    def save_edit(
        self,
        conversation_id: str,
        edit: FieldEdit,
    ) -> FieldEdit:
        """Save a new edit to the history.

        If the current_index is not at the end (after undo operations),
        the redo stack is discarded.
        """
        history = self._ensure_history(conversation_id)

        # If we're not at the end of the history, truncate the redo stack
        # by keeping only edits up to current_index
        if history.current_index < len(history.edits) - 1:
            kept_edits = list(history.edits[: history.current_index + 1])
        else:
            kept_edits = list(history.edits)

        # Append the new edit
        new_edits = [*kept_edits, edit]
        new_index = len(new_edits) - 1

        # Create new history (immutable pattern)
        new_history = EditHistory(
            conversation_id=conversation_id,
            edits=new_edits,
            current_index=new_index,
        )
        self._histories[conversation_id] = new_history

        # Update field value
        self._update_field_value(conversation_id, edit, is_apply=True)

        return edit

    def get_history(self, conversation_id: str) -> EditHistory:
        """Get the edit history for a conversation."""
        return self._ensure_history(conversation_id)

    def undo(self, conversation_id: str) -> list[FieldEdit] | None:
        """Undo the last edit in the conversation."""
        history = self._ensure_history(conversation_id)

        if not history.can_undo:
            return None

        # Get the edit to undo
        edit_to_undo = history.edits[history.current_index]

        # Decrement current_index (immutable pattern)
        new_history = EditHistory(
            conversation_id=conversation_id,
            edits=history.edits,
            current_index=history.current_index - 1,
        )
        self._histories[conversation_id] = new_history

        # Revert field value
        self._update_field_value(conversation_id, edit_to_undo, is_apply=False)

        return [edit_to_undo]

    def redo(self, conversation_id: str) -> list[FieldEdit] | None:
        """Redo previously undone edit."""
        history = self._ensure_history(conversation_id)

        if not history.can_redo:
            return None

        # Get the edit to redo (next one after current)
        edit_to_redo = history.edits[history.current_index + 1]

        # Increment current_index (immutable pattern)
        new_history = EditHistory(
            conversation_id=conversation_id,
            edits=history.edits,
            current_index=history.current_index + 1,
        )
        self._histories[conversation_id] = new_history

        # Apply field value
        self._update_field_value(conversation_id, edit_to_redo, is_apply=True)

        return [edit_to_redo]

    def clear_history(self, conversation_id: str) -> None:
        """Clear all edit history for a conversation."""
        if conversation_id in self._histories:
            del self._histories[conversation_id]
        if conversation_id in self._field_values:
            del self._field_values[conversation_id]

    def get_field_value(
        self,
        conversation_id: str,
        field_id: str,
    ) -> FieldState | None:
        """Get the current value of a specific field."""
        conv_fields = self._field_values.get(conversation_id, {})
        return conv_fields.get(field_id)

    def get_all_field_values(
        self,
        conversation_id: str,
    ) -> list[FieldState]:
        """Get all current field values for a conversation."""
        conv_fields = self._field_values.get(conversation_id, {})
        return list(conv_fields.values())

    def set_field_value(
        self,
        conversation_id: str,
        field_state: FieldState,
    ) -> FieldState:
        """Set or update a field value."""
        if conversation_id not in self._field_values:
            self._field_values[conversation_id] = {}

        self._field_values[conversation_id][field_state.field_id] = field_state
        return field_state

    def _update_field_value(
        self,
        conversation_id: str,
        edit: FieldEdit,
        is_apply: bool,
    ) -> None:
        """Update field value based on edit.

        Args:
            conversation_id: The conversation ID.
            edit: The edit to apply or revert.
            is_apply: True to apply new_value, False to revert to old_value.
        """
        if conversation_id not in self._field_values:
            self._field_values[conversation_id] = {}

        now = datetime.now(timezone.utc)
        value = edit.new_value if is_apply else edit.old_value

        new_state = FieldState(
            field_id=edit.field_id,
            current_value=value,
            source="chat",  # Could be enhanced to track source from edit
            last_modified=now,
        )

        self._field_values[conversation_id][edit.field_id] = new_state


# Ensure it satisfies the protocol
_assert_edit_repo: EditRepository = MemoryEditRepository()
