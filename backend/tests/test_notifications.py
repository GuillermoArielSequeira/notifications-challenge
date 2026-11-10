import io
import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, call, create_autospec, patch
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Enum, String, Uuid, insert, inspect, select, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.core.base import Base
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, get_notification_sender, get_notification_service
from app.core.security import create_access_token
from app.main import app
from app.models import User
from app.repositories.notifications import NotificationRepository
from app.schemas.notification import NotificationResponse
from app.services.delivery.email import EmailDeliveryStrategy
from app.services.delivery.logging import DeliveryLogHandler, DeliveryRecorder
from app.services.delivery.push import PushDeliveryStrategy
from app.services.delivery.sender import DeliveryExecutionError, NotificationSender
from app.services.delivery.sms import SmsDeliveryStrategy
from app.services.notifications import NotificationNotFoundError, NotificationService


def test_notification_schema_matches_migration(db_session):
    inspector = inspect(db_session.connection())
    assert inspector.has_table("notifications")
    assert db_session.scalar(text("SELECT current_database()")) == "notifications_test"

    columns = {column["name"]: column for column in inspector.get_columns("notifications")}
    assert set(columns) == {"id", "user_id", "title", "content", "channel"}
    assert all(column["nullable"] is False for column in columns.values())
    assert isinstance(columns["id"]["type"], Uuid)
    assert isinstance(columns["user_id"]["type"], Uuid)
    for name, length in (("title", 200), ("content", 5000), ("channel", 5)):
        assert isinstance(columns[name]["type"], String)
        assert columns[name]["type"].length == length
    assert not isinstance(columns["channel"]["type"], Enum)

    assert inspector.get_pk_constraint("notifications")["constrained_columns"] == ["id"]
    foreign_keys = inspector.get_foreign_keys("notifications")
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["constrained_columns"] == ["user_id"]
    assert foreign_keys[0]["referred_table"] == "users"
    assert foreign_keys[0]["referred_columns"] == ["id"]
    assert any(
        index["name"] == "ix_notifications_user_id" and index["column_names"] == ["user_id"]
        for index in inspector.get_indexes("notifications")
    )
    assert {check["name"] for check in inspector.get_check_constraints("notifications")} == {
        "ck_notifications_channel"
    }
    assert {column["name"] for column in inspector.get_columns("users")} == {
        "id", "email", "password_hash", "created_at"
    }


@pytest.fixture
def notification_model():
    from app.models import Notification

    return Notification


@pytest.fixture
def notification_owner(db_session):
    user = User(email="notification-model@example.com", password_hash="test-only-placeholder-hash")
    db_session.add(user)
    db_session.flush()
    return user


def test_notification_model_is_registered(notification_model):
    assert Base.metadata.tables["notifications"] is notification_model.__table__
    assert notification_model.metadata is User.metadata


@pytest.mark.parametrize("channel", ["email", "sms", "push"])
@pytest.mark.parametrize("title, content", [
    ("a", "b"),
    ("á" * 200, "ó" * 5000),
    ("  Título  ", "\n Contenido con espacios \t"),
])
def test_notification_model_persists_valid_values(
    db_session, notification_model, notification_owner, channel, title, content
):
    notification = notification_model(
        user_id=notification_owner.id, title=title, content=content, channel=channel
    )
    db_session.add(notification)
    db_session.flush()
    db_session.refresh(notification)

    assert isinstance(notification.id, UUID)
    assert notification.user_id == notification_owner.id
    assert NotificationResponse.model_validate(notification).model_dump(mode="json") == {
        "id": str(notification.id), "title": title, "content": content, "channel": channel,
    }


def test_notification_ids_are_generated_and_unique(db_session, notification_model, notification_owner):
    records = [
        notification_model(
            user_id=notification_owner.id, title="Aviso", content="Contenido", channel="email"
        )
        for _ in range(2)
    ]
    db_session.add_all(records)
    db_session.flush()
    assert all(isinstance(record.id, UUID) for record in records)
    assert records[0].id != records[1].id


@pytest.mark.parametrize("changes, sqlstate", [
    ({"id": None}, "23502"),
    ({"user_id": None}, "23502"),
    ({"title": None}, "23502"),
    ({"content": None}, "23502"),
    ({"channel": None}, "23502"),
    ({"user_id": uuid4()}, "23503"),
    ({"title": "a" * 201}, "22001"),
    ({"content": "a" * 5001}, "22001"),
    ({"channel": "fax"}, "23514"),
    ({"channel": "EMAIL"}, "23514"),
    ({"channel": ""}, "23514"),
])
def test_notification_table_rejects_invalid_values(
    db_session, notification_model, notification_owner, changes, sqlstate
):
    values = {
        "id": uuid4(), "user_id": notification_owner.id,
        "title": "Título", "content": "Contenido", "channel": "email",
        **changes,
    }
    with pytest.raises(DBAPIError) as error:
        with db_session.begin_nested():
            # Core insertion bypasses request validation to exercise DB constraints.
            db_session.execute(insert(notification_model.__table__).values(**values))
    assert error.value.orig.sqlstate == sqlstate
    assert db_session.scalar(text("SELECT 1")) == 1


def test_notification_table_rejects_duplicate_id(db_session, notification_model, notification_owner):
    values = {
        "id": uuid4(), "user_id": notification_owner.id,
        "title": "Título", "content": "Contenido", "channel": "sms",
    }
    table = notification_model.__table__
    db_session.execute(insert(table).values(**values))
    with pytest.raises(DBAPIError) as error:
        with db_session.begin_nested():
            db_session.execute(insert(table).values(**values))
    assert error.value.orig.sqlstate == "23505"
    assert db_session.scalar(select(notification_model.id).where(table.c.id == values["id"])) == values["id"]


@pytest.fixture
def notification_repository(db_session):
    from app.repositories.notifications import NotificationRepository

    return NotificationRepository(db_session)


@pytest.fixture
def notification_users(authenticated_user_factory):
    return (
        authenticated_user_factory("first-owner@example.com"),
        authenticated_user_factory("second-owner@example.com"),
    )


def test_notification_users_have_distinct_authenticated_identities(db_test_client, notification_users):
    first, second = notification_users
    assert first["id"] != second["id"]
    for user in notification_users:
        response = db_test_client.get("/api/v1/users/me", headers=user["headers"])
        assert response.status_code == 200
        assert UUID(response.json()["id"]) == user["id"]


@pytest.mark.parametrize("channel", ["email", "sms", "push"])
def test_repository_create_persists_and_commits_once(
    db_session, notification_model, notification_owner, notification_repository, channel
):
    owner_id = notification_owner.id
    with patch.object(db_session, "commit", wraps=db_session.commit) as commit:
        notification = notification_repository.create(
            owner_id, "  Título  ", "\n Contenido \t", channel
        )
    commit.assert_called_once_with()
    notification_id = notification.id
    assert isinstance(notification_id, UUID)
    # Discard any subsequent read transaction, not the committed insertion.
    db_session.rollback()
    persisted = db_session.get(notification_model, notification_id)
    assert persisted is not None
    assert persisted.user_id == owner_id
    assert (persisted.title, persisted.content, persisted.channel) == (
        "  Título  ", "\n Contenido \t", channel
    )


def test_repository_list_is_empty_for_user_without_notifications(
    notification_repository, notification_users
):
    first, second = notification_users
    notification_repository.create(second["id"], "Ajena", "Contenido", "email")
    assert notification_repository.list_by_user(first["id"]) == []


def test_repository_lists_all_and_only_notifications_owned_by_user(
    notification_repository, notification_users
):
    first, second = notification_users
    own = [
        notification_repository.create(first["id"], "Propia", "Contenido", channel)
        for channel in ("email", "sms", "push")
    ]
    foreign = notification_repository.create(second["id"], "Ajena", "Privado", "push")

    assert {record.id for record in notification_repository.list_by_user(first["id"])} == {
        record.id for record in own
    }
    assert [record.id for record in notification_repository.list_by_user(second["id"])] == [
        foreign.id
    ]


def test_repository_lookup_filters_by_id_and_owner(notification_repository, notification_users):
    first, second = notification_users
    own = notification_repository.create(first["id"], "Propia", "Contenido", "email")
    foreign = notification_repository.create(second["id"], "Ajena", "Privado", "sms")

    assert notification_repository.get_by_id_and_user(own.id, first["id"]) is own
    assert notification_repository.get_by_id_and_user(foreign.id, first["id"]) is None
    assert notification_repository.get_by_id_and_user(own.id, second["id"]) is None
    assert notification_repository.get_by_id_and_user(uuid4(), first["id"]) is None
    assert notification_repository.get_by_id_and_user(foreign.id, second["id"]) is foreign
    assert (foreign.title, foreign.content, foreign.channel) == ("Ajena", "Privado", "sms")


@pytest.mark.parametrize("changes", [
    {"title": "  Nuevo título  "},
    {"content": "\n Nuevo contenido \t"},
    {"channel": "sms"},
    {"title": "Nuevo título", "content": "Nuevo contenido"},
    {"title": "Nuevo título", "channel": "push"},
    {"content": "Nuevo contenido", "channel": "push"},
    {"title": "Nuevo título", "content": "Nuevo contenido", "channel": "sms"},
])
def test_repository_update_only_changes_submitted_fields_and_commits_once(
    db_session, notification_model, notification_owner, notification_repository, changes
):
    original = {"title": "Original", "content": "Contenido original", "channel": "email"}
    notification = notification_repository.create(notification_owner.id, **original)
    notification_id, owner_id = notification.id, notification.user_id

    with patch.object(db_session, "commit", wraps=db_session.commit) as commit:
        updated = notification_repository.update(notification, changes)
    commit.assert_called_once_with()
    assert updated is notification
    db_session.rollback()
    persisted = db_session.get(notification_model, notification_id)
    assert persisted.user_id == owner_id
    assert {field: getattr(persisted, field) for field in original} == {**original, **changes}


def test_repository_delete_is_permanent_and_commits_once(
    db_session, notification_model, notification_repository, notification_users
):
    first, second = notification_users
    removed = notification_repository.create(first["id"], "Borrar", "Contenido", "sms")
    kept = notification_repository.create(second["id"], "Conservar", "Privado", "email")
    removed_id, kept_id = removed.id, kept.id

    with patch.object(db_session, "commit", wraps=db_session.commit) as commit:
        assert notification_repository.delete(removed) is None
    commit.assert_called_once_with()
    db_session.rollback()
    assert db_session.get(notification_model, removed_id) is None
    assert notification_repository.list_by_user(first["id"]) == []
    assert notification_repository.get_by_id_and_user(removed_id, first["id"]) is None
    assert db_session.get(notification_model, kept_id).content == "Privado"


@pytest.mark.parametrize("changes, sqlstate", [
    ({"channel": "fax"}, "23514"),
    ({"title": "a" * 201}, "22001"),
    ({"user_id": uuid4()}, "23503"),
])
def test_repository_failed_creation_rolls_back_and_session_recovers(
    db_session, notification_owner, notification_repository, changes, sqlstate
):
    owner_id = notification_owner.id
    # Commit setup independently of the write being rejected.
    db_session.commit()
    values = {"user_id": owner_id, "title": "Título", "content": "Contenido", "channel": "email"}

    with patch.object(db_session, "rollback", wraps=db_session.rollback) as rollback:
        with pytest.raises(DBAPIError) as error:
            notification_repository.create(**{**values, **changes})
    rollback.assert_called_once_with()
    assert error.value.orig.sqlstate == sqlstate
    assert notification_repository.list_by_user(owner_id) == []
    saved = notification_repository.create(**values)
    assert notification_repository.get_by_id_and_user(saved.id, owner_id) is saved


@pytest.mark.parametrize("invalid_changes, sqlstate", [
    ({"channel": "fax"}, "23514"),
    ({"content": "a" * 5001}, "22001"),
])
def test_repository_failed_update_has_no_partial_changes_and_session_recovers(
    db_session, notification_model, notification_owner, notification_repository,
    invalid_changes, sqlstate
):
    original = {"title": "Original", "content": "Contenido original", "channel": "email"}
    notification = notification_repository.create(notification_owner.id, **original)
    notification_id = notification.id

    with patch.object(db_session, "rollback", wraps=db_session.rollback) as rollback:
        with pytest.raises(DBAPIError) as error:
            notification_repository.update(notification, {"title": "No guardar", **invalid_changes})
    rollback.assert_called_once_with()
    assert error.value.orig.sqlstate == sqlstate
    db_session.expire_all()
    persisted = db_session.get(notification_model, notification_id)
    assert {field: getattr(persisted, field) for field in original} == original
    notification_repository.update(persisted, {"title": "Ahora sí"})
    db_session.refresh(persisted)
    assert persisted.title == "Ahora sí"


def test_repository_failed_delete_rolls_back_and_session_recovers(
    db_session, notification_model, notification_owner, notification_repository
):
    notification = notification_repository.create(
        notification_owner.id, "Conservar", "Contenido", "email"
    )
    notification_id = notification.id
    failure = SQLAlchemyError("Simulated commit failure")

    def fail_commit_after_flush():
        db_session.flush()
        raise failure

    # This schema has no dependent rows that could reject a DELETE naturally.
    with patch.object(db_session, "commit", side_effect=fail_commit_after_flush):
        with patch.object(db_session, "rollback", wraps=db_session.rollback) as rollback:
            with pytest.raises(SQLAlchemyError) as error:
                notification_repository.delete(notification)
    rollback.assert_called_once_with()
    assert error.value is failure
    db_session.expire_all()
    persisted = db_session.get(notification_model, notification_id)
    assert persisted.title == "Conservar"
    notification_repository.delete(persisted)
    assert db_session.get(notification_model, notification_id) is None


NOTIFICATION_URL = "/api/v1/notifications"
VALID_NOTIFICATION = {"title": "Aviso", "content": "Contenido", "channel": "email"}
RECIPIENTS = {"email": "recipient@example.com", "sms": "+12345678", "push": "device-token"}


def create_payload(values: dict[str, object]) -> dict[str, object]:
    channel = values.get("channel")
    recipient = RECIPIENTS.get(channel, RECIPIENTS["email"]) if isinstance(channel, str) else RECIPIENTS["email"]
    return {**values, "recipient": recipient}


INVALID_NOTIFICATION_FIELDS = [
    (field, value)
    for field in ("title", "content")
    for value in (None, 42, True, [], {}, "", " ", "\t", "\n", " \t\n ")
] + [
    ("title", "x" * 201), ("content", "x" * 5001),
] + [
    ("channel", value)
    for value in (None, "", "fax", "EMAIL", " email", "push ", 1, True, [], {})
]


def assert_safe_validation_response(response):
    assert response.status_code == 422
    assert set(response.json()) == {"detail"}
    assert response.json()["detail"]
    for error in response.json()["detail"]:
        assert set(error) == {"type", "field", "message"}
        assert isinstance(error["type"], str)
        assert error["field"] is None or isinstance(error["field"], str)
        assert isinstance(error["message"], str)
        assert error["message"]


@pytest.mark.parametrize("channel", ["email", "sms", "push"])
@pytest.mark.parametrize("title, content", [
    ("a", "b"), ("á" * 200, "ó" * 5000), ("  Aviso  ", "\n Contenido \t"),
])
def test_api_create_persists_public_values_and_authenticated_owner(
    db_test_client, db_session, notification_model, authenticated_user_factory, channel, title, content
):
    user = authenticated_user_factory("creator@example.com")
    if channel == "sms" and len(content) > 160:
        content = content[:160]
    values = {"title": title, "content": content, "channel": channel}
    response = db_test_client.post(
        NOTIFICATION_URL, headers=user["headers"], json=create_payload(values)
    )
    assert response.status_code == 201
    data = response.json()
    assert set(data) == {"id", "title", "content", "channel"}
    notification_id = UUID(data["id"])
    assert data == {"id": str(notification_id), **values}
    db_session.expire_all()
    saved = db_session.get(notification_model, notification_id)
    assert saved.user_id == user["id"]
    assert (saved.title, saved.content, saved.channel) == (title, content, channel)


def test_api_lists_empty_then_all_and_only_own_notifications(db_test_client, notification_users):
    first, second = notification_users
    for user in notification_users:
        response = db_test_client.get(NOTIFICATION_URL, headers=user["headers"])
        assert response.status_code == 200
        assert response.json() == []
    expected = {}
    for user in notification_users:
        expected[user["id"]] = []
        for channel in ("email", "sms", "push"):
            response = db_test_client.post(
                NOTIFICATION_URL,
                headers=user["headers"],
                json=create_payload({**VALID_NOTIFICATION, "channel": channel}),
            )
            assert response.status_code == 201
            expected[user["id"]].append(response.json())
    assert {item["id"] for item in expected[first["id"]]}.isdisjoint(
        item["id"] for item in expected[second["id"]]
    )
    for user in notification_users:
        response = db_test_client.get(NOTIFICATION_URL, headers=user["headers"])
        assert response.status_code == 200
        assert sorted(response.json(), key=lambda item: item["id"]) == sorted(
            expected[user["id"]], key=lambda item: item["id"]
        )
        assert all(set(item) == {"id", "title", "content", "channel"} for item in response.json())


@pytest.mark.parametrize("field, value", INVALID_NOTIFICATION_FIELDS)
def test_api_create_rejects_invalid_values_without_persisting(
    db_test_client, db_session, notification_model, auth_headers, field, value
):
    response = db_test_client.post(
        NOTIFICATION_URL, headers=auth_headers,
        json=create_payload({**VALID_NOTIFICATION, field: value})
    )
    assert_safe_validation_response(response)
    assert any(error["field"] == field for error in response.json()["detail"])
    assert db_session.scalars(select(notification_model)).all() == []
    assert "Contenido" not in response.text


@pytest.mark.parametrize("field", ["title", "content", "channel", "recipient"])
def test_api_create_requires_all_fields(db_test_client, db_session, notification_model, auth_headers, field):
    values = {name: value for name, value in create_payload(VALID_NOTIFICATION).items() if name != field}
    response = db_test_client.post(NOTIFICATION_URL, headers=auth_headers, json=values)
    assert_safe_validation_response(response)
    assert response.json()["detail"] == [{
        "type": "required_field", "field": field, "message": "Este campo es obligatorio.",
    }]
    assert db_session.scalars(select(notification_model)).all() == []


@pytest.mark.parametrize("field", ["id", "user_id", "unexpected"])
def test_api_create_rejects_identity_owner_and_unknown_fields(
    db_test_client, db_session, notification_model, notification_users, field
):
    first, second = notification_users
    response = db_test_client.post(
        NOTIFICATION_URL, headers=first["headers"],
        json=create_payload({**VALID_NOTIFICATION, field: str(second["id"])}),
    )
    assert_safe_validation_response(response)
    assert response.json()["detail"] == [{
        "type": "unexpected_field", "field": field, "message": "Este campo no está permitido.",
    }]
    assert str(second["id"]) not in response.text
    assert db_session.scalars(select(notification_model)).all() == []


@pytest.mark.parametrize("value, expected", [
    (None, {"type": "invalid_type", "field": "recipient", "message": "Ingresá un texto válido."}),
    (42, {"type": "invalid_type", "field": "recipient", "message": "Ingresá un texto válido."}),
    ("", {"type": "string_too_short", "field": "recipient", "message": "El campo debe tener al menos 1 carácter."}),
    ("not-an-email", {
        "type": "invalid_recipient_email", "field": "recipient",
        "message": "Ingresá un email destinatario válido de hasta 254 caracteres.",
    }),
])
def test_api_create_rejects_invalid_recipient_safely_without_persisting(
    db_test_client, db_session, notification_model, auth_headers, value, expected
):
    response = db_test_client.post(
        NOTIFICATION_URL, headers=auth_headers, json={**VALID_NOTIFICATION, "recipient": value}
    )
    assert response.status_code == 422
    assert response.json() == {"detail": [expected]}
    assert "not-an-email" not in response.text
    assert db_session.scalars(select(notification_model)).all() == []


@pytest.mark.parametrize("channel, recipient, content, expected", [
    ("sms", "+02345678", "Contenido", {
        "type": "invalid_recipient_sms", "field": "recipient",
        "message": "Ingresá un número con + y entre 8 y 15 dígitos, sin cero inicial.",
    }),
    ("push", "with space", "Contenido", {
        "type": "invalid_recipient_push", "field": "recipient",
        "message": "Ingresá un token de 1 a 512 caracteres ASCII visibles, sin espacios.",
    }),
    ("sms", "+12345678", "x" * 161, {
        "type": "sms_too_long", "field": "content",
        "message": "El contenido SMS debe tener como máximo 160 caracteres.",
    }),
])
def test_api_create_rejects_channel_delivery_validation_safely_without_persisting(
    db_test_client, db_session, notification_model, auth_headers, channel, recipient, content, expected
):
    response = db_test_client.post(NOTIFICATION_URL, headers=auth_headers, json={
        "title": "Aviso", "content": content, "channel": channel, "recipient": recipient,
    })
    assert response.status_code == 422
    assert response.json() == {"detail": [expected]}
    assert db_session.scalars(select(notification_model)).all() == []


@pytest.mark.parametrize("method", ["post", "get"])
@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Basic abc"])
def test_api_create_and_list_require_valid_authentication(
    db_test_client, db_session, notification_model, method, authorization
):
    headers = {"Authorization": authorization} if authorization else {}
    arguments = {"json": create_payload(VALID_NOTIFICATION)} if method == "post" else {}
    response = getattr(db_test_client, method)(NOTIFICATION_URL, headers=headers, **arguments)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert db_session.scalars(select(notification_model)).all() == []


def test_api_create_with_valid_body_without_auth_never_simulates_or_persists(
    db_test_client, db_session, notification_model, monkeypatch
):
    sender = create_autospec(NotificationSender, instance=True)
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)
    response = db_test_client.post(NOTIFICATION_URL, json=create_payload(VALID_NOTIFICATION))
    assert response.status_code == 401
    sender.simulate.assert_not_called()
    assert db_session.scalars(select(notification_model)).all() == []


@pytest.fixture
def notification_service_client(monkeypatch, notification_model):
    service = create_autospec(NotificationService, instance=True)
    user = User(id=uuid4(), email="injected@example.com", password_hash="test-only-placeholder-hash")
    notification = notification_model(id=uuid4(), user_id=user.id, **VALID_NOTIFICATION)
    service.create.return_value = notification
    service.list_own.return_value = [notification]
    service.update.return_value = notification

    def unexpected_database_access():
        raise AssertionError("Injected services and users must bypass database access")

    monkeypatch.setitem(app.dependency_overrides, get_db, unexpected_database_access)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: user)
    monkeypatch.setitem(app.dependency_overrides, get_notification_service, lambda: service)
    with TestClient(app) as client:
        yield client, service, user, notification


def test_api_create_uses_injected_service(notification_service_client):
    client, service, user, notification = notification_service_client
    response = client.post(NOTIFICATION_URL, json=create_payload(VALID_NOTIFICATION))
    assert response.status_code == 201
    assert response.json() == {"id": str(notification.id), **VALID_NOTIFICATION}
    service.create.assert_called_once_with(user.id, **VALID_NOTIFICATION, recipient=RECIPIENTS["email"])


def test_api_create_maps_delivery_execution_failure_to_safe_500(notification_service_client):
    client, service, _, _ = notification_service_client
    service.create.side_effect = DeliveryExecutionError()
    response = client.post(NOTIFICATION_URL, json=create_payload(VALID_NOTIFICATION))
    assert response.status_code == 500
    assert response.json() == {"detail": "No se pudo completar la creación de la notificación."}


def test_api_create_maps_response_materialization_failure_to_safe_500(notification_service_client):
    client, _, _, _ = notification_service_client
    with patch.object(NotificationResponse, "model_validate", side_effect=RuntimeError("private failure")):
        response = client.post(NOTIFICATION_URL, json=create_payload(VALID_NOTIFICATION))
    assert response.status_code == 500
    assert response.json() == {"detail": "No se pudo completar la creación de la notificación."}
    assert "private failure" not in response.text


def test_api_list_uses_injected_service(notification_service_client):
    client, service, user, notification = notification_service_client
    response = client.get(NOTIFICATION_URL)
    assert response.status_code == 200
    assert response.json() == [{"id": str(notification.id), **VALID_NOTIFICATION}]
    service.list_own.assert_called_once_with(user.id)


@pytest.fixture
def api_notification(db_test_client, auth_headers):
    response = db_test_client.post(
        NOTIFICATION_URL, headers=auth_headers, json=create_payload(VALID_NOTIFICATION)
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.parametrize("changes", [
    {"title": "  Nuevo título  "}, {"content": "\n Nuevo contenido \t"}, {"channel": "sms"},
    {"title": "Nuevo título", "content": "Nuevo contenido"},
    {"title": "Nuevo título", "channel": "push"},
    {"content": "Nuevo contenido", "channel": "push"},
    {"title": "Nuevo título", "content": "Nuevo contenido", "channel": "sms"},
    {"title": "a"}, {"title": "á" * 200}, {"content": "b"}, {"content": "ó" * 5000},
    {"channel": "email"}, {"channel": "push"},
])
def test_api_patch_preserves_omitted_fields_and_persists_only_changes(
    db_test_client, db_session, notification_model, auth_headers, api_notification, changes
):
    notification_id = UUID(api_notification["id"])
    owner_id = db_session.get(notification_model, notification_id).user_id
    response = db_test_client.patch(
        f"{NOTIFICATION_URL}/{notification_id}", headers=auth_headers, json=changes
    )
    assert response.status_code == 200
    assert response.json() == {**api_notification, **changes}
    db_session.expire_all()
    persisted = db_session.get(notification_model, notification_id)
    assert persisted.user_id == owner_id
    assert NotificationResponse.model_validate(persisted).model_dump(mode="json") == response.json()
    listing = db_test_client.get(NOTIFICATION_URL, headers=auth_headers)
    assert listing.json() == [response.json()]


@pytest.mark.parametrize("field, value", INVALID_NOTIFICATION_FIELDS)
def test_api_patch_rejects_invalid_values_without_partial_changes(
    db_test_client, db_session, notification_model, auth_headers, api_notification, field, value
):
    valid_field = "content" if field == "title" else "title"
    response = db_test_client.patch(
        f"{NOTIFICATION_URL}/{api_notification['id']}", headers=auth_headers,
        json={valid_field: "private-value-not-to-persist", field: value},
    )
    assert_safe_validation_response(response)
    assert any(error["field"] == field for error in response.json()["detail"])
    assert "private-value-not-to-persist" not in response.text
    db_session.expire_all()
    persisted = db_session.get(notification_model, UUID(api_notification["id"]))
    assert NotificationResponse.model_validate(persisted).model_dump(mode="json") == api_notification
    assert db_test_client.get(NOTIFICATION_URL, headers=auth_headers).json() == [api_notification]


def test_api_patch_rejects_empty_object(db_test_client, auth_headers, api_notification):
    response = db_test_client.patch(
        f"{NOTIFICATION_URL}/{api_notification['id']}", headers=auth_headers, json={}
    )
    assert_safe_validation_response(response)
    assert response.json()["detail"] == [{
        "type": "empty_update", "field": None, "message": "Enviá al menos un campo para modificar.",
    }]
    assert db_test_client.get(NOTIFICATION_URL, headers=auth_headers).json() == [api_notification]


@pytest.mark.parametrize("field", ["id", "user_id", "unexpected"])
def test_api_patch_rejects_immutable_or_unknown_fields_without_partial_changes(
    db_test_client, db_session, notification_model, notification_users, field
):
    first, second = notification_users
    original = db_test_client.post(
        NOTIFICATION_URL, headers=first["headers"], json=create_payload(VALID_NOTIFICATION)
    ).json()
    response = db_test_client.patch(
        f"{NOTIFICATION_URL}/{original['id']}", headers=first["headers"],
        json={"title": "private-title", field: str(second["id"])},
    )
    assert_safe_validation_response(response)
    assert response.json()["detail"] == [{
        "type": "unexpected_field", "field": field, "message": "Este campo no está permitido.",
    }]
    assert "private-title" not in response.text
    assert str(second["id"]) not in response.text
    db_session.expire_all()
    persisted = db_session.get(notification_model, UUID(original["id"]))
    assert persisted.user_id == first["id"]
    assert NotificationResponse.model_validate(persisted).model_dump(mode="json") == original


def test_api_patch_rejects_recipient_without_partial_changes(
    db_test_client, db_session, notification_model, auth_headers, api_notification
):
    response = db_test_client.patch(
        f"{NOTIFICATION_URL}/{api_notification['id']}", headers=auth_headers,
        json={"title": "No guardar", "recipient": "private-recipient"},
    )
    assert response.status_code == 422
    assert response.json() == {"detail": [{
        "type": "unexpected_field", "field": "recipient", "message": "Este campo no está permitido.",
    }]}
    db_session.expire_all()
    persisted = db_session.get(notification_model, UUID(api_notification["id"]))
    assert NotificationResponse.model_validate(persisted).model_dump(mode="json") == api_notification


def test_api_patch_allows_sms_content_of_5000_without_resending(
    db_test_client, auth_headers, api_notification, monkeypatch
):
    sender = create_autospec(NotificationSender, instance=True)
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)
    response = db_test_client.patch(
        f"{NOTIFICATION_URL}/{api_notification['id']}", headers=auth_headers,
        json={"channel": "sms", "content": "x" * 5000},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "x" * 5000
    assert response.json()["channel"] == "sms"
    sender.simulate.assert_not_called()


def test_api_delete_removes_row_and_listing_and_repeated_operations_return_404(
    db_test_client, db_session, notification_model, notification_users
):
    first, second = notification_users
    records = [
        db_test_client.post(
            NOTIFICATION_URL, headers=user["headers"], json=create_payload(VALID_NOTIFICATION)
        ).json()
        for user in (first, first, second)
    ]
    url = f"{NOTIFICATION_URL}/{records[0]['id']}"
    response = db_test_client.delete(url, headers=first["headers"])
    assert response.status_code == 204
    assert response.content == b""
    db_session.expire_all()
    assert db_session.get(notification_model, UUID(records[0]["id"])) is None
    assert db_test_client.get(NOTIFICATION_URL, headers=first["headers"]).json() == [records[1]]
    assert db_test_client.get(NOTIFICATION_URL, headers=second["headers"]).json() == [records[2]]
    repeated = db_test_client.delete(url, headers=first["headers"])
    edited = db_test_client.patch(url, headers=first["headers"], json={"title": "Nuevo"})
    assert repeated.status_code == edited.status_code == 404
    assert repeated.json() == edited.json() == {"detail": "Notificación no encontrada."}


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_api_foreign_and_nonexistent_resources_are_indistinguishable_and_unchanged(
    db_test_client, db_session, notification_model, notification_users, method
):
    first, second = notification_users
    original = db_test_client.post(
        NOTIFICATION_URL, headers=second["headers"], json=create_payload(VALID_NOTIFICATION)
    ).json()
    arguments = {"json": {"title": "No guardar"}} if method == "patch" else {}
    responses = [
        getattr(db_test_client, method)(
            f"{NOTIFICATION_URL}/{notification_id}", headers=first["headers"], **arguments
        )
        for notification_id in (original["id"], str(uuid4()))
    ]
    assert all(response.status_code == 404 for response in responses)
    assert responses[0].json() == responses[1].json() == {"detail": "Notificación no encontrada."}
    assert db_test_client.get(NOTIFICATION_URL, headers=first["headers"]).json() == []
    assert db_test_client.get(NOTIFICATION_URL, headers=second["headers"]).json() == [original]
    db_session.expire_all()
    persisted = db_session.get(notification_model, UUID(original["id"]))
    assert persisted.user_id == second["id"]
    assert NotificationResponse.model_validate(persisted).model_dump(mode="json") == original


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_api_patch_and_delete_reject_malformed_uuid(db_test_client, auth_headers, method):
    arguments = {"json": {"title": "Válido"}} if method == "patch" else {}
    response = getattr(db_test_client, method)(
        f"{NOTIFICATION_URL}/private-invalid-uuid", headers=auth_headers, **arguments
    )
    assert_safe_validation_response(response)
    assert response.json()["detail"] == [{
        "type": "invalid_uuid", "field": "notification_id",
        "message": "Ingresá un identificador UUID válido.",
    }]
    assert "private-invalid-uuid" not in response.text


@pytest.mark.parametrize("method", ["patch", "delete"])
@pytest.mark.parametrize("authorization", [None, "Bearer invalid", "Basic abc"])
def test_api_patch_and_delete_require_authentication_without_changing_data(
    db_test_client, db_session, notification_model, api_notification, method, authorization
):
    headers = {"Authorization": authorization} if authorization else {}
    arguments = {"json": {"title": "No guardar"}} if method == "patch" else {}
    response = getattr(db_test_client, method)(
        f"{NOTIFICATION_URL}/{api_notification['id']}", headers=headers, **arguments
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    db_session.expire_all()
    persisted = db_session.get(notification_model, UUID(api_notification["id"]))
    assert NotificationResponse.model_validate(persisted).model_dump(mode="json") == api_notification


def test_api_patch_uses_injected_service_with_only_submitted_fields(notification_service_client):
    client, service, user, notification = notification_service_client
    response = client.patch(f"{NOTIFICATION_URL}/{notification.id}", json={"title": "Nuevo"})
    assert response.status_code == 200
    assert response.json() == {"id": str(notification.id), **VALID_NOTIFICATION}
    service.update.assert_called_once_with(user.id, notification.id, {"title": "Nuevo"})


def test_api_delete_uses_injected_service(notification_service_client):
    client, service, user, notification = notification_service_client
    response = client.delete(f"{NOTIFICATION_URL}/{notification.id}")
    assert response.status_code == 204
    assert response.content == b""
    service.delete.assert_called_once_with(user.id, notification.id)


@pytest.mark.parametrize("method, operation", [("patch", "update"), ("delete", "delete")])
def test_api_translates_not_found_service_error(notification_service_client, method, operation):
    client, service, _, notification = notification_service_client
    getattr(service, operation).side_effect = NotificationNotFoundError
    arguments = {"json": {"title": "Nuevo"}} if method == "patch" else {}
    response = getattr(client, method)(f"{NOTIFICATION_URL}/{notification.id}", **arguments)
    assert response.status_code == 404
    assert response.json() == {"detail": "Notificación no encontrada."}


@pytest.fixture
def notification_openapi():
    with TestClient(app) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("method, path, success", [
    ("post", NOTIFICATION_URL, "201"), ("get", NOTIFICATION_URL, "200"),
    ("patch", f"{NOTIFICATION_URL}/{{notification_id}}", "200"),
    ("delete", f"{NOTIFICATION_URL}/{{notification_id}}", "204"),
])
def test_notification_openapi_documents_security_responses_and_public_representation(
    notification_openapi, method, path, success
):
    operation = notification_openapi["paths"][path][method]
    assert operation["security"] == [{"HTTPBearer": []}]
    assert operation["tags"] == ["Notifications"]
    responses = operation["responses"]
    assert {success, "401", "422"} <= responses.keys()
    assert responses["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ValidationErrorResponse"
    }
    if method in {"patch", "delete"}:
        assert responses["404"]["content"]["application/json"]["example"] == {
            "detail": "Notificación no encontrada."
        }
        assert operation["parameters"] == [{
            "name": "notification_id", "in": "path", "required": True,
            "schema": {"type": "string", "format": "uuid", "title": "Notification Id"},
        }]
    else:
        assert operation.get("parameters", []) == []
    if method == "post":
        assert responses["500"]["content"]["application/json"]["example"] == {
            "detail": "No se pudo completar la creación de la notificación."
        }
    if method == "delete":
        assert "content" not in responses[success]
    else:
        response_schema = responses[success]["content"]["application/json"]["schema"]
        if method == "get":
            assert response_schema["type"] == "array"
            response_schema = response_schema["items"]
        assert response_schema == {"$ref": "#/components/schemas/NotificationResponse"}


def test_notification_openapi_documents_input_constraints_and_partial_update(notification_openapi):
    schemas = notification_openapi["components"]["schemas"]
    create = schemas["NotificationCreateRequest"]
    update = schemas["NotificationUpdateRequest"]
    response = schemas["NotificationResponse"]
    assert set(create["required"]) == {"title", "content", "channel", "recipient"}
    assert not update.get("required")
    assert update["minProperties"] == 1
    assert create["additionalProperties"] is update["additionalProperties"] is False
    for contract in (create, update, response):
        fields = contract["properties"]
        assert set(fields) == ({"id", "title", "content", "channel"} if contract is response else (
            {"title", "content", "channel", "recipient"} if contract is create else {
                "title", "content", "channel"
            }
        ))
        for field, maximum in (("title", 200), ("content", 5000)):
            assert fields[field]["type"] == "string"
            assert fields[field]["minLength"] == 1
            assert fields[field]["maxLength"] == maximum
        assert fields["channel"]["type"] == "string"
        assert fields["channel"]["enum"] == ["email", "sms", "push"]
    assert create["properties"]["recipient"]["type"] == "string"
    assert create["properties"]["recipient"]["minLength"] == 1
    assert create["properties"]["recipient"]["writeOnly"] is True
    assert "SMS" in create["properties"]["recipient"]["description"]
    assert set(response["required"]) == {"id", "title", "content", "channel"}
    assert response["properties"]["id"]["format"] == "uuid"
    for field in update["properties"].values():
        assert "anyOf" not in field
        assert "default" not in field
    for method, path, name in (
        ("post", NOTIFICATION_URL, "NotificationCreateRequest"),
        ("patch", f"{NOTIFICATION_URL}/{{notification_id}}", "NotificationUpdateRequest"),
    ):
        body = notification_openapi["paths"][path][method]["requestBody"]
        assert body["required"] is True
        assert body["content"]["application/json"]["schema"] == {
            "$ref": f"#/components/schemas/{name}"
        }


def test_notification_openapi_explains_delivery_contract_limits(notification_openapi):
    recipient_description = notification_openapi["components"]["schemas"][
        "NotificationCreateRequest"
    ]["properties"]["recipient"]["description"]
    create_description = notification_openapi["paths"][NOTIFICATION_URL]["post"]["description"]

    assert "espacios externos" in recipient_description
    assert "minúsculas" in recipient_description
    assert "160" in recipient_description
    assert "simulación local" in create_description
    assert "no acredita recepción real" in create_description
    assert "puede existir" in create_description
    assert "500" in create_description


def test_notification_openapi_has_only_approved_operations(notification_openapi):
    paths = notification_openapi["paths"]
    assert {path for path in paths if path.startswith(NOTIFICATION_URL)} == {
        NOTIFICATION_URL, f"{NOTIFICATION_URL}/{{notification_id}}"
    }
    assert set(paths[NOTIFICATION_URL]) == {"get", "post"}
    assert set(paths[NOTIFICATION_URL + "/{notification_id}"]) == {"patch", "delete"}
    assert notification_openapi["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http", "scheme": "bearer"
    }


@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize("arguments", [
    {}, {"json": None}, {"json": []}, {"json": "private-body"}, {"json": 42},
    {"content": '{"title": "private-body",'},
])
def test_api_rejects_missing_malformed_or_nonobject_bodies_without_mutations(
    db_test_client, db_session, notification_model, auth_headers, api_notification, method, arguments
):
    url = NOTIFICATION_URL if method == "post" else f"{NOTIFICATION_URL}/{api_notification['id']}"
    response = getattr(db_test_client, method)(
        url, headers={**auth_headers, "Content-Type": "application/json"}, **arguments
    )
    assert_safe_validation_response(response)
    assert "private-body" not in response.text
    db_session.expire_all()
    records = db_session.scalars(select(notification_model)).all()
    assert [NotificationResponse.model_validate(record).model_dump(mode="json") for record in records] == [
        api_notification
    ]


@pytest.mark.parametrize("method", ["post", "get", "patch", "delete"])
@pytest.mark.parametrize("kind", ["expired", "wrong-key", "unknown-user", "deleted-user"])
def test_all_notification_operations_reject_invalid_tokens_without_mutations(
    db_test_client, db_session, notification_model, authenticated_user_factory,
    api_notification, method, kind
):
    actor = authenticated_user_factory("invalid-token@example.com")
    if kind == "deleted-user":
        token = actor["headers"]["Authorization"].removeprefix("Bearer ")
        db_session.delete(db_session.get(User, actor["id"]))
        db_session.commit()
    elif kind == "unknown-user":
        token = create_access_token(uuid4())
    else:
        now = datetime.now(timezone.utc)
        expiration = now - timedelta(seconds=10) if kind == "expired" else now + timedelta(minutes=5)
        key = settings.jwt_secret_key.get_secret_value() if kind == "expired" else (
            "different-test-only-signing-key-32-chars"
        )
        token = jwt.encode({"sub": str(actor["id"]), "iat": now, "exp": expiration}, key, algorithm="HS256")
    url = NOTIFICATION_URL if method in {"post", "get"} else (
        f"{NOTIFICATION_URL}/{api_notification['id']}"
    )
    arguments = {"json": create_payload(VALID_NOTIFICATION)} if method == "post" else (
        {"json": {"title": "No guardar"}} if method == "patch" else {}
    )
    response = getattr(db_test_client, method)(
        url, headers={"Authorization": f"Bearer {token}"}, **arguments
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    db_session.expire_all()
    records = db_session.scalars(select(notification_model)).all()
    assert [NotificationResponse.model_validate(record).model_dump(mode="json") for record in records] == [
        api_notification
    ]


def _delivery_logger(stream):
    logger = logging.Logger("notification-http-delivery-test")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = DeliveryLogHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    return logger, handler


@pytest.mark.parametrize(
    "channel, recipient, strategy_factory",
    [
        ("email", "recipient@example.com", EmailDeliveryStrategy),
        ("push", "device-token-private", PushDeliveryStrategy),
    ],
)
def test_api_preparation_failure_records_one_protected_failure_and_never_persists(
    db_test_client, db_session, notification_model, auth_headers, monkeypatch,
    channel, recipient, strategy_factory,
):
    secret = "private-preparation-error"
    stream = io.StringIO()
    logger, _ = _delivery_logger(stream)
    selected = Mock(wraps=strategy_factory())
    selected.prepare.side_effect = RuntimeError(secret)
    other = Mock()
    sender = NotificationSender(
        {channel: selected, "other-channel": other},
        DeliveryRecorder(logger, lambda: datetime(2026, 11, 9, tzinfo=timezone.utc)),
    )
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)

    response = db_test_client.post(NOTIFICATION_URL, headers=auth_headers, json={
        "title": "private-title", "content": "private-content", "channel": channel,
        "recipient": recipient,
    })

    assert response.status_code == 500
    assert response.json() == {"detail": "No se pudo completar la creación de la notificación."}
    assert secret not in response.text
    assert recipient not in response.text
    assert selected.mock_calls == [
        call.validate(recipient, "private-content"),
        call.prepare("private-title", "private-content"),
        call.protect_recipient(
            "recipient@example.com" if channel == "email" else recipient
        ),
    ]
    other.assert_not_called()
    assert db_session.scalars(select(notification_model)).all() == []
    event = json.loads(stream.getvalue())
    assert event == {
        "event": "notification_delivery", "channel": channel, "status": "failed",
        "timestamp": "2026-11-09T00:00:00+00:00",
        "recipient": "[redacted]",
    }
    assert all(value not in stream.getvalue() for value in (secret, recipient, "private-title", "private-content"))


def test_api_delivery_execution_failure_stops_before_recording_or_persisting(
    db_test_client, db_session, notification_model, auth_headers, monkeypatch
):
    secret = "private-validation-execution-error"
    strategy = Mock(wraps=EmailDeliveryStrategy())
    strategy.validate.side_effect = RuntimeError(secret)
    recorder = Mock()
    sender = NotificationSender({"email": strategy, "push": Mock()}, recorder)
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)

    response = db_test_client.post(
        NOTIFICATION_URL, headers=auth_headers, json=create_payload(VALID_NOTIFICATION)
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "No se pudo completar la creación de la notificación."}
    assert secret not in response.text
    strategy.prepare.assert_not_called()
    strategy.protect_recipient.assert_not_called()
    recorder.assert_not_called()
    assert db_session.scalars(select(notification_model)).all() == []


@pytest.mark.parametrize("failure_point", ["clock", "format", "write", "flush"])
def test_api_recording_failures_from_real_recorder_handler_never_persist_or_retry(
    db_test_client, db_session, notification_model, auth_headers, monkeypatch, failure_point
):
    secret = f"private-{failure_point}-failure"
    stream = Mock()
    logger, handler = _delivery_logger(stream)
    clock = lambda: datetime(2026, 11, 9, tzinfo=timezone.utc)
    if failure_point == "clock":
        clock = Mock(side_effect=RuntimeError(secret))
    elif failure_point == "format":
        formatter = Mock()
        formatter.format.side_effect = RuntimeError(secret)
        handler.setFormatter(formatter)
    elif failure_point == "write":
        stream.write.side_effect = RuntimeError(secret)
    else:
        stream.flush.side_effect = RuntimeError(secret)
    selected = Mock(wraps=EmailDeliveryStrategy())
    other = Mock()
    sender = NotificationSender(
        {"email": selected, "push": other}, DeliveryRecorder(logger, clock)
    )
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)

    response = db_test_client.post(
        NOTIFICATION_URL, headers=auth_headers, json=create_payload(VALID_NOTIFICATION)
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "No se pudo completar la creación de la notificación."}
    assert secret not in response.text
    selected.validate.assert_called_once_with("recipient@example.com", "Contenido")
    selected.prepare.assert_called_once_with("Aviso", "Contenido")
    selected.protect_recipient.assert_called_once_with("recipient@example.com")
    other.assert_not_called()
    assert db_session.scalars(select(notification_model)).all() == []
    if failure_point == "clock":
        assert clock.call_count == 1
    else:
        assert handler.stream is stream
        stream.flush.side_effect = None


def test_api_reversible_postgresql_write_failure_rolls_back_and_preserves_existing_rows(
    db_test_client, db_session, notification_model, notification_users, monkeypatch
):
    first, second = notification_users
    repository = NotificationRepository(db_session)
    existing = [
        repository.create(user["id"], title, "Conservar", "email")
        for user, title in ((first, "Primera"), (second, "Segunda"))
    ]
    sender = create_autospec(NotificationSender, instance=True)
    failure = SQLAlchemyError("private-reversible-commit-failure")

    def fail_commit_after_real_flush():
        db_session.flush()
        raise failure

    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)
    with patch.object(db_session, "commit", side_effect=fail_commit_after_real_flush) as commit:
        with patch.object(db_session, "rollback", wraps=db_session.rollback) as rollback:
            with patch.object(db_session, "delete", wraps=db_session.delete) as delete:
                response = db_test_client.post(
                    NOTIFICATION_URL, headers=first["headers"], json=create_payload(VALID_NOTIFICATION)
                )

    assert response.status_code == 500
    assert response.json() == {"detail": "No se pudo completar la creación de la notificación."}
    sender.simulate.assert_called_once_with("email", "recipient@example.com", "Aviso", "Contenido")
    assert commit.call_count == 1
    rollback.assert_called_once_with()
    delete.assert_not_called()
    assert db_session.scalar(text("SELECT 1")) == 1
    rows = db_session.scalars(select(notification_model).order_by(notification_model.title)).all()
    assert [(row.user_id, row.title, row.content) for row in rows] == [
        (first["id"], "Primera", "Conservar"),
        (second["id"], "Segunda", "Conservar"),
    ]


@pytest.mark.parametrize("failure_point", ["refresh", "model_validate", "model_dump", "json_response"])
def test_api_postcommit_response_failures_return_safe_500_and_keep_confirmed_row(
    db_test_client, db_session, notification_model, auth_headers, monkeypatch, failure_point
):
    secret = f"private-{failure_point}-failure"
    sender = create_autospec(NotificationSender, instance=True)
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)
    patch_target = {
        "refresh": (db_session, "refresh"),
        "model_validate": (NotificationResponse, "model_validate"),
        "model_dump": (NotificationResponse, "model_dump"),
        "json_response": ("app.routers.notifications.JSONResponse", None),
    }[failure_point]
    if patch_target[1] is None:
        failure_patch = patch(patch_target[0], side_effect=RuntimeError(secret))
    else:
        failure_patch = patch.object(patch_target[0], patch_target[1], side_effect=RuntimeError(secret))

    with patch.object(db_session, "commit", wraps=db_session.commit) as commit:
        with patch.object(db_session, "delete", wraps=db_session.delete) as delete:
            with failure_patch:
                response = db_test_client.post(
                    NOTIFICATION_URL, headers=auth_headers, json=create_payload(VALID_NOTIFICATION)
                )

    assert response.status_code == 500
    assert response.json() == {"detail": "No se pudo completar la creación de la notificación."}
    assert secret not in response.text
    sender.simulate.assert_called_once_with("email", "recipient@example.com", "Aviso", "Contenido")
    commit.assert_called_once_with()
    delete.assert_not_called()
    db_session.rollback()
    saved = db_session.scalar(
        select(notification_model).where(notification_model.title == "Aviso")
    )
    assert saved is not None
    assert (saved.content, saved.channel) == ("Contenido", "email")


@pytest.mark.parametrize(
    "channel, recipient, expected_code",
    [
        ("email", "invalid-email", "invalid_recipient_email"),
        ("sms", "+1234567", "invalid_recipient_sms"),
        ("sms", "+1234567890123456", "invalid_recipient_sms"),
        ("sms", "+12345678\n", "invalid_recipient_sms"),
        ("sms", "+١٢٣٤٥٦٧٨", "invalid_recipient_sms"),
        ("push", "token with space", "invalid_recipient_push"),
        ("push", "!" * 513, "invalid_recipient_push"),
        ("push", "token\x7f", "invalid_recipient_push"),
        ("push", "token-á", "invalid_recipient_push"),
    ],
)
def test_api_recipient_format_and_unicode_errors_are_safe_and_never_simulate(
    db_test_client, db_session, notification_model, auth_headers, monkeypatch,
    channel, recipient, expected_code,
):
    recorder = Mock()
    sender = NotificationSender(
        {
            "email": EmailDeliveryStrategy(),
            "sms": SmsDeliveryStrategy(),
            "push": PushDeliveryStrategy(),
        },
        recorder,
    )
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)
    response = db_test_client.post(NOTIFICATION_URL, headers=auth_headers, json={
        "title": "Aviso", "content": "Contenido", "channel": channel, "recipient": recipient,
    })
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == expected_code
    assert response.json()["detail"][0]["field"] == "recipient"
    assert recipient not in response.text
    recorder.assert_not_called()
    assert db_session.scalars(select(notification_model)).all() == []


@pytest.mark.parametrize("recipient", [None, 42, True, [], {}])
def test_api_recipient_non_string_errors_are_safe_and_never_simulate(
    db_test_client, db_session, notification_model, auth_headers, monkeypatch, recipient
):
    sender = create_autospec(NotificationSender, instance=True)
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)
    response = db_test_client.post(NOTIFICATION_URL, headers=auth_headers, json={
        **VALID_NOTIFICATION, "recipient": recipient,
    })
    assert response.status_code == 422
    assert response.json()["detail"] == [{
        "type": "invalid_type", "field": "recipient", "message": "Ingresá un texto válido.",
    }]
    sender.simulate.assert_not_called()
    assert db_session.scalars(select(notification_model)).all() == []


@pytest.mark.parametrize(
    "channel, recipient, content",
    [
        ("sms", "+12345678", "😀" * 160),
        ("sms", "+123456789012345", "e\u0301" * 80),
        ("push", "!", "Contenido"),
        ("push", "~" * 512, "Contenido"),
    ],
)
def test_api_recipient_boundaries_and_sms_unicode_code_points_are_accepted(
    db_test_client, db_session, notification_model, auth_headers, channel, recipient, content
):
    response = db_test_client.post(NOTIFICATION_URL, headers=auth_headers, json={
        "title": "Aviso", "content": content, "channel": channel, "recipient": recipient,
    })
    assert response.status_code == 201
    assert response.json() == {"id": response.json()["id"], "title": "Aviso", "content": content, "channel": channel}
    assert db_session.get(notification_model, UUID(response.json()["id"])) is not None


@pytest.mark.parametrize("kind", ["missing", "invalid", "expired", "deleted", "unknown"])
def test_api_unauthorized_post_never_simulates_or_writes_for_all_auth_failures(
    db_test_client, db_session, notification_model, authenticated_user_factory, api_notification,
    monkeypatch, kind,
):
    sender = create_autospec(NotificationSender, instance=True)
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)
    headers = {}
    if kind == "invalid":
        headers = {"Authorization": "Bearer invalid"}
    elif kind == "expired":
        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {"sub": str(uuid4()), "iat": now, "exp": now - timedelta(seconds=1)},
            settings.jwt_secret_key.get_secret_value(), algorithm="HS256",
        )
        headers = {"Authorization": f"Bearer {token}"}
    elif kind == "unknown":
        headers = {"Authorization": f"Bearer {create_access_token(uuid4())}"}
    elif kind == "deleted":
        actor = authenticated_user_factory("deleted-post-owner@example.com")
        token = actor["headers"]["Authorization"].removeprefix("Bearer ")
        db_session.delete(db_session.get(User, actor["id"]))
        db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

    response = db_test_client.post(
        NOTIFICATION_URL, headers=headers, json=create_payload(VALID_NOTIFICATION)
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    sender.simulate.assert_not_called()
    records = db_session.scalars(select(notification_model)).all()
    assert [NotificationResponse.model_validate(record).model_dump(mode="json") for record in records] == [
        api_notification
    ]


def test_api_rest_crud_after_post_never_resends_or_records_events(
    db_test_client, auth_headers, monkeypatch
):
    sender = create_autospec(NotificationSender, instance=True)
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)
    created = db_test_client.post(
        NOTIFICATION_URL, headers=auth_headers, json=create_payload(VALID_NOTIFICATION)
    ).json()
    sender.simulate.assert_called_once()
    sender.reset_mock()

    assert db_test_client.get(NOTIFICATION_URL, headers=auth_headers).status_code == 200
    assert db_test_client.patch(
        f"{NOTIFICATION_URL}/{created['id']}", headers=auth_headers, json={"title": "Editada"}
    ).status_code == 200
    assert db_test_client.delete(
        f"{NOTIFICATION_URL}/{created['id']}", headers=auth_headers
    ).status_code == 204
    sender.simulate.assert_not_called()


def test_api_directly_persisted_preexisting_notification_remains_editable_without_delivery(
    db_test_client, db_session, notification_model, authenticated_user_factory, monkeypatch
):
    owner = authenticated_user_factory("preexisting-owner@example.com")
    record = notification_model(
        user_id=owner["id"], title="Anterior", content="Contenido anterior", channel="sms"
    )
    db_session.add(record)
    db_session.flush()
    sender = create_autospec(NotificationSender, instance=True)
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)

    assert db_test_client.get(NOTIFICATION_URL, headers=owner["headers"]).json() == [{
        "id": str(record.id), "title": "Anterior", "content": "Contenido anterior", "channel": "sms",
    }]
    response = db_test_client.patch(
        f"{NOTIFICATION_URL}/{record.id}", headers=owner["headers"], json={"content": "x" * 5000}
    )
    assert response.status_code == 200
    assert response.json()["content"] == "x" * 5000
    assert db_test_client.delete(f"{NOTIFICATION_URL}/{record.id}", headers=owner["headers"]).status_code == 204
    sender.simulate.assert_not_called()


def test_api_two_posts_emit_two_protected_events_and_two_independent_rows(
    db_test_client, db_session, notification_model, auth_headers, monkeypatch
):
    stream = io.StringIO()
    logger, _ = _delivery_logger(stream)
    sender = NotificationSender(
        {
            "email": EmailDeliveryStrategy(),
            "push": PushDeliveryStrategy(),
        },
        DeliveryRecorder(logger, lambda: datetime(2026, 11, 9, tzinfo=timezone.utc)),
    )
    monkeypatch.setitem(app.dependency_overrides, get_notification_sender, lambda: sender)
    payloads = [
        create_payload(VALID_NOTIFICATION),
        {"title": "Segundo", "content": "Otro contenido", "channel": "push", "recipient": "push-private-token"},
    ]
    responses = [
        db_test_client.post(NOTIFICATION_URL, headers=auth_headers, json=payload)
        for payload in payloads
    ]
    assert [response.status_code for response in responses] == [201, 201]
    assert len({response.json()["id"] for response in responses}) == 2
    assert len(db_session.scalars(select(notification_model)).all()) == 2
    events = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert events == [
        {
            "event": "notification_delivery", "channel": "email", "status": "simulated",
            "timestamp": "2026-11-09T00:00:00+00:00", "recipient": "[redacted]",
        },
        {
            "event": "notification_delivery", "channel": "push", "status": "simulated",
            "timestamp": "2026-11-09T00:00:00+00:00", "recipient": "[redacted]",
        },
    ]
    assert all(set(event) == {"event", "channel", "status", "timestamp", "recipient"} for event in events)
    assert all(secret not in stream.getvalue() for secret in ("recipient@example.com", "push-private-token", "Aviso", "Contenido", "Segundo", "Otro contenido"))
