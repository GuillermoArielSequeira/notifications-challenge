from sqlalchemy import text

from tests.conftest import test_engine


def test_database_connection(db_test_client):
    """
    Comprueba la conexión con PostgreSQL de testing
    y el funcionamiento del endpoint db-check.
    """

    # Verificamos la base de datos de testing.
    with test_engine.connect() as connection:
        database_name = connection.execute(
            text("SELECT current_database()")
        ).scalar_one()

    assert database_name == "notifications_test"

    # Utilizamos FastAPI con la sesión de testing.
    response = db_test_client.get("/api/v1/db-check")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
    }