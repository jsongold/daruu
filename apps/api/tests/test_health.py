"""Tests for health check endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for the /health liveness endpoint."""

    def test_health_returns_healthy(self, client: TestClient) -> None:
        """Test that health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_health_response_format(self, client: TestClient) -> None:
        """Test health response matches expected schema."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        # Verify all required fields are present
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data

        # Verify status is a valid value
        assert data["status"] in ["healthy", "degraded", "unhealthy"]

        # Verify timestamp is ISO format
        assert "T" in data["timestamp"]  # Basic ISO format check


class TestReadinessEndpoint:
    """Tests for the /health/ready readiness endpoint."""

    def test_readiness_returns_response(self, client: TestClient) -> None:
        """Test that readiness endpoint returns a response."""
        response = client.get("/health/ready")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "components" in data

    def test_readiness_includes_all_components(self, client: TestClient) -> None:
        """Test that readiness check includes all expected components."""
        response = client.get("/health/ready")
        assert response.status_code == 200

        data = response.json()
        component_names = [c["name"] for c in data["components"]]

        # Verify all expected components are checked
        assert "database" in component_names
        assert "llm" in component_names
        assert "storage" in component_names
        assert "job_queue" in component_names

    def test_readiness_component_format(self, client: TestClient) -> None:
        """Test that each component has the expected format."""
        response = client.get("/health/ready")
        assert response.status_code == 200

        data = response.json()
        for component in data["components"]:
            assert "name" in component
            assert "status" in component
            assert component["status"] in ["healthy", "degraded", "unhealthy"]
            # latency_ms and message can be None
            assert "latency_ms" in component
            assert "message" in component

    def test_readiness_storage_check(self, client: TestClient) -> None:
        """Test that storage component is checked."""
        response = client.get("/health/ready")
        assert response.status_code == 200

        data = response.json()
        storage_component = next((c for c in data["components"] if c["name"] == "storage"), None)

        assert storage_component is not None
        # Storage should be healthy in test environment
        assert storage_component["status"] == "healthy"

    def test_readiness_job_queue_check(self, client: TestClient) -> None:
        """Test that job queue component is checked."""
        response = client.get("/health/ready")
        assert response.status_code == 200

        data = response.json()
        job_queue_component = next(
            (c for c in data["components"] if c["name"] == "job_queue"), None
        )

        assert job_queue_component is not None
        # Job queue should be healthy in test environment
        assert job_queue_component["status"] == "healthy"


class TestReadinessWithMocks:
    """Tests for readiness endpoint with mocked dependencies."""

    def test_database_healthy_without_supabase(self, client: TestClient) -> None:
        """Test database shows healthy when using in-memory storage."""
        response = client.get("/health/ready")
        assert response.status_code == 200

        data = response.json()
        db_component = next((c for c in data["components"] if c["name"] == "database"), None)

        assert db_component is not None
        assert db_component["status"] == "healthy"
        assert (
            "in-memory" in db_component["message"].lower()
            or "mock" in db_component["message"].lower()
        )

    def test_llm_degraded_without_api_key(self, client: TestClient) -> None:
        """Test LLM shows degraded when API key is not configured."""
        with patch("app.routes.health.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                app_version="0.1.0",
                openai_api_key=None,
                llm_analyze_mode=None,
                supabase_url=None,
                supabase_key=None,
                supabase_anon_key=None,
                upload_dir=MagicMock(exists=MagicMock(return_value=True)),
            )
            mock_settings.return_value.upload_dir.exists.return_value = True
            mock_settings.return_value.upload_dir.__truediv__ = MagicMock(
                return_value=MagicMock(
                    write_text=MagicMock(),
                    unlink=MagicMock(),
                )
            )

            response = client.get("/health/ready")
            assert response.status_code == 200

            data = response.json()
            llm_component = next((c for c in data["components"] if c["name"] == "llm"), None)

            assert llm_component is not None
            assert llm_component["status"] == "degraded"
            assert "not configured" in llm_component["message"].lower()

    def test_llm_healthy_in_mock_mode(self, client: TestClient) -> None:
        """Test LLM shows healthy when running in mock mode."""
        with patch("app.routes.health.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                app_version="0.1.0",
                openai_api_key="test-key",
                llm_analyze_mode="mock",
                supabase_url=None,
                supabase_key=None,
                supabase_anon_key=None,
                upload_dir=MagicMock(exists=MagicMock(return_value=True)),
            )
            mock_settings.return_value.upload_dir.exists.return_value = True
            mock_settings.return_value.upload_dir.__truediv__ = MagicMock(
                return_value=MagicMock(
                    write_text=MagicMock(),
                    unlink=MagicMock(),
                )
            )

            response = client.get("/health/ready")
            assert response.status_code == 200

            data = response.json()
            llm_component = next((c for c in data["components"] if c["name"] == "llm"), None)

            assert llm_component is not None
            assert llm_component["status"] == "healthy"
            assert "mock" in llm_component["message"].lower()


class TestOverallStatusDetermination:
    """Tests for overall status determination logic."""

    def test_all_healthy_returns_healthy(self, client: TestClient) -> None:
        """Test overall status is healthy when all components are healthy."""
        # In test environment without external services, all should be healthy
        response = client.get("/health/ready")
        assert response.status_code == 200

        data = response.json()

        # If all components are healthy, overall should be healthy
        all_healthy = all(c["status"] == "healthy" for c in data["components"])

        if all_healthy:
            assert data["status"] == "healthy"

    def test_status_valid_values(self, client: TestClient) -> None:
        """Test that overall status is always a valid value."""
        response = client.get("/health/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ["healthy", "degraded", "unhealthy"]


class TestHealthModels:
    """Tests for health check Pydantic models."""

    def test_component_health_model(self) -> None:
        """Test ComponentHealth model creation."""
        from app.models.health import ComponentHealth

        component = ComponentHealth(
            name="test",
            status="healthy",
            latency_ms=10.5,
            message="Test message",
        )

        assert component.name == "test"
        assert component.status == "healthy"
        assert component.latency_ms == 10.5
        assert component.message == "Test message"

    def test_component_health_optional_fields(self) -> None:
        """Test ComponentHealth with optional fields as None."""
        from app.models.health import ComponentHealth

        component = ComponentHealth(
            name="test",
            status="degraded",
            latency_ms=None,
            message=None,
        )

        assert component.name == "test"
        assert component.status == "degraded"
        assert component.latency_ms is None
        assert component.message is None

    def test_health_response_model(self) -> None:
        """Test HealthResponse model creation."""
        from app.models.health import HealthResponse

        response = HealthResponse(
            status="healthy",
            version="1.0.0",
            timestamp="2024-01-01T00:00:00Z",
        )

        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.timestamp == "2024-01-01T00:00:00Z"

    def test_readiness_response_model(self) -> None:
        """Test ReadinessResponse model creation."""
        from app.models.health import ComponentHealth, ReadinessResponse

        component = ComponentHealth(
            name="db",
            status="healthy",
            latency_ms=5.0,
            message="Connected",
        )

        response = ReadinessResponse(
            status="healthy",
            version="1.0.0",
            timestamp="2024-01-01T00:00:00Z",
            components=[component],
        )

        assert response.status == "healthy"
        assert len(response.components) == 1
        assert response.components[0].name == "db"

    def test_models_are_frozen(self) -> None:
        """Test that health models are immutable (frozen)."""
        from app.models.health import ComponentHealth, HealthResponse

        component = ComponentHealth(
            name="test",
            status="healthy",
            latency_ms=10.0,
            message="Test",
        )

        response = HealthResponse(
            status="healthy",
            version="1.0.0",
            timestamp="2024-01-01T00:00:00Z",
        )

        # Attempting to modify should raise an error
        with pytest.raises(Exception):  # ValidationError or similar
            component.name = "modified"

        with pytest.raises(Exception):
            response.status = "modified"
