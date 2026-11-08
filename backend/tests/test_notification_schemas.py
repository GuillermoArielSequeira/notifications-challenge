from itertools import combinations
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exception_handlers import format_validation_error
from app.schemas.notification import (
    NotificationCreateRequest,
    NotificationResponse,
    NotificationUpdateRequest,
)


VALID_DATA = {"title": "Recordatorio", "content": "Contenido de prueba", "channel": "email"}
REQUEST_SCHEMAS = (NotificationCreateRequest, NotificationUpdateRequest)


def request_payload(schema, changes):
    return {**VALID_DATA, **changes} if schema is NotificationCreateRequest else changes


@pytest.mark.parametrize("channel", ["email", "sms", "push"])
def test_create_accepts_each_channel(channel):
    payload = {**VALID_DATA, "channel": channel}
    assert NotificationCreateRequest.model_validate(payload).model_dump() == payload


def test_create_preserves_text_and_significant_whitespace():
    payload = {"title": "  Aviso áéí  ", "content": "\n Texto con espacios \t\n", "channel": "sms"}
    assert NotificationCreateRequest.model_validate(payload).model_dump() == payload


@pytest.mark.parametrize("schema", REQUEST_SCHEMAS)
@pytest.mark.parametrize("field, length", [("title", 1), ("title", 200), ("content", 1), ("content", 5000)])
def test_request_accepts_exact_text_boundaries(schema, field, length):
    value = "á" * length
    data = schema.model_validate(request_payload(schema, {field: value}))
    assert getattr(data, field) == value


@pytest.mark.parametrize("schema", REQUEST_SCHEMAS)
@pytest.mark.parametrize("field, length", [("title", 0), ("title", 201), ("content", 0), ("content", 5001)])
def test_request_rejects_text_outside_boundaries(schema, field, length):
    with pytest.raises(ValidationError) as error:
        schema.model_validate(request_payload(schema, {field: "a" * length}))
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize("schema", REQUEST_SCHEMAS)
@pytest.mark.parametrize("field", ["title", "content"])
@pytest.mark.parametrize("value", [" ", "\t", "\n", " \t\n ", "\u00a0", "\u2003"])
def test_request_rejects_whitespace_only_text(schema, field, value):
    with pytest.raises(ValidationError) as error:
        schema.model_validate(request_payload(schema, {field: value}))
    assert error.value.errors()[0]["type"] == "blank_text"
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize("schema", REQUEST_SCHEMAS)
@pytest.mark.parametrize("field", ["title", "content"])
@pytest.mark.parametrize("value", [None, 42, 3.14, True, [], {}, b"private-text"])
def test_request_rejects_non_string_text_without_coercion(schema, field, value):
    with pytest.raises(ValidationError):
        schema.model_validate(request_payload(schema, {field: value}))


@pytest.mark.parametrize("schema", REQUEST_SCHEMAS)
@pytest.mark.parametrize("channel", [None, "", "fax", "EMAIL", "Sms", " email", "push ", 1, False, ["email"], b"email"])
def test_request_rejects_invalid_channels_without_normalization(schema, channel):
    with pytest.raises(ValidationError) as error:
        schema.model_validate(request_payload(schema, {"channel": channel}))
    assert error.value.errors()[0]["loc"] == ("channel",)


@pytest.mark.parametrize("field", ["title", "content", "channel"])
def test_create_requires_all_fields(field):
    payload = {key: value for key, value in VALID_DATA.items() if key != field}
    with pytest.raises(ValidationError) as error:
        NotificationCreateRequest.model_validate(payload)
    assert error.value.errors()[0]["type"] == "missing"
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize("schema", REQUEST_SCHEMAS)
@pytest.mark.parametrize("field", ["id", "user_id", "unexpected"])
def test_request_rejects_unknown_or_immutable_fields(schema, field):
    payload = request_payload(schema, {"title": "Nuevo título", field: "not-allowed"})
    with pytest.raises(ValidationError) as error:
        schema.model_validate(payload)
    assert any(item["type"] == "extra_forbidden" and item["loc"] == (field,) for item in error.value.errors())


@pytest.mark.parametrize("fields", [subset for size in (1, 2, 3) for subset in combinations(VALID_DATA, size)])
def test_update_only_contains_submitted_fields(fields):
    payload = {key: VALID_DATA[key] for key in fields}
    data = NotificationUpdateRequest.model_validate(payload)
    assert data.model_fields_set == set(fields)
    assert data.model_dump(exclude_unset=True) == payload
    assert data.model_dump(mode="json", exclude_unset=True) == payload


@pytest.mark.parametrize("channel", ["email", "sms", "push"])
def test_update_accepts_each_channel(channel):
    data = NotificationUpdateRequest(channel=channel)
    assert data.model_dump(exclude_unset=True) == {"channel": channel}


def test_update_preserves_text_and_significant_whitespace():
    payload = {"title": "  Nuevo título  ", "content": "\n Contenido \t"}
    assert NotificationUpdateRequest.model_validate(payload).model_dump(exclude_unset=True) == payload


def test_update_rejects_empty_body():
    with pytest.raises(ValidationError) as error:
        NotificationUpdateRequest.model_validate({})
    assert error.value.errors()[0]["type"] == "empty_update"
    assert error.value.errors()[0]["loc"] == ()


@pytest.mark.parametrize("field", ["title", "content", "channel"])
def test_update_rejects_explicit_null_even_with_another_valid_field(field):
    payload = {"title": "Nuevo título", "content": "Nuevo contenido", field: None}
    with pytest.raises(ValidationError) as error:
        NotificationUpdateRequest.model_validate(payload)
    assert any(item["type"] == "null_not_allowed" and item["loc"] == (field,) for item in error.value.errors())


def test_invalid_update_does_not_mutate_input():
    payload = {"title": "Título válido", "content": "x" * 5001}
    original = payload.copy()
    with pytest.raises(ValidationError):
        NotificationUpdateRequest.model_validate(payload)
    assert payload == original


def test_response_only_exposes_public_fields_from_attributes():
    notification_id = uuid4()
    record = SimpleNamespace(id=notification_id, user_id=uuid4(), **VALID_DATA)
    response = NotificationResponse.model_validate(record)
    assert response.model_dump(mode="json") == {"id": str(notification_id), **VALID_DATA}


def test_create_json_schema_documents_required_fields_and_constraints():
    schema = NotificationCreateRequest.model_json_schema()
    assert set(schema["required"]) == {"title", "content", "channel"}
    assert schema["additionalProperties"] is False
    assert schema["properties"]["title"]["minLength"] == 1
    assert schema["properties"]["title"]["maxLength"] == 200
    assert schema["properties"]["content"]["maxLength"] == 5000
    assert schema["properties"]["channel"]["enum"] == ["email", "sms", "push"]


def test_update_json_schema_documents_omittable_but_non_nullable_fields():
    schema = NotificationUpdateRequest.model_json_schema()
    assert not schema.get("required")
    assert schema["additionalProperties"] is False
    assert schema["minProperties"] == 1
    for name in ("title", "content", "channel"):
        field = schema["properties"][name]
        assert field["type"] == "string"
        assert "anyOf" not in field
        assert "default" not in field


@pytest.mark.parametrize("schema, payload, expected", [
    (NotificationCreateRequest, {**VALID_DATA, "title": "  "}, {
        "type": "blank_text", "field": "title",
        "message": "El campo no puede contener solo espacios en blanco.",
    }),
    (NotificationCreateRequest, {**VALID_DATA, "channel": "private-invalid-channel"}, {
        "type": "invalid_channel", "field": "channel",
        "message": "El canal debe ser email, sms o push.",
    }),
    (NotificationUpdateRequest, {"content": None}, {
        "type": "null_not_allowed", "field": "content",
        "message": "Este campo no admite valores nulos.",
    }),
    (NotificationUpdateRequest, {}, {
        "type": "empty_update", "field": None,
        "message": "Enviá al menos un campo para modificar.",
    }),
    (NotificationUpdateRequest, {"title": " \t"}, {
        "type": "blank_text", "field": "title",
        "message": "El campo no puede contener solo espacios en blanco.",
    }),
    (NotificationUpdateRequest, {"channel": "private-invalid-channel"}, {
        "type": "invalid_channel", "field": "channel",
        "message": "El canal debe ser email, sms o push.",
    }),
    (NotificationUpdateRequest, {"title": ""}, {
        "type": "string_too_short", "field": "title",
        "message": "El campo debe tener al menos 1 carácter.",
    }),
])
def test_schema_errors_use_safe_public_contract(schema, payload, expected):
    with pytest.raises(ValidationError) as error:
        schema.model_validate(payload)
    details = [format_validation_error(item).model_dump() for item in error.value.errors()]
    assert details == [expected]
    assert "private-invalid-channel" not in str(details)
