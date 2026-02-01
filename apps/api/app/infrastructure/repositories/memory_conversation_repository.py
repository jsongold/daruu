"""In-memory implementation of ConversationRepository.

This is an in-memory adapter for the ConversationRepository port.
Suitable for MVP development and testing. In production, swap for
a database-backed implementation (e.g., SupabaseConversationRepository).
"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.conversation import (
    AgentStage,
    AgentState,
    Conversation,
    ConversationStatus,
    ConversationSummary,
)
from app.repositories import ConversationRepository


class MemoryConversationRepository:
    """In-memory implementation of ConversationRepository.

    Thread-safe for single-process use. For multi-process deployments,
    use a database-backed implementation.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""
        self._conversations: dict[str, Conversation] = {}
        self._agent_states: dict[str, AgentState] = {}
        # Index by user_id for efficient lookup
        self._user_conversations: dict[str, set[str]] = {}

    def create(
        self,
        user_id: str,
        title: str | None = None,
    ) -> Conversation:
        """Create a new conversation."""
        conversation_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Generate title if not provided
        if not title:
            title = f"New Chat - {now.strftime('%b %d')}"

        conversation = Conversation(
            id=conversation_id,
            status=ConversationStatus.ACTIVE,
            title=title,
            form_document_id=None,
            source_document_ids=[],
            filled_pdf_ref=None,
            created_at=now,
            updated_at=now,
        )

        self._conversations[conversation_id] = conversation

        # Update user index
        if user_id not in self._user_conversations:
            self._user_conversations[user_id] = set()
        self._user_conversations[user_id].add(conversation_id)

        # Initialize agent state
        agent_state = AgentState(
            conversation_id=conversation_id,
            current_stage=AgentStage.IDLE,
            detected_documents=[],
            form_fields=[],
            extracted_values=[],
            pending_questions=[],
            last_error=None,
            retry_count=0,
            last_activity=now,
        )
        self._agent_states[conversation_id] = agent_state

        return conversation

    def get(self, conversation_id: str) -> Conversation | None:
        """Get a conversation by ID."""
        return self._conversations.get(conversation_id)

    def get_by_user(self, user_id: str, conversation_id: str) -> Conversation | None:
        """Get a conversation by ID, verifying user ownership."""
        user_convs = self._user_conversations.get(user_id, set())
        if conversation_id not in user_convs:
            return None
        return self._conversations.get(conversation_id)

    def update(self, conversation_id: str, **updates: Any) -> Conversation | None:
        """Update a conversation with new values (immutable pattern)."""
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            return None

        # Create new conversation with updates (immutable)
        updated_data = conversation.model_dump()
        updated_data.update(updates)
        updated_data["updated_at"] = datetime.now(timezone.utc)

        new_conversation = Conversation(**updated_data)
        self._conversations[conversation_id] = new_conversation
        return new_conversation

    def update_status(
        self,
        conversation_id: str,
        status: ConversationStatus,
    ) -> Conversation | None:
        """Update the status of a conversation."""
        return self.update(conversation_id, status=status)

    def set_form_document(
        self,
        conversation_id: str,
        document_id: str,
    ) -> Conversation | None:
        """Set the form document for a conversation."""
        return self.update(conversation_id, form_document_id=document_id)

    def add_source_document(
        self,
        conversation_id: str,
        document_id: str,
    ) -> Conversation | None:
        """Add a source document to a conversation."""
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            return None

        new_sources = [*conversation.source_document_ids, document_id]
        return self.update(conversation_id, source_document_ids=new_sources)

    def set_filled_pdf_ref(
        self,
        conversation_id: str,
        ref: str,
    ) -> Conversation | None:
        """Set the filled PDF reference for a conversation."""
        return self.update(conversation_id, filled_pdf_ref=ref)

    def list_by_user(
        self,
        user_id: str,
        status_filter: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[ConversationSummary], str | None]:
        """List conversations for a user."""
        user_conv_ids = self._user_conversations.get(user_id, set())

        # Get conversations and filter by status
        conversations: list[Conversation] = []
        for conv_id in user_conv_ids:
            conv = self._conversations.get(conv_id)
            if conv is None:
                continue

            if status_filter and status_filter != "all":
                if status_filter == "active" and conv.status != ConversationStatus.ACTIVE:
                    continue
                if status_filter == "completed" and conv.status != ConversationStatus.COMPLETED:
                    continue

            conversations.append(conv)

        # Sort by updated_at descending
        conversations.sort(key=lambda c: c.updated_at, reverse=True)

        # Handle cursor-based pagination
        if cursor:
            # Find the position after the cursor
            cursor_found = False
            filtered: list[Conversation] = []
            for conv in conversations:
                if cursor_found:
                    filtered.append(conv)
                elif conv.id == cursor:
                    cursor_found = True
            conversations = filtered

        # Apply limit + 1 to check for more
        has_more = len(conversations) > limit
        conversations = conversations[:limit]

        # Convert to summaries
        summaries = [
            ConversationSummary(
                id=conv.id,
                status=conv.status,
                title=conv.title,
                last_message_preview=None,  # Would need message repo to get this
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
            for conv in conversations
        ]

        next_cursor = conversations[-1].id if has_more and conversations else None
        return summaries, next_cursor

    def delete(self, conversation_id: str) -> bool:
        """Delete a conversation by ID."""
        if conversation_id not in self._conversations:
            return False

        del self._conversations[conversation_id]

        # Remove from user index
        for user_convs in self._user_conversations.values():
            user_convs.discard(conversation_id)

        # Remove agent state
        if conversation_id in self._agent_states:
            del self._agent_states[conversation_id]

        return True

    def get_agent_state(self, conversation_id: str) -> AgentState | None:
        """Get the current agent state for a conversation."""
        return self._agent_states.get(conversation_id)

    def save_agent_state(self, state: AgentState) -> AgentState:
        """Save or update the agent state for a conversation."""
        self._agent_states[state.conversation_id] = state
        return state


# Ensure it satisfies the protocol
_assert_conv_repo: ConversationRepository = MemoryConversationRepository()
