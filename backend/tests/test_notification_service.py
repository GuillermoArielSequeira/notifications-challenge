from unittest.mock import create_autospec
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.dependencies import get_notification_service
from app.models.notification import Notification
from app.repositories.notifications import NotificationRepository
from app.services.notifications import NotificationNotFoundError, NotificationService


@pytest.fixture
def repository():
    return create_autospec(NotificationRepository, instance=True)


@pytest.fixture
def service(repository):
    return NotificationService(repository)


def test_notification_service_provider_uses_injected_session():
    session = create_autospec(Session, instance=True)
    service = get_notification_service(session)
    assert isinstance(service, NotificationService)
    assert isinstance(service.notifications, NotificationRepository)
    assert service.notifications.session is session
    assert session.mock_calls == []


def test_service_create_passes_owner_and_preserves_values(service, repository):
    owner_id = uuid4()
    created = service.create(owner_id, "  Título  ", "\n Contenido \t", "push")
    repository.create.assert_called_once_with(owner_id, "  Título  ", "\n Contenido \t", "push")
    assert created is repository.create.return_value
    repository.get_by_id_and_user.assert_not_called()


@pytest.mark.parametrize("has_notifications", [False, True])
def test_service_list_passes_owner_and_returns_repository_result(service, repository, has_notifications):
    owner_id = uuid4()
    records = [Notification(id=uuid4(), user_id=owner_id)] if has_notifications else []
    repository.list_by_user.return_value = records
    assert service.list_own(owner_id) is records
    repository.list_by_user.assert_called_once_with(owner_id)
    repository.create.assert_not_called()


@pytest.mark.parametrize("changes", [
    {"title": "Nuevo título"}, {"content": "\n Contenido \t"}, {"channel": "sms"},
    {"title": "Título", "content": "Contenido", "channel": "push"},
])
def test_service_update_looks_up_own_resource_and_passes_only_changes(service, repository, changes):
    owner_id, notification_id = uuid4(), uuid4()
    notification = repository.get_by_id_and_user.return_value
    original = changes.copy()
    result = service.update(owner_id, notification_id, changes)
    repository.get_by_id_and_user.assert_called_once_with(notification_id, owner_id)
    repository.update.assert_called_once_with(notification, original)
    assert result is repository.update.return_value
    assert changes == original
    repository.delete.assert_not_called()


def test_service_delete_looks_up_own_resource(service, repository):
    owner_id, notification_id = uuid4(), uuid4()
    assert service.delete(owner_id, notification_id) is None
    repository.get_by_id_and_user.assert_called_once_with(notification_id, owner_id)
    repository.delete.assert_called_once_with(repository.get_by_id_and_user.return_value)
    repository.update.assert_not_called()


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_service_missing_or_foreign_resource_raises_same_error_without_writing(
    service, repository, operation
):
    owner_id, notification_id = uuid4(), uuid4()
    repository.get_by_id_and_user.return_value = None
    arguments = (owner_id, notification_id, {"title": "Nuevo"}) if operation == "update" else (
        owner_id, notification_id
    )
    with pytest.raises(NotificationNotFoundError):
        getattr(service, operation)(*arguments)
    repository.get_by_id_and_user.assert_called_once_with(notification_id, owner_id)
    repository.update.assert_not_called()
    repository.delete.assert_not_called()
    repository.create.assert_not_called()
    repository.list_by_user.assert_not_called()


@pytest.mark.parametrize("changes", [
    {}, {"id": str(uuid4())}, {"user_id": str(uuid4())}, {"unexpected": "value"},
    {"title": "Válido", "user_id": str(uuid4())},
])
def test_service_rejects_empty_unknown_or_immutable_changes_before_access(service, repository, changes):
    with pytest.raises(ValueError):
        service.update(uuid4(), uuid4(), changes)
    assert repository.mock_calls == []
