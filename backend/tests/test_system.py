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


def test_ping():
    """
    Verifica que el router System funcione
    y devuelva la estructura esperada.
    """
    response = client.get("/api/v1/ping")

    assert response.status_code == 200
    assert response.json() == {"message": "pong"}