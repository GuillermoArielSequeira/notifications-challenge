from pydantic import BaseModel, EmailStr, Field, ValidationError, field_validator

from app.services.delivery.sender import DeliveryValidationError


class _EmailRecipient(BaseModel):
    email: EmailStr = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class EmailDeliveryStrategy:
    def validate(self, recipient: str, content: str) -> str:
        try:
            return _EmailRecipient(email=recipient).email
        except ValidationError:
            raise DeliveryValidationError("recipient", "invalid_recipient_email") from None

    def prepare(self, title: str, content: str) -> str:
        return title + "\n\n" + content

    def protect_recipient(self, recipient: str) -> str:
        return "[redacted]"
