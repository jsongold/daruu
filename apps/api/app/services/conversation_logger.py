"""Simple conversation logging for Agent Chat UI.

Provides easy-to-use logging for tracking conversation flow.
Wraps the structured logging infrastructure.

Usage:
    from app.services.conversation_logger import log

    # Log conversation events
    log.conversation_created(conversation_id, user_id)
    log.message_received(conversation_id, message_id, content_preview)
    log.agent_thinking(conversation_id, stage, message)
    log.agent_response(conversation_id, message_id, content_preview)
    log.conversation_completed(conversation_id)
    log.error(conversation_id, error_code, message)

Output example (JSON in production):
    {"timestamp":"2024-01-30T10:00:00Z","severity":"INFO",
     "message":"conversation_created","conversation_id":"abc-123",
     "user_id":"user-456"}
"""

from typing import Any

from app.infrastructure.observability.logging import get_logger

# Create a dedicated logger for conversations
_logger = get_logger("conversation")


class ConversationLogger:
    """Simple logger for conversation events.

    All methods log structured events that are easy to filter and analyze.
    """

    def conversation_created(
        self,
        conversation_id: str,
        user_id: str,
        title: str | None = None,
    ) -> None:
        """Log when a new conversation is created."""
        _logger.info(
            "conversation_created",
            conversation_id=conversation_id,
            user_id=user_id,
            title=title,
        )

    def conversation_resumed(
        self,
        conversation_id: str,
        user_id: str,
    ) -> None:
        """Log when a conversation is resumed."""
        _logger.info(
            "conversation_resumed",
            conversation_id=conversation_id,
            user_id=user_id,
        )

    def conversation_completed(
        self,
        conversation_id: str,
        duration_seconds: float | None = None,
        message_count: int | None = None,
    ) -> None:
        """Log when a conversation is completed successfully."""
        _logger.info(
            "conversation_completed",
            conversation_id=conversation_id,
            duration_seconds=duration_seconds,
            message_count=message_count,
        )

    def conversation_abandoned(
        self,
        conversation_id: str,
        reason: str | None = None,
    ) -> None:
        """Log when a conversation is abandoned."""
        _logger.info(
            "conversation_abandoned",
            conversation_id=conversation_id,
            reason=reason,
        )

    def message_received(
        self,
        conversation_id: str,
        message_id: str,
        content_preview: str | None = None,
        has_files: bool = False,
        file_count: int = 0,
    ) -> None:
        """Log when a user message is received."""
        _logger.info(
            "message_received",
            conversation_id=conversation_id,
            message_id=message_id,
            content_preview=_truncate(content_preview, 50),
            has_files=has_files,
            file_count=file_count,
        )

    def file_uploaded(
        self,
        conversation_id: str,
        message_id: str,
        filename: str,
        content_type: str,
        size_bytes: int,
    ) -> None:
        """Log when a file is uploaded."""
        _logger.info(
            "file_uploaded",
            conversation_id=conversation_id,
            message_id=message_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
        )

    def agent_thinking(
        self,
        conversation_id: str,
        stage: str,
        message: str | None = None,
    ) -> None:
        """Log when agent starts thinking/processing."""
        _logger.info(
            "agent_thinking",
            conversation_id=conversation_id,
            stage=stage,
            message=message,
        )

    def agent_stage_change(
        self,
        conversation_id: str,
        from_stage: str,
        to_stage: str,
    ) -> None:
        """Log when agent changes processing stage."""
        _logger.info(
            "agent_stage_change",
            conversation_id=conversation_id,
            from_stage=from_stage,
            to_stage=to_stage,
        )

    def agent_response(
        self,
        conversation_id: str,
        message_id: str,
        content_preview: str | None = None,
        has_preview: bool = False,
        requires_approval: bool = False,
    ) -> None:
        """Log when agent sends a response."""
        _logger.info(
            "agent_response",
            conversation_id=conversation_id,
            message_id=message_id,
            content_preview=_truncate(content_preview, 50),
            has_preview=has_preview,
            requires_approval=requires_approval,
        )

    def document_detected(
        self,
        conversation_id: str,
        document_id: str,
        document_type: str,
        filename: str,
        page_count: int,
        confidence: float,
    ) -> None:
        """Log when a document is detected and classified."""
        _logger.info(
            "document_detected",
            conversation_id=conversation_id,
            document_id=document_id,
            document_type=document_type,
            filename=filename,
            page_count=page_count,
            confidence=confidence,
        )

    def fields_extracted(
        self,
        conversation_id: str,
        field_count: int,
        filled_count: int,
        avg_confidence: float,
    ) -> None:
        """Log when fields are extracted from documents."""
        _logger.info(
            "fields_extracted",
            conversation_id=conversation_id,
            field_count=field_count,
            filled_count=filled_count,
            avg_confidence=round(avg_confidence, 2),
        )

    def preview_generated(
        self,
        conversation_id: str,
        preview_ref: str,
    ) -> None:
        """Log when a preview is generated."""
        _logger.info(
            "preview_generated",
            conversation_id=conversation_id,
            preview_ref=preview_ref,
        )

    def approval_requested(
        self,
        conversation_id: str,
        message_id: str,
        fields_to_approve: int,
    ) -> None:
        """Log when approval is requested from user."""
        _logger.info(
            "approval_requested",
            conversation_id=conversation_id,
            message_id=message_id,
            fields_to_approve=fields_to_approve,
        )

    def approval_received(
        self,
        conversation_id: str,
        message_id: str,
        approved: bool,
    ) -> None:
        """Log when approval/rejection is received."""
        _logger.info(
            "approval_received",
            conversation_id=conversation_id,
            message_id=message_id,
            approved=approved,
        )

    def pdf_generated(
        self,
        conversation_id: str,
        pdf_ref: str,
        size_bytes: int | None = None,
    ) -> None:
        """Log when final PDF is generated."""
        _logger.info(
            "pdf_generated",
            conversation_id=conversation_id,
            pdf_ref=pdf_ref,
            size_bytes=size_bytes,
        )

    def pdf_downloaded(
        self,
        conversation_id: str,
        user_id: str,
    ) -> None:
        """Log when PDF is downloaded."""
        _logger.info(
            "pdf_downloaded",
            conversation_id=conversation_id,
            user_id=user_id,
        )

    def error(
        self,
        conversation_id: str,
        error_code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log an error in conversation processing."""
        _logger.error(
            "conversation_error",
            conversation_id=conversation_id,
            error_code=error_code,
            error_message=message,
            details=details,
        )

    def warning(
        self,
        conversation_id: str,
        warning_code: str,
        message: str,
    ) -> None:
        """Log a warning in conversation processing."""
        _logger.warning(
            "conversation_warning",
            conversation_id=conversation_id,
            warning_code=warning_code,
            warning_message=message,
        )

    def llm_call(
        self,
        conversation_id: str,
        model: str,
        purpose: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Log an LLM API call for cost tracking."""
        _logger.info(
            "llm_call",
            conversation_id=conversation_id,
            model=model,
            purpose=purpose,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
        )

    def rate_limited(
        self,
        user_id: str,
        endpoint: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        """Log when a user is rate limited."""
        _logger.warning(
            "rate_limited",
            user_id=user_id,
            endpoint=endpoint,
            limit=limit,
            window_seconds=window_seconds,
        )


def _truncate(text: str | None, max_length: int) -> str | None:
    """Truncate text for log preview."""
    if text is None:
        return None
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


# Singleton instance for easy import
log = ConversationLogger()
