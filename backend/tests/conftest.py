import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import get_db


# Base de datos exclusiva para testing.
# Puede sobrescribirse con una variable de entorno en CI.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://test_user:test_password_local"
    "@127.0.0.1:5434/notifications_test"
)

test_engine = create_engine(TEST_DATABASE_URL)

TestSessionLocal = sessionmaker(bind=test_engine)


@pytest.fixture
def db_test_client():
    """
    Crea un cliente HTTP que utiliza la base
    de datos de testing en lugar de desarrollo.
    """

    def override_get_db():
        with TestSessionLocal() as session:
            yield session

    # Reemplazamos la dependencia original.
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        # Restauramos las dependencias originales.
        app.dependency_overrides.pop(get_db, None)