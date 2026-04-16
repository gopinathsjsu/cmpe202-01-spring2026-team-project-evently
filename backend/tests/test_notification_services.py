import logging
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
import resend
from fastapi import FastAPI
from resend.exceptions import ResendError
from starlette.requests import Request

from backend.models.event import Event, EventCategory, Location
from backend.services.notifications.arq import get_arq, get_redis_settings
from backend.services.notifications.email import (
    EmailNotificationService,
    create_email_notification_service,
    get_email_notif_service,
)


def _request_for_app(app: FastAPI) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "app": app,
    }
    return Request(scope)


def _event() -> Event:
    return Event(
        id=11,
        title="Notification Test Event",
        about="An event used to verify notification email payloads",
        organizer_user_id=7,
        price=25.0,
        total_capacity=100,
        start_time=datetime(2026, 8, 1, 10, 0, 0),
        end_time=datetime(2026, 8, 1, 12, 0, 0),
        category=EventCategory.Workshop,
        schedule=[],
        location=Location(
            longitude=-122.4194,
            latitude=37.7749,
            address="123 Main St",
            city="San Francisco",
            state="CA",
            zip_code="94102",
        ),
    )


def _patch_resend_send_async(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    send_async = AsyncMock()
    monkeypatch.setattr(resend.Emails, "send_async", send_async)
    return send_async


def _sent_payload(send_async: AsyncMock) -> dict[str, Any]:
    send_async.assert_awaited_once()
    call = send_async.await_args
    assert call is not None
    payload = call.args[0]
    assert isinstance(payload, dict)
    return payload


def test_get_redis_settings_prefers_explicit_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://env.example.com:6381/4")

    settings = get_redis_settings("redis://explicit.example.com:6380/2")

    assert settings.host == "explicit.example.com"
    assert settings.port == 6380
    assert settings.database == 2


def test_get_redis_settings_uses_env_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://env.example.com:6381/4")

    settings = get_redis_settings()

    assert settings.host == "env.example.com"
    assert settings.port == 6381
    assert settings.database == 4


def test_get_redis_settings_falls_back_to_arq_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)

    settings = get_redis_settings()

    assert settings.host == "localhost"
    assert settings.port == 6379
    assert settings.database == 0


def test_create_email_notification_service_prefers_explicit_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "env-key")

    service = create_email_notification_service("explicit-key")

    assert isinstance(service, EmailNotificationService)
    assert resend.api_key == "explicit-key"


def test_create_email_notification_service_uses_env_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "env-key")

    service = create_email_notification_service()

    assert isinstance(service, EmailNotificationService)
    assert resend.api_key == "env-key"


def test_create_email_notification_service_requires_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        create_email_notification_service()


@pytest.mark.asyncio
async def test_send_event_creation_confirmation_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send_async = _patch_resend_send_async(monkeypatch)
    service = EmailNotificationService(
        "test-key", from_email="Evently <events@example.com>"
    )

    await service.send_event_creation_confirmation("organizer@example.com", _event())

    payload = _sent_payload(send_async)
    assert payload["from"] == "Evently <events@example.com>"
    assert payload["to"] == ["organizer@example.com"]
    assert payload["subject"] == "Evently - Event Creation Confirmation"
    assert "Notification Test Event" in payload["html"]
    assert "Event Created" in payload["html"]


@pytest.mark.asyncio
async def test_send_registration_confirmation_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send_async = _patch_resend_send_async(monkeypatch)
    service = EmailNotificationService(
        "test-key", from_email="Evently <events@example.com>"
    )

    await service.send_registration_confirmation("attendee@example.com", _event())

    payload = _sent_payload(send_async)
    assert payload["from"] == "Evently <events@example.com>"
    assert payload["to"] == ["attendee@example.com"]
    assert payload["subject"] == "Evently - Registration Confirmation"
    assert "Notification Test Event" in payload["html"]
    assert "Registration Confirmed" in payload["html"]


@pytest.mark.asyncio
async def test_send_event_reminder_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send_async = _patch_resend_send_async(monkeypatch)
    service = EmailNotificationService(
        "test-key", from_email="Evently <events@example.com>"
    )

    await service.send_event_reminder("attendee@example.com", _event())

    payload = _sent_payload(send_async)
    assert payload["from"] == "Evently <events@example.com>"
    assert payload["to"] == ["attendee@example.com"]
    assert payload["subject"] == "Evently - Event Reminder"
    assert "Notification Test Event" in payload["html"]
    assert "2026-08-01 10:00:00" in payload["html"]


@pytest.mark.asyncio
async def test_email_service_logs_and_swallows_resend_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    send_async = AsyncMock(
        side_effect=ResendError("500", "server_error", "boom", "retry")
    )
    monkeypatch.setattr(resend.Emails, "send_async", send_async)
    service = EmailNotificationService("test-key")
    event = _event()

    with caplog.at_level(logging.ERROR):
        await service.send_event_creation_confirmation("organizer@example.com", event)
        await service.send_registration_confirmation("attendee@example.com", event)
        await service.send_event_reminder("attendee@example.com", event)

    assert send_async.await_count == 3
    assert "Failed to send event creation confirmation email" in caplog.text
    assert "Failed to send registration confirmation email" in caplog.text
    assert "Failed to send event reminder email" in caplog.text


def test_get_arq_returns_app_state_object() -> None:
    app = FastAPI()
    arq = object()
    app.state.arq = arq

    assert get_arq(_request_for_app(app)) is arq


def test_get_arq_raises_when_missing() -> None:
    app = FastAPI()

    with pytest.raises(RuntimeError, match="ArqRedis not initialized"):
        get_arq(_request_for_app(app))


def test_get_email_notif_service_returns_app_state_object() -> None:
    app = FastAPI()
    service = EmailNotificationService("test-key")
    app.state.email_notification_service = service

    assert get_email_notif_service(_request_for_app(app)) is service


def test_get_email_notif_service_raises_when_missing() -> None:
    app = FastAPI()

    with pytest.raises(RuntimeError, match="EmailNotificationService not initialized"):
        get_email_notif_service(_request_for_app(app))
