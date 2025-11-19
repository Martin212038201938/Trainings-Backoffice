"""Tests for API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Brand, Customer, Trainer, Training
from app.models.user import User


# Health and Version Tests

def test_health_check(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "degraded"]
    assert "database" in data


def test_version_info(client: TestClient):
    """Test version endpoint."""
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data or "git_commit" in data


# Brand Tests

def test_list_brands_authenticated(client: TestClient, auth_headers: dict):
    """Test listing brands with authentication."""
    response = client.get("/brands", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_list_brands_unauthenticated(client: TestClient):
    """Test that unauthenticated users cannot list brands."""
    response = client.get("/brands")
    assert response.status_code == 401


def test_create_brand_as_admin(client: TestClient, admin_token: str, db: Session):
    """Test creating brand as admin."""
    response = client.post(
        "/brands",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Test Brand",
            "slug": "test-brand",
            "default_sender_email": "test@example.com"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Brand"
    assert data["slug"] == "test-brand"


def test_create_brand_as_non_admin(client: TestClient, backoffice_token: str):
    """Test that non-admin cannot create brands."""
    response = client.post(
        "/brands",
        headers={"Authorization": f"Bearer {backoffice_token}"},
        json={
            "name": "Test Brand",
            "slug": "test-brand"
        }
    )
    assert response.status_code == 403


# Customer Tests

def test_list_customers(client: TestClient, auth_headers: dict):
    """Test listing customers."""
    response = client.get("/customers", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_customer_as_backoffice(client: TestClient, backoffice_token: str):
    """Test creating customer as backoffice user."""
    response = client.post(
        "/customers",
        headers={"Authorization": f"Bearer {backoffice_token}"},
        json={
            "company_name": "Test Company",
            "contact_email": "contact@test.com"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["company_name"] == "Test Company"


def test_create_customer_as_trainer(client: TestClient, trainer_token: str):
    """Test that trainer cannot create customers."""
    response = client.post(
        "/customers",
        headers={"Authorization": f"Bearer {trainer_token}"},
        json={
            "company_name": "Test Company",
            "contact_email": "contact@test.com"
        }
    )
    assert response.status_code == 403


# Trainer Tests

def test_list_trainers(client: TestClient, auth_headers: dict):
    """Test listing trainers."""
    response = client.get("/trainers", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_trainer_as_backoffice(client: TestClient, backoffice_token: str):
    """Test creating trainer as backoffice user."""
    response = client.post(
        "/trainers",
        headers={"Authorization": f"Bearer {backoffice_token}"},
        json={
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "John"
    assert data["last_name"] == "Doe"


# Training Tests

def test_list_trainings(client: TestClient, auth_headers: dict):
    """Test listing trainings."""
    response = client.get("/trainings", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_training_requires_backoffice(client: TestClient, trainer_token: str, db: Session):
    """Test that trainer cannot create trainings."""
    # First create brand and customer
    brand = Brand(name="Test Brand", slug="test")
    customer = Customer(company_name="Test Customer")
    db.add(brand)
    db.add(customer)
    db.commit()

    response = client.post(
        "/trainings",
        headers={"Authorization": f"Bearer {trainer_token}"},
        json={
            "title": "Test Training",
            "brand_id": brand.id,
            "customer_id": customer.id,
            "status": "lead"
        }
    )
    assert response.status_code == 403


@pytest.mark.integration
def test_full_training_workflow(client: TestClient, admin_token: str, db: Session):
    """Integration test for complete training workflow."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create brand
    brand_response = client.post(
        "/brands",
        headers=headers,
        json={"name": "Workflow Brand", "slug": "workflow-brand"}
    )
    assert brand_response.status_code == 200
    brand_id = brand_response.json()["id"]

    # 2. Create customer
    customer_response = client.post(
        "/customers",
        headers=headers,
        json={"company_name": "Workflow Customer"}
    )
    assert customer_response.status_code == 200
    customer_id = customer_response.json()["id"]

    # 3. Create trainer
    trainer_response = client.post(
        "/trainers",
        headers=headers,
        json={
            "first_name": "Jane",
            "last_name": "Trainer",
            "email": "jane@example.com"
        }
    )
    assert trainer_response.status_code == 200
    trainer_id = trainer_response.json()["id"]

    # 4. Create training
    training_response = client.post(
        "/trainings",
        headers=headers,
        json={
            "title": "Workflow Training",
            "brand_id": brand_id,
            "customer_id": customer_id,
            "trainer_id": trainer_id,
            "status": "lead",
            "training_type": "online",
            "generate_checklist": False,
            "tasks": []
        }
    )
    assert training_response.status_code == 200
    training_id = training_response.json()["id"]

    # 5. Get training details
    get_response = client.get(f"/trainings/{training_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Workflow Training"

    # 6. Update status
    status_response = client.post(
        f"/trainings/{training_id}/status?status=delivered",
        headers=headers
    )
    assert status_response.status_code == 200

    # 7. Verify update
    verify_response = client.get(f"/trainings/{training_id}", headers=headers)
    assert verify_response.json()["status"] == "delivered"


# Search Tests

def test_search_requires_auth(client: TestClient):
    """Test that search requires authentication."""
    response = client.get("/search?query=test")
    assert response.status_code == 401


def test_search_with_auth(client: TestClient, auth_headers: dict):
    """Test search with authentication."""
    response = client.get("/search?query=test", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "customers" in data
    assert "trainers" in data
    assert "trainings" in data


# Catalog Tests

def test_list_catalog(client: TestClient, auth_headers: dict):
    """Test listing catalog entries."""
    response = client.get("/catalog", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_catalog_entry_as_backoffice(client: TestClient, backoffice_token: str):
    """Test creating catalog entry as backoffice user."""
    response = client.post(
        "/catalog",
        headers={"Authorization": f"Bearer {backoffice_token}"},
        json={
            "title": "Test Course",
            "duration_days": 2,
            "training_type": "online"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Course"


# Task Tests

def test_list_tasks(client: TestClient, auth_headers: dict):
    """Test listing tasks."""
    response = client.get("/tasks", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_task_requires_backoffice(client: TestClient, trainer_token: str):
    """Test that trainer cannot create tasks."""
    response = client.post(
        "/tasks?training_id=1",
        headers={"Authorization": f"Bearer {trainer_token}"},
        json={
            "title": "Test Task",
            "training_id": 1
        }
    )
    assert response.status_code == 403
