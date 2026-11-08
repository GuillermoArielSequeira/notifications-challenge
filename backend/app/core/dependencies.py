from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.notifications import NotificationRepository
from app.repositories.users import UserRepository
from app.services.auth import AuthService
from app.services.notifications import NotificationService


bearer = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_auth_service(db: DatabaseSession) -> AuthService:
    return AuthService(UserRepository(db))


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


def get_notification_service(db: DatabaseSession) -> NotificationService:
    return NotificationService(NotificationRepository(db))


NotificationServiceDependency = Annotated[NotificationService, Depends(get_notification_service)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: DatabaseSession,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        user_id = decode_access_token(credentials.credentials)
    except (InvalidTokenError, ValueError, TypeError):
        raise unauthorized from None
    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
