from fastapi import APIRouter

from app.schemas.system import PingResponse

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
