"""Edit service for Agent Chat UI.

This service provides business logic for field editing operations,
including single edits, batch edits, and undo/redo functionality.
"""

from datetime import datetime, timezone

from app.infrastructure.observability import get_logger
from app.models.edit import (
    BatchEditResponse,
    EditHistory,
    EditRequest,
    EditResponse,
    FieldEdit,
    FieldState,
    FieldValue,
    FieldValuesResponse,
    UndoRedoResponse,
)
from app.repositories import EditRepository

logger = get_logger("edit_service")


class EditService:
    """Service for managing field edits.

    Handles applying edits, batch edits, undo/redo operations,
    and retrieving field values and edit history.
    """

    def __init__(self, edit_repo: EditRepository) -> None:
        """Initialize the edit service.

        Args:
            edit_repo: Repository for edit persistence.
        """
        self._edit_repo = edit_repo

    def apply_edit(
        self,
        conversation_id: str,
        edit_request: EditRequest,
    ) -> EditResponse:
        """Apply a single field edit.

        Args:
            conversation_id: ID of the conversation.
            edit_request: The edit to apply.

        Returns:
            EditResponse with success status and details.
        """
        logger.info(
            "Applying edit",
            conversation_id=conversation_id,
            field_id=edit_request.field_id,
            source=edit_request.source,
        )

        # Get current value
        current_state = self._edit_repo.get_field_value(
            conversation_id,
            edit_request.field_id,
        )
        old_value = current_state.current_value if current_state else None

        # Create the field edit
        now = datetime.now(timezone.utc)
        field_edit = FieldEdit(
            field_id=edit_request.field_id,
            old_value=old_value,
            new_value=edit_request.value,
            bbox_id=None,  # Could be populated if we have template context
            timestamp=now,
        )

        # Save the edit (this also updates field value)
        self._edit_repo.save_edit(conversation_id, field_edit)

        # Build message
        field_display = edit_request.field_id
        if old_value is None:
            message = f"Set {field_display} to '{edit_request.value}'"
        else:
            message = f"Updated {field_display} to '{edit_request.value}'"

        logger.info(
            "Edit applied successfully",
            conversation_id=conversation_id,
            field_id=edit_request.field_id,
            message=message,
        )

        return EditResponse(
            success=True,
            field_id=edit_request.field_id,
            old_value=old_value,
            new_value=edit_request.value,
            message=message,
        )

    def apply_batch_edits(
        self,
        conversation_id: str,
        edit_requests: list[EditRequest],
    ) -> BatchEditResponse:
        """Apply multiple field edits at once.

        Args:
            conversation_id: ID of the conversation.
            edit_requests: List of edits to apply.

        Returns:
            BatchEditResponse with individual results and summary.
        """
        logger.info(
            "Applying batch edits",
            conversation_id=conversation_id,
            edit_count=len(edit_requests),
        )

        results: list[EditResponse] = []
        success_count = 0
        failure_count = 0

        for edit_request in edit_requests:
            try:
                result = self.apply_edit(conversation_id, edit_request)
                results.append(result)
                if result.success:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                logger.error(
                    "Edit failed in batch",
                    conversation_id=conversation_id,
                    field_id=edit_request.field_id,
                    error=str(e),
                )
                results.append(
                    EditResponse(
                        success=False,
                        field_id=edit_request.field_id,
                        old_value=None,
                        new_value=edit_request.value,
                        message=f"Failed to update {edit_request.field_id}",
                    )
                )
                failure_count += 1

        # Build summary message
        if failure_count == 0:
            summary = f"Updated {success_count} field{'s' if success_count != 1 else ''}."
        else:
            summary = f"Updated {success_count} field{'s' if success_count != 1 else ''}, {failure_count} failed."

        all_success = failure_count == 0

        logger.info(
            "Batch edits completed",
            conversation_id=conversation_id,
            success_count=success_count,
            failure_count=failure_count,
        )

        return BatchEditResponse(
            success=all_success,
            results=results,
            summary=summary,
        )

    def undo(self, conversation_id: str) -> UndoRedoResponse:
        """Undo the last edit.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            UndoRedoResponse with reverted edits and state info.
        """
        logger.info("Undo requested", conversation_id=conversation_id)

        edits_reverted = self._edit_repo.undo(conversation_id)

        if edits_reverted is None:
            logger.info("Nothing to undo", conversation_id=conversation_id)
            history = self._edit_repo.get_history(conversation_id)
            return UndoRedoResponse(
                action="undo",
                edits_reverted=[],
                can_undo=history.can_undo,
                can_redo=history.can_redo,
            )

        # Get updated history state
        history = self._edit_repo.get_history(conversation_id)

        logger.info(
            "Undo completed",
            conversation_id=conversation_id,
            edits_undone=len(edits_reverted),
            can_undo=history.can_undo,
            can_redo=history.can_redo,
        )

        return UndoRedoResponse(
            action="undo",
            edits_reverted=edits_reverted,
            can_undo=history.can_undo,
            can_redo=history.can_redo,
        )

    def redo(self, conversation_id: str) -> UndoRedoResponse:
        """Redo a previously undone edit.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            UndoRedoResponse with redone edits and state info.
        """
        logger.info("Redo requested", conversation_id=conversation_id)

        edits_redone = self._edit_repo.redo(conversation_id)

        if edits_redone is None:
            logger.info("Nothing to redo", conversation_id=conversation_id)
            history = self._edit_repo.get_history(conversation_id)
            return UndoRedoResponse(
                action="redo",
                edits_reverted=[],
                can_undo=history.can_undo,
                can_redo=history.can_redo,
            )

        # Get updated history state
        history = self._edit_repo.get_history(conversation_id)

        logger.info(
            "Redo completed",
            conversation_id=conversation_id,
            edits_redone=len(edits_redone),
            can_undo=history.can_undo,
            can_redo=history.can_redo,
        )

        return UndoRedoResponse(
            action="redo",
            edits_reverted=edits_redone,
            can_undo=history.can_undo,
            can_redo=history.can_redo,
        )

    def get_field_value(
        self,
        conversation_id: str,
        field_id: str,
    ) -> str | None:
        """Get the current value of a field.

        Args:
            conversation_id: ID of the conversation.
            field_id: ID of the field.

        Returns:
            Current value or None if not set.
        """
        state = self._edit_repo.get_field_value(conversation_id, field_id)
        return state.current_value if state else None

    def get_all_field_values(
        self,
        conversation_id: str,
    ) -> FieldValuesResponse:
        """Get all field values for a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            FieldValuesResponse with all field values and undo/redo state.
        """
        field_states = self._edit_repo.get_all_field_values(conversation_id)
        history = self._edit_repo.get_history(conversation_id)

        fields = [
            FieldValue(
                field_id=state.field_id,
                value=state.current_value,
                source=state.source,
                last_modified=state.last_modified,
            )
            for state in field_states
        ]

        return FieldValuesResponse(
            conversation_id=conversation_id,
            fields=fields,
            can_undo=history.can_undo,
            can_redo=history.can_redo,
        )

    def get_edit_history(self, conversation_id: str) -> EditHistory:
        """Get the full edit history for a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            EditHistory with all edits and current index.
        """
        return self._edit_repo.get_history(conversation_id)

    def clear_history(self, conversation_id: str) -> None:
        """Clear all edit history for a conversation.

        Args:
            conversation_id: ID of the conversation.
        """
        logger.info("Clearing edit history", conversation_id=conversation_id)
        self._edit_repo.clear_history(conversation_id)
