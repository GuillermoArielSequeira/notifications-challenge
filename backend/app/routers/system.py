from fastapi import APIRouter, Depends
from typing import Annotated

from sqlalchemy.orm import Session

from app.schemas.system import PingResponse
from app.core.database import get_db
from sqlalchemy import text


# APIRouter permite agrupar endpoints relacionados.
# Luego se registra en la aplicación principal mediante
# app.include_router().
router = APIRouter()

# Define un endpoint HTTP GET.
# response_model utiliza Pydantic para validar, serializar
# y documentar la estructura de la respuesta.
@router.get("/ping", response_model=PingResponse)
def ping() -> PingResponse:

  return PingResponse(message="pong")


@router.get("/db-check")
def check_database(
    db: Annotated[Session, Depends(get_db)]
) -> dict[str, str]:
    """
    Verifica que FastAPI pueda conectarse a PostgreSQL.

    Utiliza inyección de dependencias para obtener
    una sesión de SQLAlchemy.
    """

    db.execute(text("SELECT 1")).scalar_one()

    return {
        "status": "ok",
        "database": "connected"
    }
