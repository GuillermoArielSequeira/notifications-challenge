import os
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# Test collection must not require a development .env or use its signing key.
os.environ["JWT_SECRET_KEY"] = "test-only-secret-not-for-production-32-chars"
for name, value in {
    "POSTGRES_USER": "test_user",
    "POSTGRES_PASSWORD": "test_password_local",
    "POSTGRES_DB": "notifications_test",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "5434",
}.items():
    os.environ.setdefault(name, value)

from app.main import app
from app.core.database import get_db


# Base de datos exclusiva para testing.
# Puede sobrescribirse con una variable de entorno en CI.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://test_user:test_password_local"
    "@127.0.0.1:5434/notifications_test"
)

test_url = make_url(TEST_DATABASE_URL)
if test_url.database != "notifications_test" or test_url.host not in {
    "localhost", "127.0.0.1", "::1", "db_test"
}:
    raise RuntimeError("Tests require the local, isolated notifications_test database")
test_engine = create_engine(test_url)


@pytest.fixture(scope="session")
def migrated_database():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with test_engine.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == "notifications_test"
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield
    test_engine.dispose()


@pytest.fixture
def db_session(migrated_database):
    # Application commits release savepoints, not this outer transaction.
    with test_engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()


@pytest.fixture
def db_test_client(db_session):
    """
    Crea un cliente HTTP que utiliza la base
    de datos de testing en lugar de desarrollo.
    """

    def override_get_db():
        yield db_session

    # Reemplazamos la dependencia original.
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        # Restauramos las dependencias originales.
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def auth_headers(db_test_client):
    credentials = {"email": "user@example.com", "password": "secure-test-password"}
    assert db_test_client.post("/api/v1/auth/register", json=credentials).status_code == 201
    response = db_test_client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def authenticated_user_factory(db_test_client):
    def create_user(email: str):
        credentials = {"email": email, "password": "secure-test-password"}
        registration = db_test_client.post("/api/v1/auth/register", json=credentials)
        assert registration.status_code == 201
        login = db_test_client.post("/api/v1/auth/login", json=credentials)
        assert login.status_code == 200
        return {
            "id": UUID(registration.json()["id"]),
            "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
        }

    return create_user
