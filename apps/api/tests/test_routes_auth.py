"""Tests for authentication routes."""

from fastapi.testclient import TestClient


class TestAuthRoutes:
    """Tests for /auth endpoints."""

    def test_login(self, client: TestClient, api_prefix: str) -> None:
        """Test login endpoint returns token."""
        response = client.post(
            f"{api_prefix}/auth/login",
            json={"username": "testuser", "password": "testpass"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_at" in data

    def test_login_empty_username_fails(self, client: TestClient, api_prefix: str) -> None:
        """Test login with empty username fails."""
        response = client.post(
            f"{api_prefix}/auth/login",
            json={"username": "", "password": "testpass"},
        )
        assert response.status_code == 400

    def test_login_empty_password_fails(self, client: TestClient, api_prefix: str) -> None:
        """Test login with empty password fails."""
        response = client.post(
            f"{api_prefix}/auth/login",
            json={"username": "testuser", "password": ""},
        )
        assert response.status_code == 400

    def test_logout(self, client: TestClient, api_prefix: str) -> None:
        """Test logout endpoint."""
        response = client.post(f"{api_prefix}/auth/logout")
        assert response.status_code == 204

    def test_get_me(self, client: TestClient, api_prefix: str) -> None:
        """Test get current user endpoint."""
        response = client.get(f"{api_prefix}/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "username" in data
        assert "roles" in data
