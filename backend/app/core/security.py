from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


ALGORITHM = "HS256"
password_hasher = PasswordHash.recommended()
# Perform a real password verification even for unknown users.
DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-user-password")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> UUID:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[ALGORITHM],
        options={"require": ["sub", "iat", "exp"]},
    )
    return UUID(payload["sub"])
