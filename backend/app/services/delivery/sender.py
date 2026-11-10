from collections.abc import Mapping
from typing import Protocol

from app.services.delivery.logging import DeliveryRecorder


class DeliveryStrategy(Protocol):
    def validate(self, recipient: str, content: str) -> str: ...

    def prepare(self, title: str, content: str) -> str | dict[str, str]: ...

    def protect_recipient(self, recipient: str) -> str: ...


class DeliveryValidationError(Exception):
    def __init__(self, field: str, code: str):
        self.field = field
        self.code = code
        super().__init__(field, code)


class DeliveryExecutionError(Exception):
    def __init__(self):
        super().__init__("Notification delivery failed.")


class NotificationSender:
    def __init__(
        self,
        strategies: Mapping[str, DeliveryStrategy],
        recorder: DeliveryRecorder,
    ):
        self._strategies = strategies
        self._recorder = recorder

    def simulate(
        self,
        channel: str,
        recipient: str,
        title: str,
        content: str,
    ) -> None:
        try:
            strategy = self._strategies[channel]
        except (KeyError, TypeError):
            raise DeliveryExecutionError from None

        try:
            validated_recipient = strategy.validate(recipient, content)
        except DeliveryValidationError:
            raise
        except Exception:
            raise DeliveryExecutionError from None

        try:
            strategy.prepare(title, content)
        except Exception:
            self._record_failed_for_validated_recipient(
                channel,
                strategy,
                validated_recipient,
            )
            raise DeliveryExecutionError from None

        try:
            protected_recipient = strategy.protect_recipient(validated_recipient)
        except Exception:
            raise DeliveryExecutionError from None

        try:
            self._recorder.record(channel, "simulated", protected_recipient)
        except Exception:
            raise DeliveryExecutionError from None

    def _record_failure(
        self,
        channel: str,
        protected_recipient: str | None,
    ) -> None:
        if protected_recipient is None:
            return
        try:
            self._recorder.record(channel, "failed", protected_recipient)
        except Exception:
            return

    def _record_failed_for_validated_recipient(
        self,
        channel: str,
        strategy: DeliveryStrategy,
        validated_recipient: str,
    ) -> None:
        try:
            protected_recipient = strategy.protect_recipient(validated_recipient)
        except Exception:
            return
        self._record_failure(channel, protected_recipient)
