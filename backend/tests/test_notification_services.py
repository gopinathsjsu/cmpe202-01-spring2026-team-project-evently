import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from typing import Any, cast

import pytest
import resend
from fastapi import FastAPI
from resend.exceptions import ResendError
from resend.http_client_async import AsyncHTTPClient
from starlette.requests import Request

from backend.models.event import Event, EventCategory, Location
from backend.services.notifications.arq import get_arq, get_redis_settings
from backend.services.notifications.email import (
    EmailNotificationService,
    create_email_notification_service,
    get_email_notif_service,
)


class _RecordingAsyncHTTPClient(AsyncHTTPClient):
    def __init__(self) -> None:
        self.requests: list[
            tuple[str, str, Mapping[str, str], dict[str, object] | list[object] | None]
        ] = []

    async def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        json: dict[str, object] | list[object] | None = None,
    ) -> tuple[bytes, int, Mapping[str, str]]:
        self.requests.append((method, url, dict(headers), json))
        return b'{"id":"email-id"}', 200, {"content-type": "application/json"}


class _RecordingEmailSender:
    def __init__(self, side_effect: ResendError | None = None) -> None:
        self.payloads: list[Mapping[str, object]] = []
        self.side_effect = side_effect

    async def send_async(self, params: Mapping[str, object]) -> None:
        self.payloads.append(params)
        if self.side_effect is not None:
            raise self.side_effect


def _request_for_app(app: FastAPI) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "app": app,
    }
    return Request(scope)


def _event(title: str = "Notification Test Event") -> Event:
    return Event(
        id=11,
        title=title,
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


def _sent_payload(email_sender: _RecordingEmailSender) -> Mapping[str, Any]:
    assert len(email_sender.payloads) == 1
    return cast(Mapping[str, Any], email_sender.payloads[0])


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


@pytest.mark.asyncio
async def test_create_email_notification_service_prefers_explicit_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "env-key")
    monkeypatch.setattr(resend, "api_key", "global-key")
    http_client = _RecordingAsyncHTTPClient()
    monkeypatch.setattr(resend, "default_async_http_client", http_client)

    service = create_email_notification_service("explicit-key")
    await service.send_event_reminder("attendee@example.com", _event())

    assert isinstance(service, EmailNotificationService)
    assert http_client.requests[0][2]["Authorization"] == "Bearer explicit-key"
    assert resend.api_key == "global-key"


@pytest.mark.asyncio
async def test_create_email_notification_service_uses_env_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "env-key")
    monkeypatch.setattr(resend, "api_key", "global-key")
    http_client = _RecordingAsyncHTTPClient()
    monkeypatch.setattr(resend, "default_async_http_client", http_client)

    service = create_email_notification_service()
    await service.send_event_reminder("attendee@example.com", _event())

    assert isinstance(service, EmailNotificationService)
    assert http_client.requests[0][2]["Authorization"] == "Bearer env-key"
    assert resend.api_key == "global-key"


def test_email_service_constructor_does_not_mutate_resend_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resend, "api_key", "global-key")

    EmailNotificationService("service-key")

    assert resend.api_key == "global-key"


def test_create_email_notification_service_requires_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        create_email_notification_service()


@pytest.mark.asyncio
async def test_send_event_creation_confirmation_payload() -> None:
    email_sender = _RecordingEmailSender()
    service = EmailNotificationService(
        "test-key",
        from_email="Evently <events@example.com>",
        email_sender=email_sender,
    )

    await service.send_event_creation_confirmation("organizer@example.com", _event())

    payload = _sent_payload(email_sender)
    assert payload["from"] == "Evently <events@example.com>"
    assert payload["to"] == ["organizer@example.com"]
    assert payload["subject"] == "Evently - Event Creation Confirmation"
    assert "Notification Test Event" in payload["html"]
    assert "Event Created" in payload["html"]


@pytest.mark.asyncio
async def test_send_registration_confirmation_payload() -> None:
    email_sender = _RecordingEmailSender()
    service = EmailNotificationService(
        "test-key",
        from_email="Evently <events@example.com>",
        email_sender=email_sender,
    )

    await service.send_registration_confirmation("attendee@example.com", _event())

    payload = _sent_payload(email_sender)
    assert payload["from"] == "Evently <events@example.com>"
    assert payload["to"] == ["attendee@example.com"]
    assert payload["subject"] == "Evently - Registration Confirmation"
    assert "Notification Test Event" in payload["html"]
    assert "Registration Confirmed" in payload["html"]


@pytest.mark.asyncio
async def test_send_event_reminder_payload() -> None:
    email_sender = _RecordingEmailSender()
    service = EmailNotificationService(
        "test-key",
        from_email="Evently <events@example.com>",
        email_sender=email_sender,
    )

    await service.send_event_reminder("attendee@example.com", _event())

    payload = _sent_payload(email_sender)
    assert payload["from"] == "Evently <events@example.com>"
    assert payload["to"] == ["attendee@example.com"]
    assert payload["subject"] == "Evently - Event Reminder"
    assert "Notification Test Event" in payload["html"]
    assert "2026-08-01 10:00:00" in payload["html"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method_name",
    [
        "send_event_creation_confirmation",
        "send_registration_confirmation",
        "send_event_reminder",
    ],
)
async def test_email_html_escapes_event_title(method_name: str) -> None:
    email_sender = _RecordingEmailSender()
    service = EmailNotificationService("test-key", email_sender=email_sender)
    malicious_title = '"><img src=x onerror=alert(1)></p><script>alert(1)</script>&'

    send_email = cast(
        Callable[[str, Event], Awaitable[None]],
        getattr(service, method_name),
    )
    await send_email("attendee@example.com", _event(title=malicious_title))

    html = cast(str, _sent_payload(email_sender)["html"])
    assert malicious_title not in html
    assert "<img" not in html
    assert "</p><script>" not in html
    assert (
        "&quot;&gt;&lt;img src=x onerror=alert(1)&gt;&lt;/p&gt;"
        "&lt;script&gt;alert(1)&lt;/script&gt;&amp;"
    ) in html


@pytest.mark.asyncio
async def test_email_service_logs_and_swallows_resend_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    email_sender = _RecordingEmailSender(
        ResendError("500", "server_error", "boom", "retry")
    )
    service = EmailNotificationService("test-key", email_sender=email_sender)
    event = _event()

    with caplog.at_level(logging.ERROR):
        await service.send_event_creation_confirmation("organizer@example.com", event)
        await service.send_registration_confirmation("attendee@example.com", event)
        await service.send_event_reminder("attendee@example.com", event)

    assert len(email_sender.payloads) == 3
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

    with pytest.raises(RuntimeError, match="ArqClient not initialized"):
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
