from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.errors import ValidationErrorItem, ValidationErrorResponse


def format_validation_error(error: dict[str, Any]) -> ValidationErrorItem:
    location = error.get("loc", ())
    if location and location[0] in {"body", "query", "path", "header", "cookie"}:
        location = location[1:]
    field = ".".join(str(part) for part in location) or None
    kind = error["type"]
    name = location[-1] if location else None

    if kind == "json_invalid":
        # The numeric location is a JSON character offset, not a field name.
        return ValidationErrorItem(
            type="invalid_json", field=None, message="El cuerpo debe contener JSON válido."
        )
    if kind == "value_error" and name == "email":
        return ValidationErrorItem(
            type="invalid_email", field=field, message="Ingresá un email válido."
        )
    if kind in {"string_too_short", "string_too_long"}:
        too_short = kind == "string_too_short"
        limit = error["ctx"]["min_length" if too_short else "max_length"]
        bound = "al menos" if too_short else "como máximo"
        subject = "La contraseña debe" if name == "password" else "El campo debe"
        unit = "carácter" if limit == 1 else "caracteres"
        code = kind
        if name == "password":
            code = "password_too_short" if too_short else "password_too_long"
        return ValidationErrorItem(
            type=code, field=field,
            message=f"{subject} tener {bound} {limit} {unit}.",
        )

    messages = {
        "missing": ("required_field", "Este campo es obligatorio."),
        "string_type": ("invalid_type", "Ingresá un texto válido."),
        "int_parsing": ("invalid_integer", "Ingresá un número entero válido."),
        "model_attributes_type": ("invalid_body", "El cuerpo debe ser un objeto JSON."),
        "model_type": ("invalid_body", "El cuerpo debe ser un objeto JSON."),
    }
    code, message = messages.get(kind, (kind, "El valor ingresado no es válido."))
    # Never forward Pydantic's input, context, or raw message to the client.
    return ValidationErrorItem(type=code, field=field, message=message)


async def validation_error_handler(request: Request, error: RequestValidationError):
    response = ValidationErrorResponse(
        detail=[format_validation_error(item) for item in error.errors()]
    )
    return JSONResponse(status_code=422, content=response.model_dump())
