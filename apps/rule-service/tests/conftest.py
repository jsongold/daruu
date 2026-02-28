"""Test configuration and fixtures for rule-service."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the rule-service FastAPI app."""
    from app.main import app

    return TestClient(app)
