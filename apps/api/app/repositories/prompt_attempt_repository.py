"""Prompt attempt repository interface (Port).

Defines the contract for prompt attempt persistence operations.
"""

from typing import Any, Protocol

from app.models.prompt_attempt import PromptAttempt


class PromptAttemptRepository(Protocol):
    """Repository interface for PromptAttempt entities."""

    def create(
        self,
        conversation_id: str,
        document_id: str,
        system_prompt: str,
        user_prompt: str,
        custom_rules: list[str] | None = None,
        raw_response: str = "",
        parsed_result: dict[str, Any] | None = None,
        success: bool = False,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PromptAttempt:
        """Create a new prompt attempt record.

        Args:
            conversation_id: ID of the parent conversation.
            document_id: ID of the target document.
            system_prompt: System prompt sent to the LLM.
            user_prompt: User prompt sent to the LLM.
            custom_rules: Custom rules active during the attempt.
            raw_response: Raw LLM response text.
            parsed_result: Parsed result JSON.
            success: Whether the attempt succeeded.
            error: Error message if the attempt failed.
            metadata: Additional metadata.

        Returns:
            Created PromptAttempt entity with generated ID.
        """
        ...

    def get(self, attempt_id: str) -> PromptAttempt | None:
        """Get a prompt attempt by ID.

        Args:
            attempt_id: Unique attempt identifier.

        Returns:
            PromptAttempt if found, None otherwise.
        """
        ...

    def list_by_conversation(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PromptAttempt]:
        """List prompt attempts for a conversation.

        Args:
            conversation_id: ID of the conversation.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of prompt attempts, ordered by created_at desc.
        """
        ...

    def count_by_conversation(self, conversation_id: str) -> int:
        """Count prompt attempts for a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            Number of prompt attempts.
        """
        ...
