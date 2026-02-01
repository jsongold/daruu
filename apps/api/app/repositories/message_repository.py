"""Message repository interface (Port).

This defines the contract for message persistence operations.
Implementations can be in-memory, database, or any other storage.
"""

from typing import Any, Protocol

from app.models.conversation import (
    ApprovalStatus,
    Attachment,
    Message,
    MessageRole,
)


class MessageRepository(Protocol):
    """Repository interface for Message entities.

    This protocol defines the contract that any message storage
    implementation must satisfy. All update operations follow
    immutable patterns - they return new objects rather than
    mutating existing ones.

    Example:
        class PostgresMessageRepository:
            def create(self, ...) -> Message: ...
            def get(self, message_id: str) -> Message | None: ...
            # etc.

        # Inject into service
        service = MessageService(repo=PostgresMessageRepository())
    """

    def create(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        thinking: str | None = None,
        preview_ref: str | None = None,
        approval_required: bool = False,
        attachments: list[Attachment] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """Create a new message.

        Args:
            conversation_id: ID of the conversation this message belongs to.
            role: Role of the sender (user, agent, system).
            content: Message text content.
            thinking: Optional agent thinking/reasoning.
            preview_ref: Optional preview image URL.
            approval_required: Whether this message requires approval.
            attachments: Optional list of attachments.
            metadata: Optional additional metadata.

        Returns:
            Created Message entity with generated ID.
        """
        ...

    def get(self, message_id: str) -> Message | None:
        """Get a message by ID.

        Args:
            message_id: Unique message identifier.

        Returns:
            Message if found, None otherwise.
        """
        ...

    def update(self, message_id: str, **updates: Any) -> Message | None:
        """Update a message with new values (immutable pattern).

        Creates a new Message with the updates applied.
        The original is not mutated.

        Args:
            message_id: Unique message identifier.
            **updates: Fields to update.

        Returns:
            Updated Message if found, None otherwise.
        """
        ...

    def update_approval_status(
        self,
        message_id: str,
        status: ApprovalStatus,
    ) -> Message | None:
        """Update the approval status of a message.

        Args:
            message_id: Unique message identifier.
            status: New approval status.

        Returns:
            Updated Message if found, None otherwise.
        """
        ...

    def list_by_conversation(
        self,
        conversation_id: str,
        before: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Message], bool]:
        """List messages for a conversation.

        Args:
            conversation_id: ID of the conversation.
            before: Get messages before this message ID.
            limit: Maximum number of results.

        Returns:
            Tuple of (list of messages, has_more flag).
        """
        ...

    def get_latest(self, conversation_id: str) -> Message | None:
        """Get the latest message in a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            Latest message if exists, None otherwise.
        """
        ...

    def count_by_conversation(self, conversation_id: str) -> int:
        """Count messages in a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            Number of messages.
        """
        ...

    def get_pending_approval(self, conversation_id: str) -> Message | None:
        """Get a message pending approval in a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            Message pending approval if exists, None otherwise.
        """
        ...

    def delete_by_conversation(self, conversation_id: str) -> int:
        """Delete all messages for a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            Number of messages deleted.
        """
        ...
