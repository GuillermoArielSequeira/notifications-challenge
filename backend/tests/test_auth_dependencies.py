from datetime import datetime, timezone
from unittest.mock import create_autospec
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_auth_service
from app.core.security import decode_access_token
from app.main import app
from app.models.user import User
from app.repositories.users import EmailAlreadyRegisteredError
from app.services.auth import AuthService, InvalidCredentialsError


CREDENTIALS = {"email": "USER@example.com", "password": "secure-test-password"}


@pytest.fixture
def service_client(monkeypatch):
    service = create_autospec(AuthService, instance=True)
    user = User(
        id=uuid4(), email="user@example.com", password_hash="not-a-real-hash",
        created_at=datetime.now(timezone.utc),
    )
    service.register.return_value = user
    service.login.return_value = user

    def unexpected_database_access():
        raise AssertionError("Overriding the service must bypass its database dependency")

    monkeypatch.setitem(app.dependency_overrides, get_db, unexpected_database_access)
    monkeypatch.setitem(app.dependency_overrides, get_auth_service, lambda: service)
    with TestClient(app) as client:
        yield client, service, user


def test_auth_service_provider_uses_injected_session():
    session = create_autospec(Session, instance=True)
    service = get_auth_service(session)
    assert isinstance(service, AuthService)
    assert service.users.session is session


def test_register_uses_injected_service(service_client):
    client, service, user = service_client
    response = client.post("/api/v1/auth/register", json=CREDENTIALS)
    assert response.status_code == 201
    assert response.json()["id"] == str(user.id)
    assert response.json()["email"] == user.email
    assert set(response.json()) == {"id", "email", "created_at"}
    service.register.assert_called_once_with("user@example.com", CREDENTIALS["password"])
    service.login.assert_not_called()


def test_login_uses_injected_service(service_client):
    client, service, user = service_client
    response = client.post("/api/v1/auth/login", json=CREDENTIALS)
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert decode_access_token(response.json()["access_token"]) == user.id
    service.login.assert_called_once_with("user@example.com", CREDENTIALS["password"])
    service.register.assert_not_called()


@pytest.mark.parametrize("operation, error, status, detail", [
    ("register", EmailAlreadyRegisteredError, 409, "Email already registered"),
    ("login", InvalidCredentialsError, 401, "Invalid email or password"),
])
def test_injected_service_errors_preserve_http_contract(
    service_client, operation, error, status, detail
):
    client, service, _ = service_client
    getattr(service, operation).side_effect = error
    response = client.post(f"/api/v1/auth/{operation}", json=CREDENTIALS)
    assert response.status_code == status
    assert response.json() == {"detail": detail}
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"
