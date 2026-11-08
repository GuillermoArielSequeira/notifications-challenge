import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.exception_handlers import format_validation_error, validation_error_handler
from app.main import app
from app.schemas.auth import RegisterRequest


@pytest.mark.parametrize("data, expected", [
    ({"email": "not-an-email", "password": "abcdefgh"}, {
        "type": "invalid_email", "field": "email", "message": "Ingresá un email válido.",
    }),
    ({"email": "user@example.com", "password": "abcdefg"}, {
        "type": "password_too_short", "field": "password",
        "message": "La contraseña debe tener al menos 8 caracteres.",
    }),
    ({"email": "user@example.com", "password": "x" * 129}, {
        "type": "password_too_long", "field": "password",
        "message": "La contraseña debe tener como máximo 128 caracteres.",
    }),
    ({"email": "user@example.com", "password": None}, {
        "type": "invalid_type", "field": "password", "message": "Ingresá un texto válido.",
    }),
    ({"email": "user@example.com"}, {
        "type": "required_field", "field": "password", "message": "Este campo es obligatorio.",
    }),
    ({"password": "abcdefgh"}, {
        "type": "required_field", "field": "email", "message": "Este campo es obligatorio.",
    }),
])
def test_registration_validation_format(data, expected):
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 422
    assert response.json() == {"detail": [expected]}
    if isinstance(data.get("password"), str):
        assert data["password"] not in response.text


def test_multiple_validation_errors():
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json={})
    assert response.status_code == 422
    assert response.json() == {"detail": [
        {"type": "required_field", "field": "email", "message": "Este campo es obligatorio."},
        {"type": "required_field", "field": "password", "message": "Este campo es obligatorio."},
    ]}


def test_malformed_json():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register", content='{"password": "private-password",',
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    assert response.json() == {"detail": [{
        "type": "invalid_json", "field": None, "message": "El cuerpo debe contener JSON válido.",
    }]}
    assert "private-password" not in response.text


@pytest.mark.parametrize("data", [[], "private-password", 42])
def test_invalid_body(data):
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 422
    assert response.json() == {"detail": [{
        "type": "invalid_body", "field": None, "message": "El cuerpo debe ser un objeto JSON.",
    }]}


def test_missing_body():
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/register")
    assert response.status_code == 422
    assert response.json() == {"detail": [{
        "type": "required_field", "field": None, "message": "Este campo es obligatorio.",
    }]}


def test_login_password_limit_is_not_registration_limit():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login", json={"email": "user@example.com", "password": ""}
        )
    assert response.status_code == 422
    assert response.json() == {"detail": [{
        "type": "password_too_short", "field": "password",
        "message": "La contraseña debe tener al menos 1 carácter.",
    }]}


class NestedPayload(BaseModel):
    users: list[RegisterRequest]


def test_nested_field_paths():
    test_app = FastAPI(exception_handlers={RequestValidationError: validation_error_handler})

    @test_app.post("/nested")
    def nested(data: NestedPayload):
        return {}

    with TestClient(test_app) as client:
        response = client.post(
            "/nested", json={"users": [{"email": "invalid", "password": "abcdefgh"}]}
        )
    assert response.status_code == 422
    assert response.json() == {"detail": [{
        "type": "invalid_email", "field": "users.0.email", "message": "Ingresá un email válido.",
    }]}


def test_openapi_documents_custom_validation_response():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    for path in ("/api/v1/auth/register", "/api/v1/auth/login"):
        response = schema["paths"][path]["post"]["responses"]["422"]
        assert response["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ValidationErrorResponse"
        }
    item = schema["components"]["schemas"]["ValidationErrorItem"]
    assert set(item["properties"]) == {"type", "field", "message"}
    assert set(item["required"]) == {"type", "field", "message"}


@pytest.mark.parametrize("source", ["query", "path", "header", "cookie"])
def test_field_does_not_include_request_source(source):
    error = format_validation_error({"type": "int_parsing", "loc": (source, "page")})
    assert error.model_dump() == {
        "type": "invalid_integer", "field": "page", "message": "Ingresá un número entero válido.",
    }


def test_unmapped_error_uses_safe_message():
    error = format_validation_error({
        "type": "custom_validation", "loc": ("body", "secret"),
        "input": "sensitive-value", "msg": "invalid sensitive-value",
        "ctx": {"reason": "sensitive-value"},
    })
    assert error.model_dump() == {
        "type": "custom_validation", "field": "secret", "message": "El valor ingresado no es válido.",
    }


def test_length_message_for_other_fields():
    error = format_validation_error({
        "type": "string_too_long", "loc": ("body", "name"), "ctx": {"max_length": 20},
    })
    assert error.model_dump() == {
        "type": "string_too_long", "field": "name",
        "message": "El campo debe tener como máximo 20 caracteres.",
    }


@pytest.mark.parametrize("kind, location, expected_type, message", [
    ("blank_text", ("body", "title"), "blank_text", "El campo no puede contener solo espacios en blanco."),
    ("literal_error", ("body", "channel"), "invalid_channel", "El canal debe ser email, sms o push."),
    ("uuid_parsing", ("path", "notification_id"), "invalid_uuid", "Ingresá un identificador UUID válido."),
    ("uuid_type", ("path", "notification_id"), "invalid_uuid", "Ingresá un identificador UUID válido."),
    ("extra_forbidden", ("body", "user_id"), "unexpected_field", "Este campo no está permitido."),
    ("null_not_allowed", ("body", "content"), "null_not_allowed", "Este campo no admite valores nulos."),
    ("empty_update", ("body",), "empty_update", "Enviá al menos un campo para modificar."),
])
def test_notification_error_messages_are_safe(kind, location, expected_type, message):
    error = format_validation_error({
        "type": kind, "loc": location, "input": "private-notification-content",
        "msg": "internal private-notification-content",
        "ctx": {"reason": "private-notification-content"},
    })
    field = ".".join(str(part) for part in location[1:]) or None
    assert error.model_dump() == {"type": expected_type, "field": field, "message": message}


def test_literal_error_for_other_fields_keeps_generic_message():
    error = format_validation_error({
        "type": "literal_error", "loc": ("body", "other"), "input": "private-value",
    })
    assert error.model_dump() == {
        "type": "literal_error", "field": "other", "message": "El valor ingresado no es válido.",
    }
