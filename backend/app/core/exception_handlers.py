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
    if kind == "literal_error" and name == "channel":
        return ValidationErrorItem(
            type="invalid_channel", field=field, message="El canal debe ser email, sms o push."
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
        "blank_text": ("blank_text", "El campo no puede contener solo espacios en blanco."),
        "uuid_parsing": ("invalid_uuid", "Ingresá un identificador UUID válido."),
        "uuid_type": ("invalid_uuid", "Ingresá un identificador UUID válido."),
        "extra_forbidden": ("unexpected_field", "Este campo no está permitido."),
        "null_not_allowed": ("null_not_allowed", "Este campo no admite valores nulos."),
        "empty_update": ("empty_update", "Enviá al menos un campo para modificar."),
        "invalid_recipient_email": (
            "invalid_recipient_email",
            "Ingresá un email destinatario válido de hasta 254 caracteres.",
        ),
        "invalid_recipient_sms": (
            "invalid_recipient_sms",
            "Ingresá un número con + y entre 8 y 15 dígitos, sin cero inicial.",
        ),
        "invalid_recipient_push": (
            "invalid_recipient_push",
            "Ingresá un token de 1 a 512 caracteres ASCII visibles, sin espacios.",
        ),
        "sms_too_long": (
            "sms_too_long", "El contenido SMS debe tener como máximo 160 caracteres."
        ),
    }
    code, message = messages.get(kind, (kind, "El valor ingresado no es válido."))
    # Never forward Pydantic's input, context, or raw message to the client.
    return ValidationErrorItem(type=code, field=field, message=message)


async def validation_error_handler(request: Request, error: RequestValidationError):
    response = ValidationErrorResponse(
        detail=[format_validation_error(item) for item in error.errors()]
    )
    return JSONResponse(status_code=422, content=response.model_dump())
