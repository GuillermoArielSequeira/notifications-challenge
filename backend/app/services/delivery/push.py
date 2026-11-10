from app.services.delivery.sender import DeliveryValidationError


class PushDeliveryStrategy:
    def validate(self, recipient: str, content: str) -> str:
        if not 1 <= len(recipient) <= 512 or any(
            character < "!" or character > "~" for character in recipient
        ):
            raise DeliveryValidationError("recipient", "invalid_recipient_push")
        return recipient

    def prepare(self, title: str, content: str) -> dict[str, str]:
        return {"title": title, "body": content}

    def protect_recipient(self, recipient: str) -> str:
        return "[redacted]"
