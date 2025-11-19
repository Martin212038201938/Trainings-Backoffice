"""Pytest configuration and fixtures for testing."""

from __future__ import annotations

import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.security import get_password_hash
from app.database import Base
from app.main import app, get_db
from app.models.user import User, UserRole

# Use in-memory SQLite for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """
    Create a fresh database for each test.

    Yields:
        Database session for testing
    """
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """
    Create a test client with database dependency override.

    Args:
        db: Test database session

    Yields:
        FastAPI test client
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db: Session) -> User:
    """
    Create an admin user for testing.

    Args:
        db: Test database session

    Returns:
        Admin user
    """
    user = User(
        username="admin",
        email="admin@test.com",
        hashed_password=get_password_hash("admin123"),
        role=UserRole.ADMIN.value,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def backoffice_user(db: Session) -> User:
    """
    Create a backoffice user for testing.

    Args:
        db: Test database session

    Returns:
        Backoffice user
    """
    user = User(
        username="backoffice",
        email="backoffice@test.com",
        hashed_password=get_password_hash("backoffice123"),
        role=UserRole.BACKOFFICE_USER.value,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def trainer_user(db: Session) -> User:
    """
    Create a trainer user for testing.

    Args:
        db: Test database session

    Returns:
        Trainer user
    """
    user = User(
        username="trainer",
        email="trainer@test.com",
        hashed_password=get_password_hash("trainer123"),
        role=UserRole.TRAINER.value,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(client: TestClient, admin_user: User) -> str:
    """
    Get an authentication token for admin user.

    Args:
        client: Test client
        admin_user: Admin user fixture

    Returns:
        JWT token
    """
    response = client.post(
        "/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def backoffice_token(client: TestClient, backoffice_user: User) -> str:
    """
    Get an authentication token for backoffice user.

    Args:
        client: Test client
        backoffice_user: Backoffice user fixture

    Returns:
        JWT token
    """
    response = client.post(
        "/auth/login",
        data={"username": "backoffice", "password": "backoffice123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def trainer_token(client: TestClient, trainer_user: User) -> str:
    """
    Get an authentication token for trainer user.

    Args:
        client: Test client
        trainer_user: Trainer user fixture

    Returns:
        JWT token
    """
    response = client.post(
        "/auth/login",
        data={"username": "trainer", "password": "trainer123"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token: str) -> dict[str, str]:
    """
    Get authentication headers for requests.

    Args:
        admin_token: Admin JWT token

    Returns:
        Headers dictionary with Authorization
    """
    return {"Authorization": f"Bearer {admin_token}"}


# Configure pytest
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
