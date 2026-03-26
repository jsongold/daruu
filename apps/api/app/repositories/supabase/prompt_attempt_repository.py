"""Supabase implementation of PromptAttemptRepository.

Provides prompt attempt persistence using Supabase PostgreSQL database.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.infrastructure.supabase.client import get_supabase_client
from app.infrastructure.supabase.resilience import with_retry
from app.models.prompt_attempt import PromptAttempt
from app.repositories import PromptAttemptRepository

logger = logging.getLogger(__name__)


class SupabasePromptAttemptRepository:
    """Supabase implementation of PromptAttemptRepository."""

    TABLE_NAME = "prompt_attempts"

    def __init__(self) -> None:
        """Initialize the repository."""
        self._client = get_supabase_client()

    def _to_model(self, row: dict[str, Any]) -> PromptAttempt:
        """Convert a database row to a PromptAttempt model."""
        created_at_str = row.get("created_at")
        if isinstance(created_at_str, str):
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        else:
            created_at = created_at_str or datetime.now(timezone.utc)

        updated_at_str = row.get("updated_at")
        if isinstance(updated_at_str, str):
            updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
        else:
            updated_at = updated_at_str or datetime.now(timezone.utc)

        return PromptAttempt(
            id=str(row["id"]),
            conversation_id=row["conversation_id"],
            document_id=row["document_id"],
            system_prompt=row["system_prompt"],
            user_prompt=row["user_prompt"],
            custom_rules=row.get("custom_rules") or [],
            raw_response=row.get("raw_response", ""),
            parsed_result=row.get("parsed_result"),
            success=row.get("success", False),
            error=row.get("error"),
            metadata=row.get("metadata") or {},
            created_at=created_at,
            updated_at=updated_at,
        )

    def _to_row(
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
        attempt_id: str | None = None,
    ) -> dict[str, Any]:
        """Convert prompt attempt data to a database row."""
        row: dict[str, Any] = {
            "conversation_id": conversation_id,
            "document_id": document_id,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "custom_rules": custom_rules or [],
            "raw_response": raw_response,
            "success": success,
            "metadata": metadata or {},
        }

        if attempt_id:
            row["id"] = attempt_id
        if parsed_result is not None:
            row["parsed_result"] = parsed_result
        if error is not None:
            row["error"] = error

        return row

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
        """Create a new prompt attempt record with retry on transient errors."""
        attempt_id = str(uuid4())
        row = self._to_row(
            conversation_id=conversation_id,
            document_id=document_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            custom_rules=custom_rules,
            raw_response=raw_response,
            parsed_result=parsed_result,
            success=success,
            error=error,
            metadata=metadata,
            attempt_id=attempt_id,
        )

        try:
            return self._create_with_retry(
                row,
                attempt_id,
                conversation_id,
                document_id,
                system_prompt,
                user_prompt,
                custom_rules,
                raw_response,
                parsed_result,
                success,
                error,
                metadata,
            )
        except Exception as e:
            logger.error(f"Failed to create prompt attempt: {e}")
            raise

    @with_retry(max_retries=3, base_delay=1.0)
    def _create_with_retry(
        self,
        row: dict[str, Any],
        attempt_id: str,
        conversation_id: str,
        document_id: str,
        system_prompt: str,
        user_prompt: str,
        custom_rules: list[str] | None,
        raw_response: str,
        parsed_result: dict[str, Any] | None,
        success: bool,
        error: str | None,
        metadata: dict[str, Any] | None,
    ) -> PromptAttempt:
        """Internal create with retry logic."""
        result = self._client.table(self.TABLE_NAME).insert(row).execute()

        if result.data and len(result.data) > 0:
            return self._to_model(result.data[0])

        now = datetime.now(timezone.utc)
        return PromptAttempt(
            id=attempt_id,
            conversation_id=conversation_id,
            document_id=document_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            custom_rules=custom_rules or [],
            raw_response=raw_response,
            parsed_result=parsed_result,
            success=success,
            error=error,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )

    def get(self, attempt_id: str) -> PromptAttempt | None:
        """Get a prompt attempt by ID with retry on transient errors."""
        try:
            return self._get_with_retry(attempt_id)
        except Exception as e:
            logger.error(f"Failed to get prompt attempt {attempt_id}: {e}")
            return None

    @with_retry(max_retries=3, base_delay=1.0)
    def _get_with_retry(self, attempt_id: str) -> PromptAttempt | None:
        """Internal get with retry logic."""
        result = self._client.table(self.TABLE_NAME).select("*").eq("id", attempt_id).execute()

        if result.data and len(result.data) > 0:
            return self._to_model(result.data[0])
        return None

    def list_by_conversation(
        self,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PromptAttempt]:
        """List prompt attempts for a conversation."""
        try:
            query = (
                self._client.table(self.TABLE_NAME)
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=True)
                .limit(limit)
            )

            if offset > 0:
                query = query.offset(offset)

            result = query.execute()
            return [self._to_model(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to list prompt attempts for conversation {conversation_id}: {e}")
            return []

    def count_by_conversation(self, conversation_id: str) -> int:
        """Count prompt attempts for a conversation."""
        try:
            result = (
                self._client.table(self.TABLE_NAME)
                .select("id", count="exact")
                .eq("conversation_id", conversation_id)
                .execute()
            )

            return result.count or 0
        except Exception as e:
            logger.error(f"Failed to count prompt attempts for conversation {conversation_id}: {e}")
            return 0


# Verify protocol compliance
_assert_protocol: PromptAttemptRepository = SupabasePromptAttemptRepository()
