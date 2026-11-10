from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.notification import Notification


class NotificationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, user_id: UUID, title: str, content: str, channel: str) -> Notification:
        notification = Notification(user_id=user_id, title=title, content=content, channel=channel)
        try:
            self.session.add(notification)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        self.session.refresh(notification)
        return notification

    def list_by_user(self, user_id: UUID) -> list[Notification]:
        return list(self.session.scalars(select(Notification).where(Notification.user_id == user_id)))

    def get_by_id_and_user(self, notification_id: UUID, user_id: UUID) -> Notification | None:
        return self.session.scalar(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        )

    def update(self, notification: Notification, changes: dict[str, str]) -> Notification:
        # Changes contain only editable fields already validated by the caller.
        try:
            for field, value in changes.items():
                setattr(notification, field, value)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
        self.session.refresh(notification)
        return notification

    def delete(self, notification: Notification) -> None:
        try:
            self.session.delete(notification)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise
