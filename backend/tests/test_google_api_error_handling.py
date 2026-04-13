from collections.abc import Mapping
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend.routes import auth as auth_routes
from backend.services import calendar_sync


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        is_success: bool,
        json_body: object = None,
        json_error: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.is_success = is_success
        self._json_body = json_body
        self._json_error = json_error

    def json(self) -> object:
        if self._json_error is not None:
            raise self._json_error
        return self._json_body


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(
        self,
        _exc_type: object,
        _exc: object,
        _tb: object,
    ) -> None:
        return None

    async def post(self, *args: object, **kwargs: object) -> _FakeResponse:
        return self._response


@pytest.mark.asyncio
async def test_create_google_calendar_event_invalid_json_raises_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeResponse(
        status_code=200,
        is_success=True,
        json_error=ValueError("not json"),
    )
    with (
        patch(
            "backend.services.calendar_sync.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await calendar_sync.create_google_calendar_event("token", {"summary": "Test"})

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Google Calendar returned an invalid response."


@pytest.mark.asyncio
async def test_refresh_oauth_token_invalid_json_raises_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _FakeResponse(
        status_code=200,
        is_success=True,
        json_error=ValueError("not json"),
    )
    monkeypatch.setenv("OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "test-client-secret")

    token: Mapping[str, object] = {"access_token": "token", "refresh_token": "refresh"}

    with (
        patch(
            "backend.routes.auth.httpx.AsyncClient",
            return_value=_FakeAsyncClient(response),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await auth_routes._refresh_oauth_token(token)

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Could not refresh Google Calendar access."
