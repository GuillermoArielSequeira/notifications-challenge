from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hashes_are_salted_and_preserve_password():
    password = "  secure-password-with-spaces  "
    first = hash_password(password)
    second = hash_password(password)
    assert first != second
    assert verify_password(password, first)
    assert not verify_password(password.strip(), first)


def test_access_token_roundtrip():
    user_id = uuid4()
    assert decode_access_token(create_access_token(user_id)) == user_id


@pytest.mark.parametrize("key", ["", "too-short"])
def test_signing_key_must_be_strong(key):
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key=key)


@pytest.mark.parametrize("minutes", [0, -1, 1441])
def test_token_expiration_must_be_bounded(minutes):
    with pytest.raises(ValidationError):
        Settings(jwt_access_token_expire_minutes=minutes)
