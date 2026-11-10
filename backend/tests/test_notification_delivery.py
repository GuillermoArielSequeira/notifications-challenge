import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, call, patch

import pytest

from app.schemas.auth import EmailCredentials
from app.services.delivery.email import EmailDeliveryStrategy
from app.services.delivery.logging import (
    DeliveryLogHandler,
    DeliveryRecorder,
    DeliveryRecordingError,
    create_delivery_logger,
)
from app.services.delivery.push import PushDeliveryStrategy
from app.services.delivery.sender import (
    DeliveryExecutionError,
    DeliveryValidationError,
    NotificationSender,
)
from app.services.delivery.sms import SmsDeliveryStrategy


def assert_validation_error(call, field, code, secret):
    with pytest.raises(DeliveryValidationError) as error:
        call()
    assert error.value.field == field
    assert error.value.code == code
    assert vars(error.value) == {"field": field, "code": code}
    if secret:
        assert secret not in str(error.value)
        assert secret not in repr(error.value)


@pytest.mark.parametrize("recipient", [
    "  Recipient@Example.COM  ",
    f"{'a' * 64}@{'b' * 63}.{'c' * 63}.{'d' * 61}",
])
def test_email_validation_matches_registration_contract_and_does_not_query_dns(recipient):
    strategy = EmailDeliveryStrategy()
    with patch("dns.resolver.Resolver.resolve") as resolve:
        assert strategy.validate(recipient, "content") == EmailCredentials(email=recipient).email
    resolve.assert_not_called()


def test_email_validation_rejects_invalid_or_too_long_recipient_safely():
    strategy = EmailDeliveryStrategy()
    for recipient in ("not-an-email", f"{'a' * 64}@{'b' * 63}.{'c' * 63}.{'d' * 62}"):
        assert_validation_error(
            lambda recipient=recipient: strategy.validate(recipient, "content"),
            "recipient",
            "invalid_recipient_email",
            recipient,
        )


def test_email_preparation_preserves_title_content_and_recipient_is_redacted():
    strategy = EmailDeliveryStrategy()
    title = "  Título\n"
    content = "\n Contenido con espacios \t"
    assert strategy.prepare(title, content) == title + "\n\n" + content
    assert strategy.protect_recipient("recipient@example.com") == "[redacted]"


@pytest.mark.parametrize("recipient", ["+12345678", "+123456789012345"])
def test_sms_validation_accepts_ascii_digit_bounds(recipient):
    assert SmsDeliveryStrategy().validate(recipient, "content") == recipient


@pytest.mark.parametrize("recipient", [
    "+1234567",
    "+1234567890123456",
    "+02345678",
    "12345678",
    "+123 45678",
    "+123-45678",
    "+12345678\n",
    "+١٢٣٤٥٦٧٨",
])
def test_sms_validation_rejects_nonconforming_recipients_safely(recipient):
    assert_validation_error(
        lambda: SmsDeliveryStrategy().validate(recipient, "content"),
        "recipient",
        "invalid_recipient_sms",
        recipient,
    )


@pytest.mark.parametrize("content", [
    "é" * 159,
    "😀" * 160,
    "e\u0301" * 80,
    " \n" * 80,
])
def test_sms_validation_counts_unicode_code_points_without_normalizing(content):
    strategy = SmsDeliveryStrategy()
    assert len(content) <= 160
    assert strategy.validate("+12345678", content) == "+12345678"
    assert strategy.prepare("ignored title", content) == content


@pytest.mark.parametrize("content", ["é" * 161, "e\u0301" * 80 + "x"])
def test_sms_validation_rejects_161_code_points_without_truncation(content):
    strategy = SmsDeliveryStrategy()
    assert len(content) == 161
    assert_validation_error(
        lambda: strategy.validate("+12345678", content),
        "content",
        "sms_too_long",
        content,
    )
    assert strategy.prepare("ignored title", content) == content


def test_sms_recipient_validation_precedes_content_length_validation():
    recipient = "+1234567"
    content = "x" * 161
    assert_validation_error(
        lambda: SmsDeliveryStrategy().validate(recipient, content),
        "recipient",
        "invalid_recipient_sms",
        recipient,
    )


def test_sms_protection_masks_every_character_before_last_four_digits():
    assert SmsDeliveryStrategy().protect_recipient("+12345678901") == "********8901"


@pytest.mark.parametrize("recipient", ["!", "~" * 512])
def test_push_validation_accepts_visible_ascii_bounds_without_normalizing(recipient):
    assert PushDeliveryStrategy().validate(recipient, "content") == recipient


@pytest.mark.parametrize("recipient", [
    "",
    "!" * 513,
    "contains space",
    "contains\ttab",
    "contains\nnewline",
    "contains\x7fdel",
    "token-á",
])
def test_push_validation_rejects_invalid_bounds_and_characters_safely(recipient):
    assert_validation_error(
        lambda: PushDeliveryStrategy().validate(recipient, "content"),
        "recipient",
        "invalid_recipient_push",
        recipient,
    )


def test_push_preparation_excludes_recipient_and_protection_is_complete():
    strategy = PushDeliveryStrategy()
    recipient = "device-token-demo"
    assert strategy.prepare("Título", "Contenido") == {"title": "Título", "body": "Contenido"}
    assert recipient not in strategy.prepare("Título", "Contenido").values()
    assert strategy.protect_recipient(recipient) == "[redacted]"


def test_delivery_exceptions_only_expose_safe_information():
    validation_error = DeliveryValidationError("recipient", "invalid_recipient_sms")
    execution_error = DeliveryExecutionError()
    secret = "private-recipient-value"

    assert vars(validation_error) == {
        "field": "recipient",
        "code": "invalid_recipient_sms",
    }
    assert secret not in str(validation_error)
    assert secret not in repr(validation_error)
    assert vars(execution_error) == {}
    assert str(execution_error) == "Notification delivery failed."
    assert secret not in repr(execution_error)


@pytest.mark.parametrize(
    "channel, recipient, normalized_recipient, title, content, strategy_factory, protected_recipient",
    [
        (
            "email",
            "  Recipient@Example.COM  ",
            "recipient@example.com",
            "Email title",
            "Email content",
            EmailDeliveryStrategy,
            "[redacted]",
        ),
        (
            "sms",
            "+12345678901",
            "+12345678901",
            "SMS title",
            "SMS content",
            SmsDeliveryStrategy,
            "********8901",
        ),
        (
            "push",
            "device-token-demo",
            "device-token-demo",
            "Push title",
            "Push content",
            PushDeliveryStrategy,
            "[redacted]",
        ),
    ],
)
def test_notification_sender_selects_one_actual_strategy_in_order(
    channel,
    recipient,
    normalized_recipient,
    title,
    content,
    strategy_factory,
    protected_recipient,
):
    selected_strategy = Mock(wraps=strategy_factory())
    other_strategies = {
        other_channel: Mock()
        for other_channel in {"email", "sms", "push"} - {channel}
    }
    recorder = Mock()
    calls = Mock()
    calls.attach_mock(selected_strategy, "strategy")
    calls.attach_mock(recorder, "recorder")
    sender = NotificationSender(
        {channel: selected_strategy, **other_strategies},
        recorder,
    )

    sender.simulate(channel, recipient, title, content)

    assert calls.mock_calls == [
        call.strategy.validate(recipient, content),
        call.strategy.prepare(title, content),
        call.strategy.protect_recipient(normalized_recipient),
        call.recorder.record(channel, "simulated", protected_recipient),
    ]
    for strategy in other_strategies.values():
        strategy.assert_not_called()


def test_notification_sender_uses_validated_recipient_for_protection_and_recording():
    strategy = Mock()
    strategy.validate.return_value = "normalized-recipient"
    strategy.protect_recipient.return_value = "[redacted]"
    recorder = Mock()
    sender = NotificationSender({"email": strategy}, recorder)

    sender.simulate("email", "original-recipient", "Title", "Content")

    strategy.protect_recipient.assert_called_once_with("normalized-recipient")
    recorder.record.assert_called_once_with("email", "simulated", "[redacted]")


def test_notification_sender_allows_a_fictional_strategy_registered_only_in_its_map():
    class FictionalDeliveryStrategy:
        def validate(self, recipient, content):
            return recipient

        def prepare(self, title, content):
            return f"{title}:{content}"

        def protect_recipient(self, recipient):
            return "fictional-protected"

    recorder = Mock()
    sender = NotificationSender({"fictional": FictionalDeliveryStrategy()}, recorder)

    sender.simulate("fictional", "fictional-recipient", "Title", "Content")

    recorder.record.assert_called_once_with(
        "fictional", "simulated", "fictional-protected"
    )


def test_notification_sender_stops_after_validation_error_without_recording():
    strategy = Mock()
    strategy.validate.side_effect = DeliveryValidationError(
        "recipient", "invalid_recipient_email"
    )
    recorder = Mock()
    sender = NotificationSender({"email": strategy}, recorder)

    with pytest.raises(DeliveryValidationError):
        sender.simulate("email", "invalid", "Title", "Content")

    strategy.prepare.assert_not_called()
    strategy.protect_recipient.assert_not_called()
    recorder.record.assert_not_called()


def test_notification_sender_records_one_protected_failure_after_preparation_error():
    secret = "preparation-error-secret"
    strategy = Mock()
    strategy.validate.return_value = "normalized-recipient"
    strategy.prepare.side_effect = RuntimeError(secret)
    strategy.protect_recipient.return_value = "[redacted]"
    recorder = Mock()
    calls = Mock()
    calls.attach_mock(strategy, "strategy")
    calls.attach_mock(recorder, "recorder")
    sender = NotificationSender({"email": strategy}, recorder)

    with pytest.raises(DeliveryExecutionError) as error:
        sender.simulate("email", "original-recipient", "Title", "Content")

    assert calls.mock_calls == [
        call.strategy.validate("original-recipient", "Content"),
        call.strategy.prepare("Title", "Content"),
        call.strategy.protect_recipient("normalized-recipient"),
        call.recorder.record("email", "failed", "[redacted]"),
    ]
    assert secret not in str(error.value)
    assert secret not in repr(error.value)


def test_notification_sender_does_not_retry_when_simulated_recording_fails():
    strategy = Mock()
    strategy.validate.return_value = "normalized-recipient"
    strategy.protect_recipient.return_value = "[redacted]"
    recorder = Mock()
    recorder.record.side_effect = DeliveryRecordingError()
    sender = NotificationSender({"email": strategy}, recorder)

    with pytest.raises(DeliveryExecutionError, match="Notification delivery failed\\."):
        sender.simulate("email", "original-recipient", "Title", "Content")

    recorder.record.assert_called_once_with("email", "simulated", "[redacted]")


def test_notification_sender_does_not_retry_when_failed_recording_fails():
    strategy = Mock()
    strategy.validate.return_value = "normalized-recipient"
    strategy.prepare.side_effect = RuntimeError("preparation failure")
    strategy.protect_recipient.return_value = "[redacted]"
    recorder = Mock()
    recorder.record.side_effect = DeliveryRecordingError()
    sender = NotificationSender({"email": strategy}, recorder)

    with pytest.raises(DeliveryExecutionError, match="Notification delivery failed\\."):
        sender.simulate("email", "original-recipient", "Title", "Content")

    recorder.record.assert_called_once_with("email", "failed", "[redacted]")


def test_notification_sender_does_not_retry_when_recorder_clock_fails():
    secret = "clock-failure-secret"
    strategy = Mock()
    strategy.validate.return_value = "normalized-recipient"
    strategy.protect_recipient.return_value = "[redacted]"
    clock = Mock(side_effect=RuntimeError(secret))
    recorder = DeliveryRecorder(Mock(), clock)
    sender = NotificationSender({"email": strategy}, recorder)

    with pytest.raises(DeliveryExecutionError) as error:
        sender.simulate("email", "original-recipient", "Title", "Content")

    assert clock.call_count == 1
    assert secret not in str(error.value)
    assert secret not in repr(error.value)


def test_notification_sender_rejects_a_missing_strategy_mapping_safely():
    secret = "unmapped-channel-secret"
    recorder = Mock()
    sender = NotificationSender({}, recorder)

    with pytest.raises(DeliveryExecutionError) as error:
        sender.simulate(secret, "recipient", "Title", "Content")

    recorder.assert_not_called()
    assert str(error.value) == "Notification delivery failed."
    assert secret not in str(error.value)
    assert secret not in repr(error.value)


@pytest.mark.parametrize(
    "channel, recipient, title, content, protected_recipient",
    [
        ("email", "recipient@example.com", "Email title", "Email content", "[redacted]"),
        ("sms", "+12345678901", "SMS title", "SMS content", "********8901"),
        ("push", "device-token-demo", "Push title", "Push content", "[redacted]"),
    ],
)
def test_notification_sender_with_real_components_emits_protected_json(
    capsys, channel, recipient, title, content, protected_recipient
):
    recorder = DeliveryRecorder(
        _logger_with_handler(DeliveryLogHandler()),
        lambda: datetime(2026, 11, 9, tzinfo=timezone.utc),
    )
    sender = NotificationSender(
        {
            "email": EmailDeliveryStrategy(),
            "sms": SmsDeliveryStrategy(),
            "push": PushDeliveryStrategy(),
        },
        recorder,
    )

    sender.simulate(channel, recipient, title, content)

    output = capsys.readouterr().err
    assert json.loads(output) == {
        "event": "notification_delivery",
        "channel": channel,
        "status": "simulated",
        "timestamp": "2026-11-09T00:00:00+00:00",
        "recipient": protected_recipient,
    }
    assert recipient not in output
    assert title not in output
    assert content not in output


def _logger_with_handler(handler):
    logger = logging.Logger("delivery-recorder-test")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    return logger


def test_delivery_recorder_emits_exactly_allowed_json_fields_in_utc(capsys):
    clock = Mock(return_value=datetime(2026, 11, 9, 10, 30, tzinfo=timezone(timedelta(hours=-3))))
    recorder = DeliveryRecorder(
        _logger_with_handler(DeliveryLogHandler()),
        clock,
    )

    recorder.record("sms", "simulated", "********8901")
    recorder.record("email", "failed", "[redacted]")

    lines = capsys.readouterr().err.splitlines()
    assert [json.loads(line) for line in lines] == [
        {
            "event": "notification_delivery",
            "channel": "sms",
            "status": "simulated",
            "timestamp": "2026-11-09T13:30:00+00:00",
            "recipient": "********8901",
        },
        {
            "event": "notification_delivery",
            "channel": "email",
            "status": "failed",
            "timestamp": "2026-11-09T13:30:00+00:00",
            "recipient": "[redacted]",
        },
    ]
    assert all(set(json.loads(line)) == {
        "event", "channel", "status", "timestamp", "recipient"
    } for line in lines)
    assert clock.call_count == 2


def test_delivery_recorder_output_does_not_include_sensitive_values(capsys):
    secrets = [
        "recipient@example.com",
        "device-token-secret",
        "jwt-secret-value",
        "password-secret-value",
        "title-secret-value",
        "content-secret-value",
        "template-secret-value",
        "payload-secret-value",
    ]
    recorder = DeliveryRecorder(
        _logger_with_handler(DeliveryLogHandler()),
        lambda: datetime(2026, 11, 9, tzinfo=timezone.utc),
    )

    recorder.record("push", "simulated", "[redacted]")

    output = capsys.readouterr().err
    event = json.loads(output)
    assert event["recipient"] == "[redacted]"
    assert all(secret not in output for secret in secrets)


@pytest.mark.parametrize(
    "channel, status, recipient",
    [
        ("unknown", "simulated", "[redacted]"),
        ("email", "unknown", "[redacted]"),
        ("email", "simulated", object()),
    ],
)
def test_delivery_recorder_rejects_values_outside_its_safe_primitives(channel, status, recipient):
    recorder = DeliveryRecorder(
        _logger_with_handler(DeliveryLogHandler()),
        lambda: datetime(2026, 11, 9, tzinfo=timezone.utc),
    )

    with pytest.raises(DeliveryRecordingError, match="Notification delivery logging failed\\."):
        recorder.record(channel, status, recipient)


@pytest.mark.parametrize("failure_point", ["format", "write", "flush"])
def test_delivery_log_handler_failures_propagate_safely_without_global_changes(
    capsys, failure_point
):
    secret = "handler-failure-secret"
    stream = Mock()
    handler = DeliveryLogHandler(stream)
    if failure_point == "format":
        formatter = Mock()
        formatter.format.side_effect = RuntimeError(secret)
        handler.setFormatter(formatter)
    elif failure_point == "write":
        stream.write.side_effect = RuntimeError(secret)
    else:
        stream.flush.side_effect = RuntimeError(secret)
    recorder = DeliveryRecorder(
        _logger_with_handler(handler),
        lambda: datetime(2026, 11, 9, tzinfo=timezone.utc),
    )
    root_handlers = list(logging.getLogger().handlers)
    raise_exceptions = logging.raiseExceptions

    with pytest.raises(DeliveryRecordingError, match="Notification delivery logging failed\\."):
        recorder.record("email", "simulated", "[redacted]")

    assert secret not in capsys.readouterr().err
    assert logging.raiseExceptions is raise_exceptions
    assert logging.getLogger().handlers == root_handlers


def test_delivery_recorder_clock_failure_propagates_without_emitting_sensitive_data(capsys):
    secret = "clock-failure-secret"
    recorder = DeliveryRecorder(
        _logger_with_handler(DeliveryLogHandler()),
        Mock(side_effect=RuntimeError(secret)),
    )

    with pytest.raises(DeliveryRecordingError, match="Notification delivery logging failed\\."):
        recorder.record("email", "simulated", "[redacted]")

    assert secret not in capsys.readouterr().err


def test_delivery_recorder_rejects_naive_clock_values_without_local_interpretation():
    recorder = DeliveryRecorder(
        _logger_with_handler(DeliveryLogHandler()),
        lambda: datetime(2026, 11, 9, 10, 30),
    )

    with pytest.raises(DeliveryRecordingError, match="Notification delivery logging failed\\."):
        recorder.record("email", "simulated", "[redacted]")


def test_delivery_logger_is_dedicated_and_does_not_duplicate_handlers():
    root_handlers = list(logging.getLogger().handlers)
    raise_exceptions = logging.raiseExceptions

    logger = create_delivery_logger()
    repeated_logger = create_delivery_logger()

    assert logger is repeated_logger
    assert logger.propagate is False
    assert logger.level == logging.INFO
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], DeliveryLogHandler)
    assert logging.raiseExceptions is raise_exceptions
    assert logging.getLogger().handlers == root_handlers
