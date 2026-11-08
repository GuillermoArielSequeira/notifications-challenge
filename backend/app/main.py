from fastapi import APIRouter, Depends, FastAPI
from fastapi.exceptions import RequestValidationError

from app.core.dependencies import get_current_user
from app.core.exception_handlers import validation_error_handler
from app.routers import auth, notifications, system, users
from app.schemas.errors import ValidationErrorResponse


app = FastAPI(
    title="Notification API",
    description="Full Stack Take Home Challenge",
    version="0.1.0",
    responses={422: {
        "model": ValidationErrorResponse,
        "description": "Error de validación de la solicitud",
    }},
    exception_handlers={RequestValidationError: validation_error_handler},
)

# Public auth routes must not inherit the protected API dependency.
app.include_router(auth.router, prefix="/api/v1")
protected_api = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])
protected_api.include_router(system.router, tags=["System"])
protected_api.include_router(users.router)
protected_api.include_router(notifications.router)
app.include_router(protected_api)


@app.get("/", dependencies=[Depends(get_current_user)])
def root():
    return {"message": "Hello World"}

@app.get("/health")
def health():
    return {"status": "ok"}
