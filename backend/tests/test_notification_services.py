from typing import Any

import pytest
from fastapi import FastAPI
from starlette.requests import Request

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

    assert service._resend_api_key == "explicit-key"


def test_create_email_notification_service_uses_env_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "env-key")

    service = create_email_notification_service()

    assert service._resend_api_key == "env-key"


def test_create_email_notification_service_requires_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RESEND_API_KEY", raising=False)

    with pytest.raises(ValueError, match="RESEND_API_KEY"):
        create_email_notification_service()


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
