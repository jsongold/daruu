"""Tests for Edit Routes (API endpoints).

Tests the HTTP API endpoints for edit operations.
Validates request/response contracts, status codes, and error handling.
Phase 3: Edit & Adjust feature.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# Create a minimal test app for edit routes testing
def create_test_app() -> FastAPI:
    """Create a test FastAPI app with edit routes."""
    from typing import List

    from fastapi import APIRouter, HTTPException, Body
    from pydantic import BaseModel

    class BatchEditItem(BaseModel):
        field_id: str
        value: str

    class BatchEditBody(BaseModel):
        edits: List[BatchEditItem]

    app = FastAPI()
    router = APIRouter(prefix="/api/v2/conversations/{conversation_id}")

    # Mock service
    mock_service = MagicMock()

    @router.patch("/fields/{field_id}")
    def update_field(conversation_id: str, field_id: str, value: str, source: str = "inline"):
        """Update a single field value."""
        result = mock_service.apply_edit(conversation_id, field_id, value, source)
        if not result["success"]:
            if result.get("error_code") == "CONVERSATION_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result)
            if result.get("error_code") == "FIELD_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result)
            if result.get("error_code") == "FIELD_NOT_EDITABLE":
                raise HTTPException(status_code=422, detail=result)
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.patch("/fields")
    def update_fields_batch(conversation_id: str, body: BatchEditBody = Body(...)):
        """Update multiple fields at once."""
        result = mock_service.apply_batch_edits(conversation_id, body.edits)
        if not result["success"]:
            if result.get("error_code") == "CONVERSATION_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result)
            # Partial failures return 200 with success=False
        return result

    @router.post("/undo")
    def undo_edit(conversation_id: str):
        """Undo the last edit."""
        result = mock_service.undo(conversation_id)
        if not result["success"]:
            if result.get("error_code") == "CONVERSATION_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result)
            if result.get("error_code") == "NOTHING_TO_UNDO":
                raise HTTPException(status_code=400, detail=result)
        return result

    @router.post("/redo")
    def redo_edit(conversation_id: str):
        """Redo the last undone edit."""
        result = mock_service.redo(conversation_id)
        if not result["success"]:
            if result.get("error_code") == "CONVERSATION_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result)
            if result.get("error_code") == "NOTHING_TO_REDO":
                raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/fields")
    def get_all_fields(conversation_id: str):
        """Get all field values."""
        result = mock_service.get_all_field_values(conversation_id)
        if not result.get("success", True):
            if result.get("error_code") == "CONVERSATION_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result)
        return result

    @router.get("/edit-history")
    def get_edit_history(conversation_id: str):
        """Get edit history for conversation."""
        result = mock_service.get_edit_history(conversation_id)
        if not result.get("success", True):
            if result.get("error_code") == "CONVERSATION_NOT_FOUND":
                raise HTTPException(status_code=404, detail=result)
        return result

    app.include_router(router)
    app._mock_service = mock_service
    return app


@pytest.fixture
def app() -> FastAPI:
    """Create test app."""
    return create_test_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_service(app: FastAPI) -> MagicMock:
    """Get mock service from app."""
    return app._mock_service


class TestUpdateSingleField:
    """Tests for PATCH /fields/{field_id} endpoint."""

    def test_update_field_success(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test successful field update returns 200."""
        mock_service.apply_edit.return_value = {
            "success": True,
            "field_id": "name",
            "old_value": "Old",
            "new_value": "New",
            "can_undo": True,
            "can_redo": False,
            "message": "Updated name to New",
        }

        response = client.patch(
            "/api/v2/conversations/conv-001/fields/name",
            params={"value": "New"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["field_id"] == "name"
        assert data["new_value"] == "New"

    def test_update_field_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test update non-existent field returns 404."""
        mock_service.apply_edit.return_value = {
            "success": False,
            "error_code": "FIELD_NOT_FOUND",
            "error_message": "Field not found",
        }

        response = client.patch(
            "/api/v2/conversations/conv-001/fields/nonexistent",
            params={"value": "Value"},
        )

        assert response.status_code == 404

    def test_update_field_not_editable(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test update read-only field returns 422."""
        mock_service.apply_edit.return_value = {
            "success": False,
            "error_code": "FIELD_NOT_EDITABLE",
            "error_message": "Field is read-only",
        }

        response = client.patch(
            "/api/v2/conversations/conv-001/fields/readonly",
            params={"value": "Value"},
        )

        assert response.status_code == 422

    def test_update_field_conversation_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test update with non-existent conversation returns 404."""
        mock_service.apply_edit.return_value = {
            "success": False,
            "error_code": "CONVERSATION_NOT_FOUND",
            "error_message": "Conversation not found",
        }

        response = client.patch(
            "/api/v2/conversations/nonexistent/fields/name",
            params={"value": "Value"},
        )

        assert response.status_code == 404


class TestBatchUpdate:
    """Tests for PATCH /fields endpoint (batch update)."""

    def test_batch_update_success(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test successful batch update returns 200."""
        mock_service.apply_batch_edits.return_value = {
            "success": True,
            "results": [
                {"success": True, "field_id": "name", "new_value": "John"},
                {"success": True, "field_id": "email", "new_value": "john@example.com"},
            ],
            "summary": "Updated 2 of 2 fields",
        }

        response = client.patch(
            "/api/v2/conversations/conv-001/fields",
            json={
                "edits": [
                    {"field_id": "name", "value": "John"},
                    {"field_id": "email", "value": "john@example.com"},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_batch_update_partial_failure(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test batch with some failures still returns 200."""
        mock_service.apply_batch_edits.return_value = {
            "success": False,
            "results": [
                {"success": True, "field_id": "name", "new_value": "John"},
                {"success": False, "field_id": "invalid", "error_code": "FIELD_NOT_FOUND"},
            ],
            "summary": "Updated 1 of 2 fields",
        }

        response = client.patch(
            "/api/v2/conversations/conv-001/fields",
            json={
                "edits": [
                    {"field_id": "name", "value": "John"},
                    {"field_id": "invalid", "value": "Value"},
                ]
            },
        )

        # Partial failure returns 200 with success=False in body
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_batch_update_conversation_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test batch with non-existent conversation returns 404."""
        mock_service.apply_batch_edits.return_value = {
            "success": False,
            "error_code": "CONVERSATION_NOT_FOUND",
            "error_message": "Conversation not found",
            "results": [],
        }

        response = client.patch(
            "/api/v2/conversations/nonexistent/fields",
            json={"edits": [{"field_id": "name", "value": "John"}]},
        )

        assert response.status_code == 404


class TestUndo:
    """Tests for POST /undo endpoint."""

    def test_undo_success(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test successful undo returns 200."""
        mock_service.undo.return_value = {
            "success": True,
            "action": "undo",
            "edits_reverted": [{"field_id": "name", "old_value": "Old", "new_value": "New"}],
            "can_undo": False,
            "can_redo": True,
        }

        response = client.post("/api/v2/conversations/conv-001/undo")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "undo"

    def test_undo_nothing_to_undo(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test undo with empty history returns 400."""
        mock_service.undo.return_value = {
            "success": False,
            "error_code": "NOTHING_TO_UNDO",
            "error_message": "No edits to undo",
        }

        response = client.post("/api/v2/conversations/conv-001/undo")

        assert response.status_code == 400

    def test_undo_conversation_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test undo with non-existent conversation returns 404."""
        mock_service.undo.return_value = {
            "success": False,
            "error_code": "CONVERSATION_NOT_FOUND",
            "error_message": "Conversation not found",
        }

        response = client.post("/api/v2/conversations/nonexistent/undo")

        assert response.status_code == 404


class TestRedo:
    """Tests for POST /redo endpoint."""

    def test_redo_success(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test successful redo returns 200."""
        mock_service.redo.return_value = {
            "success": True,
            "action": "redo",
            "edits_reverted": [{"field_id": "name", "old_value": "Old", "new_value": "New"}],
            "can_undo": True,
            "can_redo": False,
        }

        response = client.post("/api/v2/conversations/conv-001/redo")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "redo"

    def test_redo_nothing_to_redo(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test redo at end of history returns 400."""
        mock_service.redo.return_value = {
            "success": False,
            "error_code": "NOTHING_TO_REDO",
            "error_message": "No edits to redo",
        }

        response = client.post("/api/v2/conversations/conv-001/redo")

        assert response.status_code == 400

    def test_redo_conversation_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test redo with non-existent conversation returns 404."""
        mock_service.redo.return_value = {
            "success": False,
            "error_code": "CONVERSATION_NOT_FOUND",
            "error_message": "Conversation not found",
        }

        response = client.post("/api/v2/conversations/nonexistent/redo")

        assert response.status_code == 404


class TestGetAllFields:
    """Tests for GET /fields endpoint."""

    def test_get_all_fields_success(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test getting all fields returns 200."""
        mock_service.get_all_field_values.return_value = {
            "success": True,
            "conversation_id": "conv-001",
            "fields": [
                {"field_id": "name", "value": "John", "source": "inline"},
                {"field_id": "email", "value": "john@example.com", "source": "extracted"},
            ],
            "can_undo": True,
            "can_redo": False,
        }

        response = client.get("/api/v2/conversations/conv-001/fields")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["fields"]) == 2

    def test_get_all_fields_empty(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test getting fields when none exist returns empty list."""
        mock_service.get_all_field_values.return_value = {
            "success": True,
            "conversation_id": "conv-001",
            "fields": [],
            "can_undo": False,
            "can_redo": False,
        }

        response = client.get("/api/v2/conversations/conv-001/fields")

        assert response.status_code == 200
        data = response.json()
        assert data["fields"] == []

    def test_get_all_fields_conversation_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test getting fields with non-existent conversation returns 404."""
        mock_service.get_all_field_values.return_value = {
            "success": False,
            "error_code": "CONVERSATION_NOT_FOUND",
            "fields": [],
        }

        response = client.get("/api/v2/conversations/nonexistent/fields")

        assert response.status_code == 404


class TestGetEditHistory:
    """Tests for GET /edit-history endpoint."""

    def test_get_edit_history_success(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test getting edit history returns 200."""
        mock_service.get_edit_history.return_value = {
            "success": True,
            "conversation_id": "conv-001",
            "history": {
                "edits": [
                    {"field_id": "name", "old_value": None, "new_value": "John"},
                    {"field_id": "name", "old_value": "John", "new_value": "Jane"},
                ],
                "current_index": 1,
            },
            "total_edits": 2,
        }

        response = client.get("/api/v2/conversations/conv-001/edit-history")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_edits"] == 2

    def test_get_edit_history_empty(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test getting empty history returns empty list."""
        mock_service.get_edit_history.return_value = {
            "success": True,
            "conversation_id": "conv-001",
            "history": {"edits": [], "current_index": -1},
            "total_edits": 0,
        }

        response = client.get("/api/v2/conversations/conv-001/edit-history")

        assert response.status_code == 200
        data = response.json()
        assert data["total_edits"] == 0

    def test_get_edit_history_conversation_not_found(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test getting history with non-existent conversation returns 404."""
        mock_service.get_edit_history.return_value = {
            "success": False,
            "error_code": "CONVERSATION_NOT_FOUND",
        }

        response = client.get("/api/v2/conversations/nonexistent/edit-history")

        assert response.status_code == 404


class TestErrorResponses:
    """Tests for error response format consistency."""

    def test_error_response_has_code_and_message(
        self, client: TestClient, mock_service: MagicMock
    ) -> None:
        """Test error responses include code and message."""
        mock_service.apply_edit.return_value = {
            "success": False,
            "error_code": "FIELD_NOT_FOUND",
            "error_message": "Field 'name' not found",
        }

        response = client.patch(
            "/api/v2/conversations/conv-001/fields/name",
            params={"value": "Value"},
        )

        assert response.status_code == 404
        data = response.json()["detail"]
        assert "error_code" in data
        assert "error_message" in data
