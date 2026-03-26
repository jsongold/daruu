"""Tests for conversation Pydantic models.

Tests all conversation-related models from app.models.conversation module.
Validates serialization, deserialization, enum values, and frozen behavior.
"""

from datetime import datetime, timezone

import pytest
from app.models.conversation import (
    ERROR_MESSAGES,
    AgentStage,
    AgentState,
    ApprovalStatus,
    ApprovePreviewRequest,
    # Response models
    Attachment,
    Conversation,
    ConversationListResponse,
    # Enums
    ConversationStatus,
    ConversationSummary,
    ConversationWithMessages,
    # Request models
    CreateConversationRequest,
    # Agent state models
    DetectedDocument,
    ErrorCode,
    # Error models
    ErrorDetail,
    ErrorResponse,
    Message,
    MessageListResponse,
    MessageRole,
    SendMessageRequest,
    SSEApprovalData,
    # SSE models
    SSEConnectedData,
    SSEErrorData,
    SSEEventType,
    SSEMessageData,
    SSEPreviewData,
    SSEStageChangeData,
    SSEThinkingData,
)
from pydantic import ValidationError


class TestConversationStatusEnum:
    """Tests for ConversationStatus enum."""

    def test_enum_values(self) -> None:
        """Test all expected status values exist."""
        assert ConversationStatus.ACTIVE == "active"
        assert ConversationStatus.COMPLETED == "completed"
        assert ConversationStatus.ABANDONED == "abandoned"
        assert ConversationStatus.ERROR == "error"

    def test_enum_is_string(self) -> None:
        """Test enum values are strings."""
        assert isinstance(ConversationStatus.ACTIVE.value, str)


class TestMessageRoleEnum:
    """Tests for MessageRole enum."""

    def test_enum_values(self) -> None:
        """Test all expected role values exist."""
        assert MessageRole.USER == "user"
        assert MessageRole.AGENT == "agent"
        assert MessageRole.SYSTEM == "system"


class TestApprovalStatusEnum:
    """Tests for ApprovalStatus enum."""

    def test_enum_values(self) -> None:
        """Test all expected approval status values exist."""
        assert ApprovalStatus.PENDING == "pending"
        assert ApprovalStatus.APPROVED == "approved"
        assert ApprovalStatus.REJECTED == "rejected"
        assert ApprovalStatus.EDITED == "edited"


class TestAgentStageEnum:
    """Tests for AgentStage enum."""

    def test_enum_values(self) -> None:
        """Test all expected stage values exist."""
        assert AgentStage.IDLE == "idle"
        assert AgentStage.ANALYZING == "analyzing"
        assert AgentStage.CONFIRMING == "confirming"
        assert AgentStage.MAPPING == "mapping"
        assert AgentStage.FILLING == "filling"
        assert AgentStage.REVIEWING == "reviewing"
        assert AgentStage.COMPLETE == "complete"
        assert AgentStage.ERROR == "error"


class TestSSEEventTypeEnum:
    """Tests for SSEEventType enum."""

    def test_enum_values(self) -> None:
        """Test all expected SSE event types exist."""
        assert SSEEventType.CONNECTED == "connected"
        assert SSEEventType.THINKING == "thinking"
        assert SSEEventType.MESSAGE == "message"
        assert SSEEventType.PREVIEW == "preview"
        assert SSEEventType.APPROVAL == "approval"
        assert SSEEventType.STAGE_CHANGE == "stage_change"
        assert SSEEventType.ERROR == "error"
        assert SSEEventType.COMPLETE == "complete"


class TestErrorCodeEnum:
    """Tests for ErrorCode enum."""

    def test_client_error_codes(self) -> None:
        """Test client error codes (4xx) exist."""
        assert ErrorCode.INVALID_FILE_TYPE == "INVALID_FILE_TYPE"
        assert ErrorCode.FILE_TOO_LARGE == "FILE_TOO_LARGE"
        assert ErrorCode.TOO_MANY_FILES == "TOO_MANY_FILES"
        assert ErrorCode.CONVERSATION_NOT_FOUND == "CONVERSATION_NOT_FOUND"
        assert ErrorCode.CONVERSATION_COMPLETED == "CONVERSATION_COMPLETED"
        assert ErrorCode.RATE_LIMITED == "RATE_LIMITED"

    def test_agent_error_codes(self) -> None:
        """Test agent error codes (5xx) exist."""
        assert ErrorCode.AGENT_TIMEOUT == "AGENT_TIMEOUT"
        assert ErrorCode.EXTRACTION_FAILED == "EXTRACTION_FAILED"
        assert ErrorCode.FILL_FAILED == "FILL_FAILED"
        assert ErrorCode.LLM_ERROR == "LLM_ERROR"

    def test_all_error_codes_have_messages(self) -> None:
        """Test that all error codes have corresponding messages."""
        for code in ErrorCode:
            assert code in ERROR_MESSAGES, f"Missing message for {code}"
            assert isinstance(ERROR_MESSAGES[code], str)
            assert len(ERROR_MESSAGES[code]) > 0


class TestCreateConversationRequest:
    """Tests for CreateConversationRequest model."""

    def test_with_title(self) -> None:
        """Test creating request with title."""
        request = CreateConversationRequest(title="My Conversation")
        assert request.title == "My Conversation"

    def test_without_title(self) -> None:
        """Test creating request without title."""
        request = CreateConversationRequest()
        assert request.title is None

    def test_is_frozen(self) -> None:
        """Test that model is immutable."""
        request = CreateConversationRequest(title="Test")
        with pytest.raises(ValidationError):
            request.title = "Modified"  # type: ignore


class TestSendMessageRequest:
    """Tests for SendMessageRequest model."""

    def test_valid_content(self) -> None:
        """Test creating request with valid content."""
        request = SendMessageRequest(content="Hello, agent!")
        assert request.content == "Hello, agent!"

    def test_empty_content_fails(self) -> None:
        """Test that empty content is rejected."""
        with pytest.raises(ValidationError):
            SendMessageRequest(content="")

    def test_content_too_long_fails(self) -> None:
        """Test that content exceeding max length is rejected."""
        with pytest.raises(ValidationError):
            SendMessageRequest(content="a" * 10001)

    def test_max_length_content(self) -> None:
        """Test that max length content is accepted."""
        content = "a" * 10000
        request = SendMessageRequest(content=content)
        assert len(request.content) == 10000

    def test_is_frozen(self) -> None:
        """Test that model is immutable."""
        request = SendMessageRequest(content="Test")
        with pytest.raises(ValidationError):
            request.content = "Modified"  # type: ignore


class TestApprovePreviewRequest:
    """Tests for ApprovePreviewRequest model."""

    def test_valid_request(self) -> None:
        """Test creating valid approval request."""
        request = ApprovePreviewRequest(message_id="msg-123")
        assert request.message_id == "msg-123"

    def test_missing_message_id_fails(self) -> None:
        """Test that missing message_id is rejected."""
        with pytest.raises(ValidationError):
            ApprovePreviewRequest()  # type: ignore

    def test_is_frozen(self) -> None:
        """Test that model is immutable."""
        request = ApprovePreviewRequest(message_id="msg-123")
        with pytest.raises(ValidationError):
            request.message_id = "modified"  # type: ignore


class TestAttachment:
    """Tests for Attachment model."""

    def test_valid_attachment(self) -> None:
        """Test creating valid attachment."""
        attachment = Attachment(
            id="att-123",
            filename="document.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            ref="https://storage.example.com/doc.pdf",
            document_id="doc-456",
        )
        assert attachment.id == "att-123"
        assert attachment.filename == "document.pdf"
        assert attachment.content_type == "application/pdf"
        assert attachment.size_bytes == 1024
        assert attachment.ref == "https://storage.example.com/doc.pdf"
        assert attachment.document_id == "doc-456"

    def test_attachment_without_document_id(self) -> None:
        """Test attachment without linked document."""
        attachment = Attachment(
            id="att-123",
            filename="image.png",
            content_type="image/png",
            size_bytes=2048,
            ref="https://storage.example.com/img.png",
        )
        assert attachment.document_id is None

    def test_negative_size_fails(self) -> None:
        """Test that negative size is rejected."""
        with pytest.raises(ValidationError):
            Attachment(
                id="att-123",
                filename="doc.pdf",
                content_type="application/pdf",
                size_bytes=-1,
                ref="https://example.com/doc.pdf",
            )

    def test_is_frozen(self) -> None:
        """Test that model is immutable."""
        attachment = Attachment(
            id="att-123",
            filename="doc.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            ref="https://example.com/doc.pdf",
        )
        with pytest.raises(ValidationError):
            attachment.filename = "modified.pdf"  # type: ignore


class TestMessage:
    """Tests for Message model."""

    def test_valid_user_message(self) -> None:
        """Test creating valid user message."""
        now = datetime.now(timezone.utc)
        message = Message(
            id="msg-123",
            role=MessageRole.USER,
            content="Hello!",
            created_at=now,
        )
        assert message.id == "msg-123"
        assert message.role == MessageRole.USER
        assert message.content == "Hello!"
        assert message.thinking is None
        assert message.preview_ref is None
        assert message.approval_required is False
        assert message.approval_status is None
        assert message.attachments == []
        assert message.metadata == {}
        assert message.created_at == now

    def test_valid_agent_message_with_approval(self) -> None:
        """Test creating agent message with approval required."""
        now = datetime.now(timezone.utc)
        message = Message(
            id="msg-456",
            role=MessageRole.AGENT,
            content="Here's your preview.",
            thinking="Analyzing document...",
            preview_ref="https://preview.example.com/img.png",
            approval_required=True,
            approval_status=ApprovalStatus.PENDING,
            created_at=now,
        )
        assert message.role == MessageRole.AGENT
        assert message.thinking == "Analyzing document..."
        assert message.preview_ref is not None
        assert message.approval_required is True
        assert message.approval_status == ApprovalStatus.PENDING

    def test_message_with_attachments(self) -> None:
        """Test message with file attachments."""
        now = datetime.now(timezone.utc)
        attachment = Attachment(
            id="att-1",
            filename="doc.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            ref="https://storage.example.com/doc.pdf",
        )
        message = Message(
            id="msg-789",
            role=MessageRole.USER,
            content="See attached file.",
            attachments=[attachment],
            created_at=now,
        )
        assert len(message.attachments) == 1
        assert message.attachments[0].filename == "doc.pdf"

    def test_is_frozen(self) -> None:
        """Test that model is immutable."""
        message = Message(
            id="msg-123",
            role=MessageRole.USER,
            content="Test",
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(ValidationError):
            message.content = "Modified"  # type: ignore


class TestConversation:
    """Tests for Conversation model."""

    def test_valid_conversation(self) -> None:
        """Test creating valid conversation."""
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            id="conv-123",
            status=ConversationStatus.ACTIVE,
            title="Tax Form 2024",
            created_at=now,
            updated_at=now,
        )
        assert conversation.id == "conv-123"
        assert conversation.status == ConversationStatus.ACTIVE
        assert conversation.title == "Tax Form 2024"
        assert conversation.form_document_id is None
        assert conversation.source_document_ids == []
        assert conversation.filled_pdf_ref is None

    def test_conversation_with_documents(self) -> None:
        """Test conversation with linked documents."""
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            id="conv-456",
            status=ConversationStatus.COMPLETED,
            title="Completed Form",
            form_document_id="form-doc-1",
            source_document_ids=["src-1", "src-2"],
            filled_pdf_ref="https://storage.example.com/filled.pdf",
            created_at=now,
            updated_at=now,
        )
        assert conversation.form_document_id == "form-doc-1"
        assert len(conversation.source_document_ids) == 2
        assert conversation.filled_pdf_ref is not None

    def test_is_frozen(self) -> None:
        """Test that model is immutable."""
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            id="conv-123",
            status=ConversationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        with pytest.raises(ValidationError):
            conversation.status = ConversationStatus.COMPLETED  # type: ignore


class TestConversationSummary:
    """Tests for ConversationSummary model."""

    def test_valid_summary(self) -> None:
        """Test creating valid conversation summary."""
        now = datetime.now(timezone.utc)
        summary = ConversationSummary(
            id="conv-123",
            status=ConversationStatus.ACTIVE,
            title="My Form",
            last_message_preview="Hello...",
            created_at=now,
            updated_at=now,
        )
        assert summary.id == "conv-123"
        assert summary.last_message_preview == "Hello..."

    def test_summary_without_preview(self) -> None:
        """Test summary without last message preview."""
        now = datetime.now(timezone.utc)
        summary = ConversationSummary(
            id="conv-123",
            status=ConversationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        assert summary.last_message_preview is None
        assert summary.title is None


class TestConversationWithMessages:
    """Tests for ConversationWithMessages model."""

    def test_valid_conversation_with_messages(self) -> None:
        """Test conversation with embedded messages."""
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            id="conv-123",
            status=ConversationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        message = Message(
            id="msg-1",
            role=MessageRole.USER,
            content="Hello",
            created_at=now,
        )
        result = ConversationWithMessages(
            conversation=conversation,
            messages=[message],
        )
        assert result.conversation.id == "conv-123"
        assert len(result.messages) == 1

    def test_empty_messages(self) -> None:
        """Test conversation with no messages."""
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            id="conv-123",
            status=ConversationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        result = ConversationWithMessages(
            conversation=conversation,
            messages=[],
        )
        assert len(result.messages) == 0


class TestConversationListResponse:
    """Tests for ConversationListResponse model."""

    def test_valid_list_response(self) -> None:
        """Test list response with items."""
        now = datetime.now(timezone.utc)
        summary = ConversationSummary(
            id="conv-1",
            status=ConversationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        response = ConversationListResponse(
            items=[summary],
            next_cursor="cursor-abc",
        )
        assert len(response.items) == 1
        assert response.next_cursor == "cursor-abc"

    def test_empty_list_response(self) -> None:
        """Test empty list response."""
        response = ConversationListResponse(items=[], next_cursor=None)
        assert len(response.items) == 0
        assert response.next_cursor is None


class TestMessageListResponse:
    """Tests for MessageListResponse model."""

    def test_valid_response(self) -> None:
        """Test message list response."""
        now = datetime.now(timezone.utc)
        message = Message(
            id="msg-1",
            role=MessageRole.USER,
            content="Test",
            created_at=now,
        )
        response = MessageListResponse(items=[message], has_more=True)
        assert len(response.items) == 1
        assert response.has_more is True


class TestSSEEventModels:
    """Tests for SSE event data models."""

    def test_sse_connected_data(self) -> None:
        """Test SSE connected event data."""
        data = SSEConnectedData(conversation_id="conv-123")
        assert data.conversation_id == "conv-123"

    def test_sse_thinking_data(self) -> None:
        """Test SSE thinking event data."""
        data = SSEThinkingData(
            stage=AgentStage.ANALYZING,
            message="Processing your documents...",
        )
        assert data.stage == AgentStage.ANALYZING
        assert data.message == "Processing your documents..."

    def test_sse_message_data(self) -> None:
        """Test SSE message event data."""
        data = SSEMessageData(
            id="msg-123",
            role=MessageRole.AGENT,
            content="Analysis complete.",
        )
        assert data.id == "msg-123"
        assert data.role == MessageRole.AGENT

    def test_sse_preview_data(self) -> None:
        """Test SSE preview event data."""
        data = SSEPreviewData(
            message_id="msg-123",
            preview_ref="https://preview.example.com/img.png",
        )
        assert data.message_id == "msg-123"
        assert data.preview_ref.startswith("https://")

    def test_sse_approval_data(self) -> None:
        """Test SSE approval event data."""
        data = SSEApprovalData(
            message_id="msg-123",
            fields_to_approve=["field-1", "field-2"],
        )
        assert data.message_id == "msg-123"
        assert len(data.fields_to_approve) == 2

    def test_sse_stage_change_data(self) -> None:
        """Test SSE stage change event data."""
        data = SSEStageChangeData(
            previous_stage=AgentStage.ANALYZING,
            new_stage=AgentStage.MAPPING,
        )
        assert data.previous_stage == AgentStage.ANALYZING
        assert data.new_stage == AgentStage.MAPPING

    def test_sse_error_data(self) -> None:
        """Test SSE error event data."""
        data = SSEErrorData(
            code="EXTRACTION_FAILED",
            message="Could not extract data from document",
        )
        assert data.code == "EXTRACTION_FAILED"
        assert "extract" in data.message.lower()


class TestErrorModels:
    """Tests for error response models."""

    def test_error_detail(self) -> None:
        """Test ErrorDetail model."""
        error = ErrorDetail(
            code=ErrorCode.INVALID_FILE_TYPE,
            message="Only PDF and image files are supported",
        )
        assert error.code == ErrorCode.INVALID_FILE_TYPE
        assert error.message == "Only PDF and image files are supported"
        assert error.details is None
        assert error.retry_after is None

    def test_error_detail_with_details(self) -> None:
        """Test ErrorDetail with additional details."""
        error = ErrorDetail(
            code=ErrorCode.FILE_TOO_LARGE,
            message="File exceeds 50MB limit",
            details={"file_size": 75000000, "max_size": 50000000},
            retry_after=None,
        )
        assert error.details is not None
        assert error.details["file_size"] == 75000000

    def test_error_detail_with_retry_after(self) -> None:
        """Test ErrorDetail with retry_after."""
        error = ErrorDetail(
            code=ErrorCode.RATE_LIMITED,
            message="Too many requests",
            retry_after=60,
        )
        assert error.retry_after == 60

    def test_error_detail_negative_retry_fails(self) -> None:
        """Test that negative retry_after is rejected."""
        with pytest.raises(ValidationError):
            ErrorDetail(
                code=ErrorCode.RATE_LIMITED,
                message="Test",
                retry_after=-1,
            )

    def test_error_response(self) -> None:
        """Test ErrorResponse model."""
        error = ErrorDetail(
            code=ErrorCode.CONVERSATION_NOT_FOUND,
            message="Conversation not found",
        )
        response = ErrorResponse(error=error)
        assert response.error.code == ErrorCode.CONVERSATION_NOT_FOUND


class TestDetectedDocument:
    """Tests for DetectedDocument model."""

    def test_valid_detected_document(self) -> None:
        """Test creating valid detected document."""
        doc = DetectedDocument(
            document_id="doc-123",
            filename="form.pdf",
            document_type="form",
            confidence=0.95,
            page_count=3,
            preview_ref="https://preview.example.com/page1.png",
        )
        assert doc.document_id == "doc-123"
        assert doc.filename == "form.pdf"
        assert doc.document_type == "form"
        assert doc.confidence == 0.95
        assert doc.page_count == 3
        assert doc.preview_ref is not None

    def test_detected_document_without_preview(self) -> None:
        """Test detected document without preview."""
        doc = DetectedDocument(
            document_id="doc-456",
            filename="source.pdf",
            document_type="source",
            confidence=0.85,
            page_count=1,
        )
        assert doc.preview_ref is None

    def test_confidence_out_of_range_fails(self) -> None:
        """Test that confidence > 1.0 is rejected."""
        with pytest.raises(ValidationError):
            DetectedDocument(
                document_id="doc-123",
                filename="test.pdf",
                document_type="form",
                confidence=1.5,
                page_count=1,
            )

    def test_confidence_negative_fails(self) -> None:
        """Test that negative confidence is rejected."""
        with pytest.raises(ValidationError):
            DetectedDocument(
                document_id="doc-123",
                filename="test.pdf",
                document_type="form",
                confidence=-0.1,
                page_count=1,
            )

    def test_page_count_zero_fails(self) -> None:
        """Test that page_count < 1 is rejected."""
        with pytest.raises(ValidationError):
            DetectedDocument(
                document_id="doc-123",
                filename="test.pdf",
                document_type="form",
                confidence=0.9,
                page_count=0,
            )


class TestAgentState:
    """Tests for AgentState model."""

    def test_valid_agent_state(self) -> None:
        """Test creating valid agent state."""
        now = datetime.now(timezone.utc)
        state = AgentState(
            conversation_id="conv-123",
            current_stage=AgentStage.ANALYZING,
            last_activity=now,
        )
        assert state.conversation_id == "conv-123"
        assert state.current_stage == AgentStage.ANALYZING
        assert state.detected_documents == []
        assert state.form_fields == []
        assert state.extracted_values == []
        assert state.pending_questions == []
        assert state.last_error is None
        assert state.retry_count == 0
        assert state.last_activity == now

    def test_agent_state_with_data(self) -> None:
        """Test agent state with populated data."""
        now = datetime.now(timezone.utc)
        doc = DetectedDocument(
            document_id="doc-1",
            filename="form.pdf",
            document_type="form",
            confidence=0.95,
            page_count=2,
        )
        state = AgentState(
            conversation_id="conv-456",
            current_stage=AgentStage.FILLING,
            detected_documents=[doc],
            form_fields=[{"id": "field-1", "name": "Name"}],
            extracted_values=[{"field_id": "field-1", "value": "John"}],
            pending_questions=[{"field_id": "field-2", "question": "What is your SSN?"}],
            last_error=None,
            retry_count=1,
            last_activity=now,
        )
        assert len(state.detected_documents) == 1
        assert len(state.form_fields) == 1
        assert len(state.extracted_values) == 1
        assert len(state.pending_questions) == 1
        assert state.retry_count == 1

    def test_agent_state_default_stage(self) -> None:
        """Test that default stage is IDLE."""
        now = datetime.now(timezone.utc)
        state = AgentState(
            conversation_id="conv-123",
            last_activity=now,
        )
        assert state.current_stage == AgentStage.IDLE

    def test_retry_count_negative_fails(self) -> None:
        """Test that negative retry_count is rejected."""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            AgentState(
                conversation_id="conv-123",
                retry_count=-1,
                last_activity=now,
            )

    def test_is_frozen(self) -> None:
        """Test that model is immutable."""
        now = datetime.now(timezone.utc)
        state = AgentState(
            conversation_id="conv-123",
            last_activity=now,
        )
        with pytest.raises(ValidationError):
            state.current_stage = AgentStage.COMPLETE  # type: ignore


class TestModelSerialization:
    """Tests for model serialization/deserialization."""

    def test_conversation_to_json(self) -> None:
        """Test conversation serializes to JSON correctly."""
        now = datetime.now(timezone.utc)
        conversation = Conversation(
            id="conv-123",
            status=ConversationStatus.ACTIVE,
            title="Test",
            created_at=now,
            updated_at=now,
        )
        json_data = conversation.model_dump_json()
        assert "conv-123" in json_data
        assert "active" in json_data

    def test_conversation_from_json(self) -> None:
        """Test conversation deserializes from dict correctly."""
        now = datetime.now(timezone.utc)
        data = {
            "id": "conv-123",
            "status": "completed",
            "title": "Done",
            "form_document_id": None,
            "source_document_ids": [],
            "filled_pdf_ref": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        conversation = Conversation.model_validate(data)
        assert conversation.id == "conv-123"
        assert conversation.status == ConversationStatus.COMPLETED

    def test_message_roundtrip(self) -> None:
        """Test message serialization roundtrip."""
        now = datetime.now(timezone.utc)
        original = Message(
            id="msg-123",
            role=MessageRole.AGENT,
            content="Test message",
            thinking="Thinking...",
            approval_required=True,
            approval_status=ApprovalStatus.PENDING,
            created_at=now,
        )
        json_data = original.model_dump()
        restored = Message.model_validate(json_data)
        assert restored.id == original.id
        assert restored.role == original.role
        assert restored.content == original.content
        assert restored.thinking == original.thinking
        assert restored.approval_required == original.approval_required
        assert restored.approval_status == original.approval_status
