"""Tests for correction REST endpoints."""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _memory_mode(monkeypatch):
    """Force memory mode for all tests."""
    monkeypatch.setenv("DARU_REPOSITORY_MODE", "memory")


@pytest.fixture
def client():
    """Create a test client with fresh singletons."""
    from app.infrastructure.repositories.factory import clear_repository_singletons
    clear_repository_singletons()

    from app.main import create_app
    app = create_app()
    return TestClient(app)


class TestCreateCorrection:
    def test_post_creates_record(self, client):
        response = client.post(
            "/api/v1/corrections",
            json={
                "document_id": "doc-123",
                "field_id": "name",
                "original_value": "John",
                "corrected_value": "Jane",
                "category": "wrong_value",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["document_id"] == "doc-123"
        assert data["data"]["field_id"] == "name"
        assert data["data"]["corrected_value"] == "Jane"

    def test_post_validates_required_fields(self, client):
        response = client.post(
            "/api/v1/corrections",
            json={
                "document_id": "doc-123",
                # missing field_id and corrected_value
            },
        )
        assert response.status_code == 400

    def test_post_with_minimal_fields(self, client):
        response = client.post(
            "/api/v1/corrections",
            json={
                "document_id": "doc-123",
                "field_id": "date",
                "corrected_value": "2024-01-15",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["data"]["category"] == "other"
        assert data["data"]["original_value"] is None


class TestListCorrections:
    def test_get_returns_list(self, client):
        # Create two corrections
        client.post(
            "/api/v1/corrections",
            json={
                "document_id": "doc-abc",
                "field_id": "name",
                "corrected_value": "Fixed",
            },
        )
        client.post(
            "/api/v1/corrections",
            json={
                "document_id": "doc-abc",
                "field_id": "date",
                "corrected_value": "2024-01-01",
            },
        )

        response = client.get("/api/v1/corrections/doc-abc")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 2
        assert data["meta"]["count"] == 2

    def test_get_empty_for_unknown(self, client):
        response = client.get("/api/v1/corrections/nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 0
