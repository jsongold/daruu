"""In-memory implementation of MessageRepository.

This is an in-memory adapter for the MessageRepository port.
Suitable for MVP development and testing. In production, swap for
a database-backed implementation (e.g., SupabaseMessageRepository).
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.conversation import (
    ApprovalStatus,
    Attachment,
    Message,
    MessageRole,
)
from app.repositories import MessageRepository


class MemoryMessageRepository:
    """In-memory implementation of MessageRepository.

    Thread-safe for single-process use. For multi-process deployments,
    use a database-backed implementation.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._messages: dict[str, Message] = {}
        # Index by conversation_id for efficient lookup
        self._conversation_messages: dict[str, list[str]] = {}

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
        """Create a new message."""
        message_id = str(uuid4())
        now = datetime.now(timezone.utc)

        message = Message(
            id=message_id,
            role=role,
            content=content,
            thinking=thinking,
            preview_ref=preview_ref,
            approval_required=approval_required,
            approval_status=ApprovalStatus.PENDING if approval_required else None,
            attachments=attachments or [],
            metadata=metadata or {},
            created_at=now,
        )

        self._messages[message_id] = message

        # Update conversation index
        if conversation_id not in self._conversation_messages:
            self._conversation_messages[conversation_id] = []
        self._conversation_messages[conversation_id].append(message_id)

        return message

    def get(self, message_id: str) -> Message | None:
        """Get a message by ID."""
        return self._messages.get(message_id)

    def update(self, message_id: str, **updates: Any) -> Message | None:
        """Update a message with new values (immutable pattern)."""
        message = self._messages.get(message_id)
        if message is None:
            return None

        # Create new message with updates (immutable)
        updated_data = message.model_dump()
        updated_data.update(updates)

        new_message = Message(**updated_data)
        self._messages[message_id] = new_message
        return new_message

    def update_approval_status(
        self,
        message_id: str,
        status: ApprovalStatus,
    ) -> Message | None:
        """Update the approval status of a message."""
        return self.update(message_id, approval_status=status)

    def list_by_conversation(
        self,
        conversation_id: str,
        before: str | None = None,
        limit: int = 50,
    ) -> tuple[list[Message], bool]:
        """List messages for a conversation."""
        message_ids = self._conversation_messages.get(conversation_id, [])

        # Get messages in order (oldest first)
        messages: list[Message] = []
        for msg_id in message_ids:
            msg = self._messages.get(msg_id)
            if msg:
                messages.append(msg)

        # Sort by created_at ascending
        messages.sort(key=lambda m: m.created_at)

        # Handle 'before' pagination (get messages before a specific message)
        if before:
            before_idx = None
            for i, msg in enumerate(messages):
                if msg.id == before:
                    before_idx = i
                    break
            if before_idx is not None:
                messages = messages[:before_idx]

        # For 'before' pagination, we return the last N messages
        # but keep them in ascending order
        if len(messages) > limit:
            has_more = True
            messages = messages[-limit:]
        else:
            has_more = False

        return messages, has_more

    def get_latest(self, conversation_id: str) -> Message | None:
        """Get the latest message in a conversation."""
        message_ids = self._conversation_messages.get(conversation_id, [])
        if not message_ids:
            return None

        # Get all messages and find the latest by created_at
        latest: Message | None = None
        for msg_id in message_ids:
            msg = self._messages.get(msg_id)
            if msg:
                if latest is None or msg.created_at > latest.created_at:
                    latest = msg

        return latest

    def count_by_conversation(self, conversation_id: str) -> int:
        """Count messages in a conversation."""
        return len(self._conversation_messages.get(conversation_id, []))

    def get_pending_approval(self, conversation_id: str) -> Message | None:
        """Get a message pending approval in a conversation."""
        message_ids = self._conversation_messages.get(conversation_id, [])

        for msg_id in message_ids:
            msg = self._messages.get(msg_id)
            if msg and msg.approval_required and msg.approval_status == ApprovalStatus.PENDING:
                return msg

        return None

    def delete_by_conversation(self, conversation_id: str) -> int:
        """Delete all messages for a conversation."""
        message_ids = self._conversation_messages.get(conversation_id, [])
        count = 0

        for msg_id in message_ids:
            if msg_id in self._messages:
                del self._messages[msg_id]
                count += 1

        if conversation_id in self._conversation_messages:
            del self._conversation_messages[conversation_id]

        return count


# Ensure it satisfies the protocol
_assert_msg_repo: MessageRepository = MemoryMessageRepository()
