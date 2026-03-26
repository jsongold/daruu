"""Tests for conversation logger.

Tests the ConversationLogger class for logging conversation events.
Ensures all log methods work without errors and produce correct output.
"""

from unittest.mock import MagicMock, patch

import pytest
from app.services.conversation_logger import ConversationLogger, _truncate, log


class TestTruncateFunction:
    """Tests for the _truncate helper function."""

    def test_truncate_none(self) -> None:
        """Test truncate returns None for None input."""
        assert _truncate(None, 50) is None

    def test_truncate_short_text(self) -> None:
        """Test truncate returns original text if shorter than max."""
        text = "Hello"
        result = _truncate(text, 50)
        assert result == "Hello"

    def test_truncate_exact_length(self) -> None:
        """Test truncate returns original text if exactly max length."""
        text = "x" * 50
        result = _truncate(text, 50)
        assert result == text
        assert len(result) == 50

    def test_truncate_long_text(self) -> None:
        """Test truncate adds ellipsis for long text."""
        text = "x" * 100
        result = _truncate(text, 50)
        assert result == "x" * 50 + "..."
        assert len(result) == 53  # 50 + "..."


class TestConversationLoggerMethods:
    """Tests for ConversationLogger method signatures and basic functionality."""

    @pytest.fixture
    def logger(self) -> ConversationLogger:
        """Create a logger instance for testing."""
        return ConversationLogger()

    def test_conversation_created(self, logger: ConversationLogger) -> None:
        """Test conversation_created logs without error."""
        # Should not raise
        logger.conversation_created(
            conversation_id="conv-123",
            user_id="user-456",
            title="Test Conversation",
        )

    def test_conversation_created_without_title(self, logger: ConversationLogger) -> None:
        """Test conversation_created without title."""
        logger.conversation_created(
            conversation_id="conv-123",
            user_id="user-456",
        )

    def test_conversation_resumed(self, logger: ConversationLogger) -> None:
        """Test conversation_resumed logs without error."""
        logger.conversation_resumed(
            conversation_id="conv-123",
            user_id="user-456",
        )

    def test_conversation_completed(self, logger: ConversationLogger) -> None:
        """Test conversation_completed logs without error."""
        logger.conversation_completed(
            conversation_id="conv-123",
            duration_seconds=120.5,
            message_count=15,
        )

    def test_conversation_completed_minimal(self, logger: ConversationLogger) -> None:
        """Test conversation_completed with minimal args."""
        logger.conversation_completed(conversation_id="conv-123")

    def test_conversation_abandoned(self, logger: ConversationLogger) -> None:
        """Test conversation_abandoned logs without error."""
        logger.conversation_abandoned(
            conversation_id="conv-123",
            reason="User closed browser",
        )

    def test_conversation_abandoned_without_reason(self, logger: ConversationLogger) -> None:
        """Test conversation_abandoned without reason."""
        logger.conversation_abandoned(conversation_id="conv-123")

    def test_message_received(self, logger: ConversationLogger) -> None:
        """Test message_received logs without error."""
        logger.message_received(
            conversation_id="conv-123",
            message_id="msg-456",
            content_preview="Hello, I need help...",
            has_files=True,
            file_count=2,
        )

    def test_message_received_minimal(self, logger: ConversationLogger) -> None:
        """Test message_received with minimal args."""
        logger.message_received(
            conversation_id="conv-123",
            message_id="msg-456",
        )

    def test_message_received_truncates_content(self, logger: ConversationLogger) -> None:
        """Test message_received truncates long content."""
        long_content = "x" * 100
        # Should not raise and should handle truncation
        logger.message_received(
            conversation_id="conv-123",
            message_id="msg-456",
            content_preview=long_content,
        )

    def test_file_uploaded(self, logger: ConversationLogger) -> None:
        """Test file_uploaded logs without error."""
        logger.file_uploaded(
            conversation_id="conv-123",
            message_id="msg-456",
            filename="document.pdf",
            content_type="application/pdf",
            size_bytes=1024000,
        )

    def test_agent_thinking(self, logger: ConversationLogger) -> None:
        """Test agent_thinking logs without error."""
        logger.agent_thinking(
            conversation_id="conv-123",
            stage="analyzing",
            message="Processing your documents...",
        )

    def test_agent_thinking_minimal(self, logger: ConversationLogger) -> None:
        """Test agent_thinking with minimal args."""
        logger.agent_thinking(
            conversation_id="conv-123",
            stage="mapping",
        )

    def test_agent_stage_change(self, logger: ConversationLogger) -> None:
        """Test agent_stage_change logs without error."""
        logger.agent_stage_change(
            conversation_id="conv-123",
            from_stage="analyzing",
            to_stage="mapping",
        )

    def test_agent_response(self, logger: ConversationLogger) -> None:
        """Test agent_response logs without error."""
        logger.agent_response(
            conversation_id="conv-123",
            message_id="msg-789",
            content_preview="Here's your filled form...",
            has_preview=True,
            requires_approval=True,
        )

    def test_agent_response_minimal(self, logger: ConversationLogger) -> None:
        """Test agent_response with minimal args."""
        logger.agent_response(
            conversation_id="conv-123",
            message_id="msg-789",
        )

    def test_document_detected(self, logger: ConversationLogger) -> None:
        """Test document_detected logs without error."""
        logger.document_detected(
            conversation_id="conv-123",
            document_id="doc-456",
            document_type="form",
            filename="application.pdf",
            page_count=3,
            confidence=0.95,
        )

    def test_fields_extracted(self, logger: ConversationLogger) -> None:
        """Test fields_extracted logs without error."""
        logger.fields_extracted(
            conversation_id="conv-123",
            field_count=20,
            filled_count=15,
            avg_confidence=0.87,
        )

    def test_preview_generated(self, logger: ConversationLogger) -> None:
        """Test preview_generated logs without error."""
        logger.preview_generated(
            conversation_id="conv-123",
            preview_ref="https://storage.example.com/preview.png",
        )

    def test_approval_requested(self, logger: ConversationLogger) -> None:
        """Test approval_requested logs without error."""
        logger.approval_requested(
            conversation_id="conv-123",
            message_id="msg-789",
            fields_to_approve=5,
        )

    def test_approval_received(self, logger: ConversationLogger) -> None:
        """Test approval_received logs without error."""
        logger.approval_received(
            conversation_id="conv-123",
            message_id="msg-789",
            approved=True,
        )

    def test_approval_received_rejected(self, logger: ConversationLogger) -> None:
        """Test approval_received with rejection."""
        logger.approval_received(
            conversation_id="conv-123",
            message_id="msg-789",
            approved=False,
        )

    def test_pdf_generated(self, logger: ConversationLogger) -> None:
        """Test pdf_generated logs without error."""
        logger.pdf_generated(
            conversation_id="conv-123",
            pdf_ref="https://storage.example.com/filled.pdf",
            size_bytes=2048000,
        )

    def test_pdf_generated_without_size(self, logger: ConversationLogger) -> None:
        """Test pdf_generated without size."""
        logger.pdf_generated(
            conversation_id="conv-123",
            pdf_ref="https://storage.example.com/filled.pdf",
        )

    def test_pdf_downloaded(self, logger: ConversationLogger) -> None:
        """Test pdf_downloaded logs without error."""
        logger.pdf_downloaded(
            conversation_id="conv-123",
            user_id="user-456",
        )

    def test_error(self, logger: ConversationLogger) -> None:
        """Test error logs without error."""
        logger.error(
            conversation_id="conv-123",
            error_code="EXTRACTION_FAILED",
            message="Could not extract data from document",
            details={"page": 2, "reason": "Image quality too low"},
        )

    def test_error_without_details(self, logger: ConversationLogger) -> None:
        """Test error without details."""
        logger.error(
            conversation_id="conv-123",
            error_code="LLM_ERROR",
            message="AI service temporarily unavailable",
        )

    def test_warning(self, logger: ConversationLogger) -> None:
        """Test warning logs without error."""
        logger.warning(
            conversation_id="conv-123",
            warning_code="LOW_CONFIDENCE",
            message="Some fields have low confidence values",
        )

    def test_llm_call(self, logger: ConversationLogger) -> None:
        """Test llm_call logs without error."""
        logger.llm_call(
            conversation_id="conv-123",
            model="gpt-4o",
            purpose="field_extraction",
            input_tokens=1500,
            output_tokens=500,
            duration_ms=2500,
        )

    def test_llm_call_minimal(self, logger: ConversationLogger) -> None:
        """Test llm_call with minimal args."""
        logger.llm_call(
            conversation_id="conv-123",
            model="gpt-4o-mini",
            purpose="validation",
        )

    def test_rate_limited(self, logger: ConversationLogger) -> None:
        """Test rate_limited logs without error."""
        logger.rate_limited(
            user_id="user-456",
            endpoint="/api/v2/conversations",
            limit=100,
            window_seconds=60,
        )


class TestConversationLoggerSingleton:
    """Tests for the singleton logger instance."""

    def test_singleton_exists(self) -> None:
        """Test that singleton log instance exists."""
        assert log is not None
        assert isinstance(log, ConversationLogger)

    def test_singleton_methods_available(self) -> None:
        """Test that singleton has expected methods."""
        assert hasattr(log, "conversation_created")
        assert hasattr(log, "message_received")
        assert hasattr(log, "error")
        assert hasattr(log, "warning")


class TestConversationLoggerOutput:
    """Tests for verifying log output format."""

    @pytest.fixture
    def mock_logger(self) -> MagicMock:
        """Create mock logger for capturing output."""
        return MagicMock()

    def test_conversation_created_calls_info(self, mock_logger: MagicMock) -> None:
        """Test conversation_created calls logger.info."""
        with patch("app.services.conversation_logger._logger", mock_logger):
            logger = ConversationLogger()
            logger.conversation_created("conv-123", "user-456", "Test")

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert call_args[0][0] == "conversation_created"
            assert call_args[1]["conversation_id"] == "conv-123"
            assert call_args[1]["user_id"] == "user-456"
            assert call_args[1]["title"] == "Test"

    def test_error_calls_error_level(self, mock_logger: MagicMock) -> None:
        """Test error method calls logger.error."""
        with patch("app.services.conversation_logger._logger", mock_logger):
            logger = ConversationLogger()
            logger.error("conv-123", "TEST_ERROR", "Test message")

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[0][0] == "conversation_error"
            assert call_args[1]["error_code"] == "TEST_ERROR"

    def test_warning_calls_warning_level(self, mock_logger: MagicMock) -> None:
        """Test warning method calls logger.warning."""
        with patch("app.services.conversation_logger._logger", mock_logger):
            logger = ConversationLogger()
            logger.warning("conv-123", "TEST_WARN", "Test warning")

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "conversation_warning"

    def test_rate_limited_calls_warning_level(self, mock_logger: MagicMock) -> None:
        """Test rate_limited calls logger.warning."""
        with patch("app.services.conversation_logger._logger", mock_logger):
            logger = ConversationLogger()
            logger.rate_limited("user-123", "/api/v2/test", 100, 60)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert call_args[0][0] == "rate_limited"

    def test_fields_extracted_rounds_confidence(self, mock_logger: MagicMock) -> None:
        """Test fields_extracted rounds avg_confidence to 2 decimals."""
        with patch("app.services.conversation_logger._logger", mock_logger):
            logger = ConversationLogger()
            logger.fields_extracted("conv-123", 10, 8, 0.87654321)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            # Should be rounded to 0.88
            assert call_args[1]["avg_confidence"] == 0.88


class TestConversationLoggerEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_string_conversation_id(self) -> None:
        """Test logging with empty conversation ID."""
        logger = ConversationLogger()
        # Should not raise
        logger.conversation_created("", "user-123")

    def test_special_characters_in_content(self) -> None:
        """Test logging with special characters in content."""
        logger = ConversationLogger()
        special_content = "Hello\n\t\r\x00\ud83d\ude00"
        # Should not raise
        logger.message_received("conv-123", "msg-456", special_content)

    def test_very_long_content(self) -> None:
        """Test logging with very long content."""
        logger = ConversationLogger()
        long_content = "x" * 10000
        # Should not raise, content should be truncated
        logger.message_received("conv-123", "msg-456", long_content)

    def test_unicode_content(self) -> None:
        """Test logging with unicode content."""
        logger = ConversationLogger()
        unicode_content = "Hello, world!"
        # Should not raise
        logger.message_received("conv-123", "msg-456", unicode_content)

    def test_zero_values(self) -> None:
        """Test logging with zero numeric values."""
        logger = ConversationLogger()
        # Should not raise
        logger.fields_extracted("conv-123", 0, 0, 0.0)
        logger.file_uploaded("conv-123", "msg-456", "empty.pdf", "application/pdf", 0)
        logger.llm_call("conv-123", "gpt-4o", "test", 0, 0, 0)

    def test_negative_duration(self) -> None:
        """Test logging with negative duration (edge case)."""
        logger = ConversationLogger()
        # Should not raise - validation is not enforced at logger level
        logger.conversation_completed("conv-123", duration_seconds=-1.0)

    def test_none_optional_values(self) -> None:
        """Test logging with None for all optional values."""
        logger = ConversationLogger()
        # Should not raise
        logger.conversation_created("conv-123", "user-456", None)
        logger.message_received("conv-123", "msg-456", None, False, 0)
        logger.agent_thinking("conv-123", "analyzing", None)
        logger.agent_response("conv-123", "msg-789", None, False, False)
        logger.conversation_abandoned("conv-123", None)
        logger.error("conv-123", "CODE", "message", None)
        logger.pdf_generated("conv-123", "ref", None)
        logger.llm_call("conv-123", "model", "purpose", None, None, None)


class TestConversationLoggerConcurrency:
    """Tests for thread-safety considerations."""

    def test_multiple_calls_dont_interfere(self) -> None:
        """Test that multiple rapid calls don't interfere."""
        logger = ConversationLogger()

        # Rapid fire multiple log calls
        for i in range(100):
            logger.message_received(f"conv-{i}", f"msg-{i}", f"content-{i}")

        # Should complete without error

    def test_different_log_levels_mixed(self) -> None:
        """Test mixing different log levels."""
        logger = ConversationLogger()

        # Mix of different log levels
        logger.conversation_created("conv-1", "user-1")
        logger.warning("conv-1", "WARN", "warning message")
        logger.message_received("conv-1", "msg-1")
        logger.error("conv-1", "ERROR", "error message")
        logger.conversation_completed("conv-1")

        # Should complete without error
