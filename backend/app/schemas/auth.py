from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class EmailCredentials(BaseModel):
    email: EmailStr = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # Accounts deliberately treat both parts of an email as case-insensitive.
        return value.lower()


class RegisterRequest(EmailCredentials):
    password: str = Field(
        min_length=8, max_length=128, repr=False,
        json_schema_extra={"format": "password", "writeOnly": True},
    )


class LoginRequest(EmailCredentials):
    password: str = Field(
        min_length=1, max_length=128, repr=False,
        json_schema_extra={"format": "password", "writeOnly": True},
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
