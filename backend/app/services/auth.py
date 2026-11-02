from app.core.security import DUMMY_PASSWORD_HASH, hash_password, verify_password
from app.models.user import User
from app.repositories.users import UserRepository


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, users: UserRepository):
        self.users = users

    def register(self, email: str, password: str) -> User:
        return self.users.create(email, hash_password(password))

    def login(self, email: str, password: str) -> User:
        user = self.users.get_by_email(email)
        valid = verify_password(
            password, user.password_hash if user else DUMMY_PASSWORD_HASH
        )
        if not user or not valid:
            raise InvalidCredentialsError
        return user
