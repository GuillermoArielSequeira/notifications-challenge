from uuid import UUID

from app.models.notification import Notification
from app.repositories.notifications import NotificationRepository
from app.services.delivery.sender import NotificationSender


class NotificationNotFoundError(Exception):
    pass


class NotificationService:
    def __init__(self, notifications: NotificationRepository, sender: NotificationSender):
        self.notifications = notifications
        self.sender = sender

    def create(
        self, user_id: UUID, title: str, content: str, channel: str, recipient: str
    ) -> Notification:
        self.sender.simulate(channel, recipient, title, content)
        return self.notifications.create(user_id, title, content, channel)

    def list_own(self, user_id: UUID) -> list[Notification]:
        return self.notifications.list_by_user(user_id)

    def update(
        self, user_id: UUID, notification_id: UUID, changes: dict[str, str]
    ) -> Notification:
        if not changes or changes.keys() - {"title", "content", "channel"}:
            raise ValueError("La modificación debe incluir únicamente campos modificables.")
        notification = self.notifications.get_by_id_and_user(notification_id, user_id)
        if notification is None:
            raise NotificationNotFoundError
        return self.notifications.update(notification, changes)

    def delete(self, user_id: UUID, notification_id: UUID) -> None:
        notification = self.notifications.get_by_id_and_user(notification_id, user_id)
        if notification is None:
            raise NotificationNotFoundError
        self.notifications.delete(notification)
