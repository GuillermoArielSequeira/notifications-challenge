import re

from app.services.delivery.sender import DeliveryValidationError


SMS_RECIPIENT_PATTERN = re.compile(r"\+[1-9][0-9]{7,14}")


class SmsDeliveryStrategy:
    def validate(self, recipient: str, content: str) -> str:
        if SMS_RECIPIENT_PATTERN.fullmatch(recipient) is None:
            raise DeliveryValidationError("recipient", "invalid_recipient_sms")
        if len(content) > 160:
            raise DeliveryValidationError("content", "sms_too_long")
        return recipient

    def prepare(self, title: str, content: str) -> str:
        return content

    def protect_recipient(self, recipient: str) -> str:
        return "*" * (len(recipient) - 4) + recipient[-4:]
