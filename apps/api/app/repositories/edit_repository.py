"""Edit repository interface (Port).

This defines the contract for edit history persistence operations.
Implementations can be in-memory, database, or any other storage.
The repository manages both the edit history (for undo/redo) and
the current field values.
"""

from typing import Protocol

from app.models.edit import EditHistory, FieldEdit, FieldState


class EditRepository(Protocol):
    """Repository interface for edit operations.

    This protocol defines the contract that any edit storage
    implementation must satisfy. All update operations follow
    immutable patterns - they return new objects rather than
    mutating existing ones.

    The repository maintains:
    1. Edit history per conversation (for undo/redo)
    2. Current field values per conversation

    Example:
        class SupabaseEditRepository:
            def save_edit(self, ...) -> FieldEdit: ...
            def get_history(self, conversation_id: str) -> EditHistory: ...
            # etc.

        # Inject into service
        service = EditService(edit_repo=SupabaseEditRepository())
    """

    def save_edit(
        self,
        conversation_id: str,
        edit: FieldEdit,
    ) -> FieldEdit:
        """Save a new edit to the history.

        This appends the edit to the history and updates the current_index.
        If called after undo operations, any redo stack is discarded.

        Args:
            conversation_id: ID of the conversation.
            edit: The edit to save.

        Returns:
            The saved FieldEdit (may have generated ID added).
        """
        ...

    def get_history(self, conversation_id: str) -> EditHistory:
        """Get the edit history for a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            EditHistory for the conversation (empty if none exists).
        """
        ...

    def undo(self, conversation_id: str) -> list[FieldEdit] | None:
        """Undo the last edit(s) in the conversation.

        Moves current_index back by one and returns the edit(s)
        that were undone so their old_values can be restored.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            List of edits that were undone, or None if nothing to undo.
        """
        ...

    def redo(self, conversation_id: str) -> list[FieldEdit] | None:
        """Redo previously undone edit(s).

        Moves current_index forward by one and returns the edit(s)
        that were redone so their new_values can be applied.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            List of edits that were redone, or None if nothing to redo.
        """
        ...

    def clear_history(self, conversation_id: str) -> None:
        """Clear all edit history for a conversation.

        Used when a conversation is deleted or reset.

        Args:
            conversation_id: ID of the conversation.
        """
        ...

    # Field value operations

    def get_field_value(
        self,
        conversation_id: str,
        field_id: str,
    ) -> FieldState | None:
        """Get the current value of a specific field.

        Args:
            conversation_id: ID of the conversation.
            field_id: ID of the field.

        Returns:
            FieldState if field has a value, None otherwise.
        """
        ...

    def get_all_field_values(
        self,
        conversation_id: str,
    ) -> list[FieldState]:
        """Get all current field values for a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            List of all field states (may be empty).
        """
        ...

    def set_field_value(
        self,
        conversation_id: str,
        field_state: FieldState,
    ) -> FieldState:
        """Set or update a field value.

        This updates the current value without adding to history.
        Used internally when applying/reverting edits.

        Args:
            conversation_id: ID of the conversation.
            field_state: The field state to set.

        Returns:
            The saved FieldState.
        """
        ...
