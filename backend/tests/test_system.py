from fastapi.testclient import TestClient

from app.main import app

# Cliente que permite realizar peticiones HTTP
# a nuestra aplicación sin levantar Uvicorn.
client = TestClient(app)

def test_health():
  """
       Verifica que el endpoint de health responda
  correctamente con HTTP 200.
  """
  response = client.get("/health")

  assert response.status_code == 200
  assert response.json() == {"status": "ok"}


def test_ping(db_test_client, auth_headers):
    """
    Verifica que el router System funcione
    y devuelva la estructura esperada.
    """
    response = db_test_client.get("/api/v1/ping", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"message": "pong"}


def test_root(db_test_client, auth_headers):
    response = db_test_client.get("/", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}


def test_documentation_is_public():
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert schema["paths"]["/api/v1/users/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert "security" not in schema["paths"]["/api/v1/auth/login"]["post"]
