"""Conversation repository interface (Port).

This defines the contract for conversation persistence operations.
Implementations can be in-memory, database, or any other storage.
"""

from typing import Any, Protocol

from app.models.conversation import (
    AgentState,
    Conversation,
    ConversationStatus,
    ConversationSummary,
)


class ConversationRepository(Protocol):
    """Repository interface for Conversation entities.

    This protocol defines the contract that any conversation storage
    implementation must satisfy. All update operations follow
    immutable patterns - they return new objects rather than
    mutating existing ones.

    Example:
        class PostgresConversationRepository:
            def create(self, ...) -> Conversation: ...
            def get(self, conversation_id: str) -> Conversation | None: ...
            # etc.

        # Inject into service
        service = ConversationService(repo=PostgresConversationRepository())
    """

    def create(
        self,
        user_id: str,
        title: str | None = None,
    ) -> Conversation:
        """Create a new conversation.

        Args:
            user_id: ID of the user who owns the conversation.
            title: Optional title (auto-generated if not provided).

        Returns:
            Created Conversation entity with generated ID.
        """
        ...

    def get(self, conversation_id: str) -> Conversation | None:
        """Get a conversation by ID.

        Args:
            conversation_id: Unique conversation identifier.

        Returns:
            Conversation if found, None otherwise.
        """
        ...

    def get_by_user(self, user_id: str, conversation_id: str) -> Conversation | None:
        """Get a conversation by ID, verifying user ownership.

        Args:
            user_id: ID of the user who owns the conversation.
            conversation_id: Unique conversation identifier.

        Returns:
            Conversation if found and user matches, None otherwise.
        """
        ...

    def update(self, conversation_id: str, **updates: Any) -> Conversation | None:
        """Update a conversation with new values (immutable pattern).

        Creates a new Conversation with the updates applied.
        The original is not mutated.

        Args:
            conversation_id: Unique conversation identifier.
            **updates: Fields to update.

        Returns:
            Updated Conversation if found, None otherwise.
        """
        ...

    def update_status(
        self,
        conversation_id: str,
        status: ConversationStatus,
    ) -> Conversation | None:
        """Update the status of a conversation.

        Args:
            conversation_id: Unique conversation identifier.
            status: New status to set.

        Returns:
            Updated Conversation if found, None otherwise.
        """
        ...

    def set_form_document(
        self,
        conversation_id: str,
        document_id: str,
    ) -> Conversation | None:
        """Set the form document for a conversation.

        Args:
            conversation_id: Unique conversation identifier.
            document_id: ID of the form document.

        Returns:
            Updated Conversation if found, None otherwise.
        """
        ...

    def add_source_document(
        self,
        conversation_id: str,
        document_id: str,
    ) -> Conversation | None:
        """Add a source document to a conversation.

        Args:
            conversation_id: Unique conversation identifier.
            document_id: ID of the source document.

        Returns:
            Updated Conversation if found, None otherwise.
        """
        ...

    def set_filled_pdf_ref(
        self,
        conversation_id: str,
        ref: str,
    ) -> Conversation | None:
        """Set the filled PDF reference for a conversation.

        Args:
            conversation_id: Unique conversation identifier.
            ref: Storage reference to the filled PDF.

        Returns:
            Updated Conversation if found, None otherwise.
        """
        ...

    def list_by_user(
        self,
        user_id: str,
        status_filter: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[ConversationSummary], str | None]:
        """List conversations for a user.

        Args:
            user_id: ID of the user.
            status_filter: Optional filter by status (active, completed, all).
            limit: Maximum number of results.
            cursor: Pagination cursor.

        Returns:
            Tuple of (list of summaries, next cursor or None).
        """
        ...

    def delete(self, conversation_id: str) -> bool:
        """Delete a conversation by ID.

        Args:
            conversation_id: Unique conversation identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...

    # Agent state management

    def get_agent_state(self, conversation_id: str) -> AgentState | None:
        """Get the current agent state for a conversation.

        Args:
            conversation_id: Unique conversation identifier.

        Returns:
            AgentState if exists, None otherwise.
        """
        ...

    def save_agent_state(self, state: AgentState) -> AgentState:
        """Save or update the agent state for a conversation.

        Args:
            state: AgentState to save.

        Returns:
            Saved AgentState.
        """
        ...
