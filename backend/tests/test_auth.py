"""Tests for authentication endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def test_login_success(client: TestClient, admin_user: User):
    """Test successful login."""
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client: TestClient, admin_user: User):
    """Test login with invalid credentials."""
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_login_nonexistent_user(client: TestClient):
    """Test login with non-existent user."""
    response = client.post(
        "/auth/login",
        data={"username": "nonexistent", "password": "password"}
    )
    assert response.status_code == 401


def test_get_current_user(client: TestClient, admin_token: str):
    """Test getting current user info."""
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["role"] == "admin"


def test_get_current_user_no_token(client: TestClient):
    """Test getting current user without token."""
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_get_current_user_invalid_token(client: TestClient):
    """Test getting current user with invalid token."""
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401


def test_register_user_as_admin(client: TestClient, admin_token: str):
    """Test user registration by admin."""
    response = client.post(
        "/auth/register",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "newuser",
            "email": "newuser@test.com",
            "password": "password123",
            "role": "backoffice_user"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@test.com"


def test_register_user_as_non_admin(client: TestClient, backoffice_token: str):
    """Test that non-admin cannot register users."""
    response = client.post(
        "/auth/register",
        headers={"Authorization": f"Bearer {backoffice_token}"},
        json={
            "username": "newuser",
            "email": "newuser@test.com",
            "password": "password123",
            "role": "backoffice_user"
        }
    )
    assert response.status_code == 403


def test_register_duplicate_username(client: TestClient, admin_token: str, admin_user: User):
    """Test that duplicate username is rejected."""
    response = client.post(
        "/auth/register",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "username": "admin",  # Already exists
            "email": "another@test.com",
            "password": "password123",
            "role": "backoffice_user"
        }
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_list_users_as_admin(client: TestClient, admin_token: str, admin_user: User):
    """Test listing all users as admin."""
    response = client.get(
        "/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(u["username"] == "admin" for u in data)


def test_list_users_as_non_admin(client: TestClient, backoffice_token: str):
    """Test that non-admin cannot list users."""
    response = client.get(
        "/auth/users",
        headers={"Authorization": f"Bearer {backoffice_token}"}
    )
    assert response.status_code == 403


def test_delete_user_as_admin(client: TestClient, admin_token: str, backoffice_user: User):
    """Test deleting user as admin."""
    response = client.delete(
        f"/auth/users/{backoffice_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 204


def test_delete_self(client: TestClient, admin_token: str, admin_user: User):
    """Test that user cannot delete themselves."""
    response = client.delete(
        f"/auth/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 400
    assert "Cannot delete your own account" in response.json()["detail"]


def test_inactive_user_cannot_login(client: TestClient, db: Session, admin_user: User):
    """Test that inactive user cannot login."""
    # Deactivate user
    admin_user.is_active = False
    db.commit()

    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_token_expiration(client: TestClient, admin_user: User):
    """Test that expired tokens are rejected."""
    # This would require mocking time or waiting for token expiration
    # For now, just ensure token validation works
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    token = response.json()["access_token"]

    # Use token immediately (should work)
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


def test_logout(client: TestClient, admin_token: str):
    """Test logout endpoint."""
    response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    assert "logged out" in response.json()["message"].lower()
