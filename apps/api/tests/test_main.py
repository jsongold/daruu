"""Tests for main application."""

from fastapi.testclient import TestClient


class TestMainApp:
    """Tests for main FastAPI application."""

    def test_root_endpoint(self, client: TestClient) -> None:
        """Test root endpoint returns app info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data

    def test_health_endpoint(self, client: TestClient) -> None:
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

    def test_docs_endpoint(self, client: TestClient) -> None:
        """Test OpenAPI docs endpoint is accessible."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_endpoint(self, client: TestClient) -> None:
        """Test OpenAPI schema endpoint."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data


class TestErrorHandling:
    """Tests for error handling."""

    def test_validation_error_format(self, client: TestClient, api_prefix: str) -> None:
        """Test that validation errors return proper format."""
        response = client.post(
            f"{api_prefix}/jobs",
            json={},  # Missing required fields
        )
        assert response.status_code == 400 or response.status_code == 422
        data = response.json()
        assert data["success"] is False
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    def test_not_found_error_format(self, client: TestClient, api_prefix: str) -> None:
        """Test that 404 errors return proper format."""
        response = client.get(f"{api_prefix}/jobs/non-existent-id")
        assert response.status_code == 404
        data = response.json()
        assert data["success"] is False
        assert data["error"]["code"] == "NOT_FOUND"
