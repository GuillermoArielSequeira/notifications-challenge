from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.main import app
from app.models.user import User


CREDENTIALS = {"email": "user@example.com", "password": "secure-test-password"}


def test_register(db_test_client, db_session):
    response = db_test_client.post(
        "/api/v1/auth/register",
        json={**CREDENTIALS, "email": " User@EXAMPLE.com "},
    )
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {"id", "email", "created_at"}
    assert UUID(data["id"])
    assert datetime.fromisoformat(data["created_at"]).tzinfo is not None
    assert data["email"] == "user@example.com"
    user = db_session.scalar(select(User).where(User.email == data["email"]))
    assert user.password_hash != CREDENTIALS["password"]
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(CREDENTIALS["password"], user.password_hash)


def test_register_and_login_with_eight_character_password(db_test_client):
    credentials = {**CREDENTIALS, "password": "abcdefgh"}
    assert db_test_client.post("/api/v1/auth/register", json=credentials).status_code == 201
    response = db_test_client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_duplicate_email_and_session_recovery(db_test_client):
    assert db_test_client.post("/api/v1/auth/register", json=CREDENTIALS).status_code == 201
    response = db_test_client.post(
        "/api/v1/auth/register", json={**CREDENTIALS, "email": "USER@example.com"}
    )
    assert response.status_code == 409
    # A constraint violation must not leave the session unusable.
    assert db_test_client.post("/api/v1/auth/login", json=CREDENTIALS).status_code == 200


@pytest.mark.parametrize("changes", [
    {"email": "invalid-email"},
    {"password": "abcdefg"},
    {"password": "x" * 129},
    {"password": None},
])
def test_invalid_registration(changes):
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json={**CREDENTIALS, **changes})
    assert response.status_code == 422
    assert all("input" not in error for error in response.json()["detail"])
    assert CREDENTIALS["password"] not in response.text


def test_login_and_me(db_test_client):
    registered = db_test_client.post("/api/v1/auth/register", json=CREDENTIALS).json()
    response = db_test_client.post(
        "/api/v1/auth/login", json={**CREDENTIALS, "email": "USER@example.com"}
    )
    assert response.status_code == 200
    token = response.json()
    assert token["token_type"] == "bearer"
    assert token["expires_in"] == settings.jwt_access_token_expire_minutes * 60
    claims = jwt.decode(
        token["access_token"], settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"]
    )
    assert claims["sub"] == registered["id"]
    assert claims["exp"] - claims["iat"] == token["expires_in"]
    me = db_test_client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json() == registered


def test_wrong_password_and_unknown_email_are_indistinguishable(db_test_client):
    db_test_client.post("/api/v1/auth/register", json=CREDENTIALS)
    wrong = db_test_client.post(
        "/api/v1/auth/login", json={**CREDENTIALS, "password": "wrong-password"}
    )
    unknown = db_test_client.post(
        "/api/v1/auth/login", json={**CREDENTIALS, "email": "unknown@example.com"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid email or password"}
    assert wrong.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("path", ["/", "/api/v1/ping", "/api/v1/db-check", "/api/v1/users/me"])
@pytest.mark.parametrize("authorization", [None, "Basic abc", "Bearer", "Bearer invalid"])
def test_protected_routes_reject_invalid_credentials(path, authorization):
    headers = {"Authorization": authorization} if authorization else {}
    with TestClient(app) as client:
        response = client.get(path, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("kind", [
    "expired", "wrong-key", "wrong-algorithm", "missing-exp", "missing-iat", "missing-sub",
    "invalid-sub", "future-iat",
])
def test_invalid_tokens(kind):
    now = datetime.now(timezone.utc)
    payload = {"sub": str(uuid4()), "iat": now, "exp": now + timedelta(minutes=5)}
    key = settings.jwt_secret_key.get_secret_value()
    algorithm = "HS256"
    if kind == "expired":
        payload["exp"] = now - timedelta(seconds=10)
    elif kind == "wrong-key":
        key = "a-different-signing-key-of-at-least-32-chars"
    elif kind == "wrong-algorithm":
        algorithm = "HS512"
        key = key * 2
    elif kind.startswith("missing-"):
        del payload[kind.removeprefix("missing-")]
    elif kind == "invalid-sub":
        payload["sub"] = "not-a-uuid"
    elif kind == "future-iat":
        payload["iat"] = now + timedelta(minutes=5)
    token = jwt.encode(payload, key, algorithm=algorithm)
    with TestClient(app) as client:
        response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_for_nonexistent_user(db_test_client):
    token = create_access_token(uuid4())
    response = db_test_client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_deleted_user_token_is_rejected(db_test_client, db_session, auth_headers):
    user = db_session.scalar(select(User).where(User.email == CREDENTIALS["email"]))
    db_session.delete(user)
    db_session.commit()
    assert db_test_client.get("/api/v1/users/me", headers=auth_headers).status_code == 401


def test_migration_matches_models(db_session):
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from app.core.base import Base

    context = MigrationContext.configure(db_session.connection())
    assert compare_metadata(context, Base.metadata) == []
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    assert head is not None
    assert db_session.scalar(text("SELECT version_num FROM alembic_version")) == head
