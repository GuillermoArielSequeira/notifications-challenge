import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone


class DeliveryRecordingError(Exception):
    def __init__(self):
        super().__init__("Notification delivery logging failed.")


class DeliveryLogHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self.stream.write(message + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:
        raise DeliveryRecordingError from None


_DELIVERY_LOGGER_NAME = "app.services.delivery.events"
_ALLOWED_CHANNELS = frozenset({"email", "sms", "push"})
_ALLOWED_STATUSES = frozenset({"simulated", "failed"})
_PROTECTED_SMS_RECIPIENT = re.compile(r"\*{5,12}[0-9]{4}")


def create_delivery_logger() -> logging.Logger:
    logger = logging.getLogger(_DELIVERY_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        if not isinstance(handler, DeliveryLogHandler):
            logger.removeHandler(handler)
    handlers = [
        handler for handler in logger.handlers if isinstance(handler, DeliveryLogHandler)
    ]
    if not handlers:
        handler = DeliveryLogHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    else:
        for handler in handlers[1:]:
            logger.removeHandler(handler)

    return logger


class DeliveryRecorder:
    def __init__(
        self,
        logger: logging.Logger,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._logger = logger
        self._clock = clock

    def record(self, channel: str, status: str, protected_recipient: str) -> None:
        try:
            self._validate_inputs(channel, status, protected_recipient)
            timestamp = self._clock()
            if not isinstance(timestamp, datetime) or timestamp.utcoffset() is None:
                raise DeliveryRecordingError
            event = {
                "event": "notification_delivery",
                "channel": channel,
                "status": status,
                "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
                "recipient": protected_recipient,
            }
            self._logger.info(json.dumps(event, separators=(",", ":")))
        except DeliveryRecordingError:
            raise
        except Exception:
            raise DeliveryRecordingError from None

    @staticmethod
    def _validate_inputs(channel: str, status: str, protected_recipient: str) -> None:
        if (
            not isinstance(channel, str)
            or not isinstance(status, str)
            or not isinstance(protected_recipient, str)
            or channel not in _ALLOWED_CHANNELS
            or status not in _ALLOWED_STATUSES
        ):
            raise DeliveryRecordingError
        if channel in {"email", "push"} and protected_recipient != "[redacted]":
            raise DeliveryRecordingError
        if channel == "sms" and _PROTECTED_SMS_RECIPIENT.fullmatch(protected_recipient) is None:
            raise DeliveryRecordingError
