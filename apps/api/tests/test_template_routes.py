"""Tests for Template API routes.

Tests API endpoints with TestClient:
- POST /api/v2/templates - create template
- GET /api/v2/templates - list templates
- GET /api/v2/templates/{id} - get template
- DELETE /api/v2/templates/{id} - delete template
- POST /api/v2/templates/match - match templates
- Error responses (404, 422, etc.)
"""

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestTemplateRoutes:
    """Tests for /templates endpoints."""

    @pytest.fixture
    def mock_template_service(self):
        """Create a mock template service."""
        from app.models.template import Template, TemplateBbox, TemplateRule, TemplateMatch

        sample_template = Template(
            id="tpl-001",
            tenant_id="tenant-123",
            name="Test Form",
            form_type="application",
            page_count=2,
            bboxes=[
                TemplateBbox(
                    x=10.0, y=20.0, width=100.0, height=30.0, page=1,
                    field_name="name", field_type="text", label="Full Name"
                )
            ],
            rules=[
                TemplateRule(
                    id="rule-1",
                    field_name="name",
                    rule_type="required",
                    config={},
                )
            ],
            embedding_id="emb-001",
            version=1,
        )

        mock = MagicMock()
        mock.get_template = MagicMock(return_value=sample_template)
        mock.list_templates = MagicMock(return_value=[sample_template])
        mock.save_template = AsyncMock(return_value=sample_template)
        mock.delete_template = AsyncMock(return_value=True)
        mock.search_by_embedding = AsyncMock(return_value=[
            TemplateMatch(template=sample_template, score=0.95, matched_pages=[1])
        ])
        mock.get_rules = MagicMock(return_value=sample_template.rules)
        mock.get_bboxes = MagicMock(return_value=sample_template.bboxes)
        return mock

    @pytest.fixture
    def client_with_mock_service(self, mock_template_service):
        """Create test client with mocked service."""
        from app.main import app
        from app.services.template_service import get_template_service

        app.dependency_overrides[get_template_service] = lambda: mock_template_service
        yield TestClient(app)
        app.dependency_overrides.clear()

    @pytest.fixture
    def api_v2_prefix(self) -> str:
        """Get API v2 prefix for templates."""
        return "/api/v2"

    # =========================================================================
    # Create Template Tests (POST /api/v2/templates)
    # =========================================================================

    def test_create_template(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test creating a template via API."""
        request_data = {
            "name": "New Application Form",
            "form_type": "application",
            "page_count": 2,
            "bboxes": [
                {
                    "x": 10.0,
                    "y": 20.0,
                    "width": 100.0,
                    "height": 30.0,
                    "page": 1,
                    "field_name": "name",
                    "field_type": "text",
                    "label": "Full Name",
                }
            ],
            "rules": [
                {
                    "id": "rule-1",
                    "field_name": "name",
                    "rule_type": "required",
                    "config": {},
                }
            ],
            "description": "Standard application form",
            "tags": ["application", "standard"],
        }

        response = client_with_mock_service.post(
            f"{api_v2_prefix}/templates",
            json=request_data,
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["id"] == "tpl-001"
        mock_template_service.save_template.assert_called_once()

    def test_create_template_minimal(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test creating a minimal template."""
        request_data = {
            "name": "Minimal Form",
            "form_type": "simple",
            "page_count": 1,
        }

        response = client_with_mock_service.post(
            f"{api_v2_prefix}/templates",
            json=request_data,
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 201

    def test_create_template_missing_name_fails(
        self,
        client_with_mock_service: TestClient,
        api_v2_prefix: str,
    ) -> None:
        """Test that missing name field fails validation."""
        request_data = {
            "form_type": "application",
            "page_count": 1,
        }

        response = client_with_mock_service.post(
            f"{api_v2_prefix}/templates",
            json=request_data,
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 422

    def test_create_template_invalid_bbox_fails(
        self,
        client_with_mock_service: TestClient,
        api_v2_prefix: str,
    ) -> None:
        """Test that invalid bbox data fails validation."""
        request_data = {
            "name": "Form",
            "form_type": "test",
            "page_count": 1,
            "bboxes": [
                {
                    "x": 10.0,
                    "y": 20.0,
                    "width": -100.0,  # Invalid: negative width
                    "height": 30.0,
                    "page": 1,
                    "field_name": "name",
                    "field_type": "text",
                }
            ],
        }

        response = client_with_mock_service.post(
            f"{api_v2_prefix}/templates",
            json=request_data,
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 422

    def test_create_template_missing_tenant_fails(
        self,
        client_with_mock_service: TestClient,
        api_v2_prefix: str,
    ) -> None:
        """Test that missing tenant ID fails."""
        request_data = {
            "name": "Form",
            "form_type": "test",
            "page_count": 1,
        }

        response = client_with_mock_service.post(
            f"{api_v2_prefix}/templates",
            json=request_data,
            # No X-Tenant-ID header
        )

        assert response.status_code in [400, 401, 422]

    # =========================================================================
    # List Templates Tests (GET /api/v2/templates)
    # =========================================================================

    def test_list_templates(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test listing templates."""
        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "items" in data["data"]
        assert len(data["data"]["items"]) == 1
        mock_template_service.list_templates.assert_called_once()

    def test_list_templates_with_form_type_filter(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test listing templates with form_type filter."""
        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates?form_type=application",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        mock_template_service.list_templates.assert_called()

    def test_list_templates_empty(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test listing templates when none exist."""
        mock_template_service.list_templates.return_value = []

        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0

    def test_list_templates_pagination(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test listing templates with pagination."""
        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates?limit=10&offset=0",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200

    # =========================================================================
    # Get Template Tests (GET /api/v2/templates/{id})
    # =========================================================================

    def test_get_template(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test getting a single template."""
        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates/tpl-001",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == "tpl-001"
        assert data["data"]["name"] == "Test Form"
        mock_template_service.get_template.assert_called_with("tpl-001")

    def test_get_template_not_found(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test getting a non-existent template."""
        mock_template_service.get_template.return_value = None

        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates/non-existent",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False

    def test_get_template_includes_bboxes(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test that template response includes bboxes."""
        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates/tpl-001",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "bboxes" in data["data"]
        assert len(data["data"]["bboxes"]) == 1
        assert data["data"]["bboxes"][0]["field_name"] == "name"

    def test_get_template_includes_rules(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test that template response includes rules."""
        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates/tpl-001",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "rules" in data["data"]
        assert len(data["data"]["rules"]) == 1
        assert data["data"]["rules"][0]["rule_type"] == "required"

    # =========================================================================
    # Delete Template Tests (DELETE /api/v2/templates/{id})
    # =========================================================================

    def test_delete_template(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test deleting a template."""
        response = client_with_mock_service.delete(
            f"{api_v2_prefix}/templates/tpl-001",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_template_service.delete_template.assert_called_with("tpl-001")

    def test_delete_template_not_found(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test deleting a non-existent template."""
        mock_template_service.delete_template.return_value = False

        response = client_with_mock_service.delete(
            f"{api_v2_prefix}/templates/non-existent",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 404

    # =========================================================================
    # Match Templates Tests (POST /api/v2/templates/match)
    # =========================================================================

    def test_match_templates(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test matching templates with an uploaded document."""
        response = client_with_mock_service.post(
            f"{api_v2_prefix}/templates/match",
            files={"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "matches" in data["data"]
        assert len(data["data"]["matches"]) == 1
        assert data["data"]["matches"][0]["score"] == 0.95
        mock_template_service.search_by_embedding.assert_called()

    def test_match_templates_no_matches(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test matching when no templates match."""
        mock_template_service.search_by_embedding.return_value = []

        response = client_with_mock_service.post(
            f"{api_v2_prefix}/templates/match",
            files={"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["matches"] == []

    def test_match_templates_with_limit(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test matching with result limit."""
        response = client_with_mock_service.post(
            f"{api_v2_prefix}/templates/match?limit=3",
            files={"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200

    def test_match_templates_with_min_score(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
        sample_pdf_content: bytes,
    ) -> None:
        """Test matching with minimum score threshold."""
        response = client_with_mock_service.post(
            f"{api_v2_prefix}/templates/match?min_score=0.8",
            files={"file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")},
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200

    def test_match_templates_no_file_fails(
        self,
        client_with_mock_service: TestClient,
        api_v2_prefix: str,
    ) -> None:
        """Test that matching without a file fails."""
        response = client_with_mock_service.post(
            f"{api_v2_prefix}/templates/match",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code in [400, 422]

    # =========================================================================
    # Get Template Rules Tests (GET /api/v2/templates/{id}/rules)
    # =========================================================================

    def test_get_template_rules(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test getting rules for a template."""
        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates/tpl-001/rules",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["rules"]) == 1

    def test_get_template_rules_not_found(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test getting rules for non-existent template."""
        mock_template_service.get_rules.return_value = None

        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates/non-existent/rules",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 404

    # =========================================================================
    # Get Template Bboxes Tests (GET /api/v2/templates/{id}/bboxes)
    # =========================================================================

    def test_get_template_bboxes(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test getting bboxes for a template."""
        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates/tpl-001/bboxes",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["bboxes"]) == 1
        assert data["data"]["bboxes"][0]["field_name"] == "name"

    def test_get_template_bboxes_by_page(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test getting bboxes filtered by page."""
        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates/tpl-001/bboxes?page=1",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 200

    def test_get_template_bboxes_not_found(
        self,
        client_with_mock_service: TestClient,
        mock_template_service,
        api_v2_prefix: str,
    ) -> None:
        """Test getting bboxes for non-existent template."""
        mock_template_service.get_bboxes.return_value = None

        response = client_with_mock_service.get(
            f"{api_v2_prefix}/templates/non-existent/bboxes",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 404


class TestTemplateRoutesErrorHandling:
    """Tests for error handling in template routes."""

    @pytest.fixture
    def mock_template_service_with_errors(self):
        """Create a mock service that raises errors."""
        mock = MagicMock()
        mock.get_template = MagicMock(side_effect=Exception("Database error"))
        mock.list_templates = MagicMock(side_effect=Exception("Database error"))
        mock.save_template = AsyncMock(side_effect=Exception("Save failed"))
        mock.delete_template = AsyncMock(side_effect=Exception("Delete failed"))
        mock.search_by_embedding = AsyncMock(side_effect=Exception("Search failed"))
        return mock

    @pytest.fixture
    def client_with_error_service(self, mock_template_service_with_errors):
        """Create test client with error-raising service."""
        from app.main import app
        from app.services.template_service import get_template_service

        app.dependency_overrides[get_template_service] = lambda: mock_template_service_with_errors
        yield TestClient(app)
        app.dependency_overrides.clear()

    def test_get_template_internal_error(
        self,
        client_with_error_service: TestClient,
    ) -> None:
        """Test that internal errors are handled gracefully."""
        response = client_with_error_service.get(
            "/api/v2/templates/tpl-001",
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 500
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_create_template_internal_error(
        self,
        client_with_error_service: TestClient,
    ) -> None:
        """Test that creation errors are handled gracefully."""
        response = client_with_error_service.post(
            "/api/v2/templates",
            json={
                "name": "Test",
                "form_type": "test",
                "page_count": 1,
            },
            headers={"X-Tenant-ID": "tenant-123"},
        )

        assert response.status_code == 500
