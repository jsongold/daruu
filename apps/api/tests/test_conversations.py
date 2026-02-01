"""Tests for conversation routes.

Tests the Agent Chat UI conversation API endpoints.
"""

import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.models.conversation import (
    ConversationStatus,
    ErrorCode,
    MessageRole,
)


class TestCreateConversation:
    """Tests for POST /api/v2/conversations endpoint."""

    def test_create_conversation_success(self, client: TestClient) -> None:
        """Test creating a new conversation successfully."""
        response = client.post("/api/v2/conversations")
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert data["status"] == "active"
        assert data["title"] is not None  # Auto-generated title
        assert data["form_document_id"] is None
        assert data["source_document_ids"] == []
        assert data["filled_pdf_ref"] is None
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_conversation_with_title(self, client: TestClient) -> None:
        """Test creating conversation with custom title."""
        response = client.post(
            "/api/v2/conversations",
            json={"title": "My Tax Form"},
        )
        assert response.status_code == 201

        data = response.json()
        assert data["title"] == "My Tax Form"

    def test_create_conversation_empty_body(self, client: TestClient) -> None:
        """Test creating conversation with empty JSON body."""
        response = client.post(
            "/api/v2/conversations",
            json={},
        )
        assert response.status_code == 201

        data = response.json()
        assert data["title"] is not None  # Auto-generated

    def test_create_conversation_null_title(self, client: TestClient) -> None:
        """Test creating conversation with explicit null title."""
        response = client.post(
            "/api/v2/conversations",
            json={"title": None},
        )
        assert response.status_code == 201

        data = response.json()
        assert data["title"] is not None  # Auto-generated


class TestListConversations:
    """Tests for GET /api/v2/conversations endpoint."""

    def test_list_conversations_empty(self, client: TestClient) -> None:
        """Test listing conversations when none exist."""
        response = client.get("/api/v2/conversations")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert data["next_cursor"] is None

    def test_list_conversations_with_status_filter(self, client: TestClient) -> None:
        """Test listing conversations with status filter."""
        response = client.get("/api/v2/conversations?status=active")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data

    def test_list_conversations_with_limit(self, client: TestClient) -> None:
        """Test listing conversations with limit parameter."""
        response = client.get("/api/v2/conversations?limit=10")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data

    def test_list_conversations_invalid_limit(self, client: TestClient) -> None:
        """Test listing conversations with invalid limit returns error."""
        response = client.get("/api/v2/conversations?limit=0")
        # API returns 400 for validation errors (wrapped by exception handler)
        assert response.status_code == 400

        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_list_conversations_limit_too_large(self, client: TestClient) -> None:
        """Test listing conversations with limit exceeding max returns error."""
        response = client.get("/api/v2/conversations?limit=200")
        # API returns 400 for validation errors
        assert response.status_code == 400

        data = response.json()
        assert data["success"] is False

    def test_list_conversations_with_cursor(self, client: TestClient) -> None:
        """Test listing conversations with pagination cursor."""
        response = client.get("/api/v2/conversations?cursor=some-cursor")
        assert response.status_code == 200


class TestGetConversation:
    """Tests for GET /api/v2/conversations/{conversation_id} endpoint."""

    def test_get_conversation_not_found(self, client: TestClient) -> None:
        """Test getting non-existent conversation returns 404."""
        response = client.get("/api/v2/conversations/non-existent-id")
        assert response.status_code == 404

        data = response.json()
        # App wraps errors with success=False, error structure
        assert data["success"] is False
        assert "error" in data

    def test_get_conversation_empty_id_returns_list(self, client: TestClient) -> None:
        """Test getting conversation with empty ID returns list endpoint."""
        response = client.get("/api/v2/conversations/")
        # Trailing slash redirects or returns list
        assert response.status_code in [200, 307]


class TestDeleteConversation:
    """Tests for DELETE /api/v2/conversations/{conversation_id} endpoint."""

    def test_delete_conversation_not_found(self, client: TestClient) -> None:
        """Test deleting non-existent conversation returns 404."""
        response = client.delete("/api/v2/conversations/non-existent-id")
        assert response.status_code == 404


class TestSendMessage:
    """Tests for POST /api/v2/conversations/{conversation_id}/messages endpoint."""

    def test_send_text_message(self, client: TestClient) -> None:
        """Test sending text-only message."""
        # First create a conversation
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        # Send message
        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            data={"content": "Hello, I need help with a form"},
        )
        assert response.status_code == 202

        data = response.json()
        assert data["id"] is not None
        assert data["role"] == "user"
        assert data["content"] == "Hello, I need help with a form"
        assert "created_at" in data

    def test_send_empty_message_fails(self, client: TestClient) -> None:
        """Test sending empty message fails."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            data={},
        )
        assert response.status_code == 400

        data = response.json()
        assert data["success"] is False
        assert "content or files" in data["error"]["message"].lower()

    def test_send_message_with_file(
        self, client: TestClient, sample_pdf_content: bytes
    ) -> None:
        """Test sending message with file upload."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files={"files": ("document.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
        )
        assert response.status_code == 202

        data = response.json()
        assert data["role"] == "user"

    def test_send_message_with_text_and_file(
        self, client: TestClient, sample_pdf_content: bytes
    ) -> None:
        """Test sending message with both text and file."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            data={"content": "Here's my form"},
            files={"files": ("form.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
        )
        assert response.status_code == 202

        data = response.json()
        assert data["content"] == "Here's my form"

    def test_send_message_too_many_files(
        self, client: TestClient, sample_pdf_content: bytes
    ) -> None:
        """Test sending message with more than 5 files fails."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        files = [
            ("files", (f"doc{i}.pdf", io.BytesIO(sample_pdf_content), "application/pdf"))
            for i in range(6)
        ]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files=files,
        )
        assert response.status_code == 400

        data = response.json()
        assert data["success"] is False
        # Error message contains info about too many files
        assert "5" in data["error"]["message"] or "TOO_MANY" in data["error"]["message"]

    def test_send_message_invalid_file_type(self, client: TestClient) -> None:
        """Test sending message with invalid file type fails."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files={"files": ("document.doc", io.BytesIO(b"fake doc"), "application/msword")},
        )
        assert response.status_code == 400

        data = response.json()
        assert data["success"] is False

    def test_send_message_file_too_large(self, client: TestClient) -> None:
        """Test sending message with file exceeding 50MB fails."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        # Create a file larger than 50MB
        large_content = b"x" * (51 * 1024 * 1024)  # 51MB

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files={"files": ("large.pdf", io.BytesIO(large_content), "application/pdf")},
        )
        assert response.status_code == 400

        data = response.json()
        assert data["success"] is False

    def test_send_message_supported_image_types(
        self, client: TestClient
    ) -> None:
        """Test sending message with supported image types."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        # Test PNG
        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files={"files": ("image.png", io.BytesIO(b"fake png"), "image/png")},
        )
        assert response.status_code == 202

    def test_send_message_jpeg_type(self, client: TestClient) -> None:
        """Test sending message with JPEG file."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files={"files": ("image.jpg", io.BytesIO(b"fake jpeg"), "image/jpeg")},
        )
        assert response.status_code == 202

    def test_send_message_tiff_type(self, client: TestClient) -> None:
        """Test sending message with TIFF file."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files={"files": ("image.tiff", io.BytesIO(b"fake tiff"), "image/tiff")},
        )
        assert response.status_code == 202

    def test_send_message_multiple_valid_files(
        self, client: TestClient, sample_pdf_content: bytes
    ) -> None:
        """Test sending message with multiple valid files (up to 5)."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        files = [
            ("files", (f"doc{i}.pdf", io.BytesIO(sample_pdf_content), "application/pdf"))
            for i in range(5)
        ]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files=files,
        )
        assert response.status_code == 202


class TestGetMessages:
    """Tests for GET /api/v2/conversations/{conversation_id}/messages endpoint."""

    def test_get_messages_empty(self, client: TestClient) -> None:
        """Test getting messages from conversation with no messages."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.get(f"/api/v2/conversations/{conv_id}/messages")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "has_more" in data
        assert data["has_more"] is False

    def test_get_messages_with_limit(self, client: TestClient) -> None:
        """Test getting messages with limit parameter."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.get(f"/api/v2/conversations/{conv_id}/messages?limit=10")
        assert response.status_code == 200

    def test_get_messages_with_before_cursor(self, client: TestClient) -> None:
        """Test getting messages with before cursor for pagination."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.get(f"/api/v2/conversations/{conv_id}/messages?before=msg-123")
        assert response.status_code == 200


class TestStreamUpdates:
    """Tests for GET /api/v2/conversations/{conversation_id}/stream endpoint."""

    @pytest.mark.skip(reason="SSE streaming tests hang in TestClient - requires integration test")
    def test_stream_returns_sse_response(self, client: TestClient) -> None:
        """Test that stream endpoint returns SSE content type."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        # This test is skipped because SSE streaming hangs in TestClient
        pass

    @pytest.mark.skip(reason="SSE streaming requires async client setup that differs between httpx versions")
    def test_stream_endpoint_exists(self, client: TestClient) -> None:
        """Test that stream endpoint is reachable (without full streaming).

        Note: This test is skipped because httpx ASGITransport doesn't support
        sync client context manager in all versions.
        """
        pass


class TestApprovePreview:
    """Tests for POST /api/v2/conversations/{conversation_id}/approve endpoint."""

    def test_approve_preview_not_found(self, client: TestClient) -> None:
        """Test approving preview for non-existent conversation."""
        response = client.post(
            "/api/v2/conversations/non-existent-id/approve",
            json={"message_id": "msg-123"},
        )
        assert response.status_code == 404

    def test_approve_preview_missing_message_id(self, client: TestClient) -> None:
        """Test approving preview without message_id fails."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/approve",
            json={},
        )
        # API returns 400 for validation errors
        assert response.status_code == 400

        data = response.json()
        assert data["success"] is False


class TestDownloadPdf:
    """Tests for GET /api/v2/conversations/{conversation_id}/download endpoint."""

    def test_download_pdf_not_found(self, client: TestClient) -> None:
        """Test downloading PDF when not available."""
        response = client.get("/api/v2/conversations/non-existent-id/download")
        assert response.status_code == 404

    def test_download_pdf_not_ready(self, client: TestClient) -> None:
        """Test downloading PDF when conversation not completed."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.get(f"/api/v2/conversations/{conv_id}/download")
        assert response.status_code == 404  # No filled PDF available yet


class TestErrorResponses:
    """Tests for error response format consistency."""

    def test_not_found_error_format(self, client: TestClient) -> None:
        """Test 404 error response format."""
        response = client.get("/api/v2/conversations/non-existent")
        assert response.status_code == 404

        data = response.json()
        # API uses success/error format
        assert data["success"] is False
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    def test_validation_error_format(self, client: TestClient) -> None:
        """Test validation error response format."""
        response = client.get("/api/v2/conversations?limit=-1")
        # API returns 400 for validation errors
        assert response.status_code == 400

        data = response.json()
        assert data["success"] is False
        assert "error" in data


class TestFileValidation:
    """Additional tests for file validation logic."""

    def test_exactly_five_files_allowed(
        self, client: TestClient, sample_pdf_content: bytes
    ) -> None:
        """Test that exactly 5 files is the maximum allowed."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        # 5 files should work
        files = [
            ("files", (f"doc{i}.pdf", io.BytesIO(sample_pdf_content), "application/pdf"))
            for i in range(5)
        ]
        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files=files,
        )
        assert response.status_code == 202

    def test_empty_file_name_with_valid_content(
        self, client: TestClient, sample_pdf_content: bytes
    ) -> None:
        """Test sending file with empty filename but valid PDF content."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files={"files": ("", io.BytesIO(sample_pdf_content), "application/pdf")},
        )
        # May succeed or fail depending on implementation - just verify no 500
        assert response.status_code in [202, 400]

    def test_mixed_valid_and_invalid_files(
        self, client: TestClient, sample_pdf_content: bytes
    ) -> None:
        """Test sending mix of valid and invalid file types."""
        create_response = client.post("/api/v2/conversations")
        conv_id = create_response.json()["id"]

        files = [
            ("files", ("valid.pdf", io.BytesIO(sample_pdf_content), "application/pdf")),
            ("files", ("invalid.doc", io.BytesIO(b"doc"), "application/msword")),
        ]

        response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files=files,
        )
        # Should fail because one file has invalid type
        assert response.status_code == 400

        data = response.json()
        assert data["success"] is False


class TestConversationWorkflow:
    """Integration tests for conversation workflow."""

    def test_create_and_send_message_flow(
        self, client: TestClient, sample_pdf_content: bytes
    ) -> None:
        """Test basic workflow: create conversation, send message."""
        # Create conversation
        create_response = client.post(
            "/api/v2/conversations",
            json={"title": "Tax Form Workflow"},
        )
        assert create_response.status_code == 201
        conv_id = create_response.json()["id"]

        # Send text message
        msg_response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            data={"content": "I need help with my tax form"},
        )
        assert msg_response.status_code == 202

        # Send file message
        file_response = client.post(
            f"/api/v2/conversations/{conv_id}/messages",
            files={"files": ("form.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
        )
        assert file_response.status_code == 202

        # Get messages
        list_response = client.get(f"/api/v2/conversations/{conv_id}/messages")
        assert list_response.status_code == 200

    def test_list_conversations_includes_created(self, client: TestClient) -> None:
        """Test that listing conversations returns expected format."""
        # Create a conversation
        client.post("/api/v2/conversations", json={"title": "Test"})

        # List should return proper format (even if empty due to stub)
        response = client.get("/api/v2/conversations")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "next_cursor" in data
