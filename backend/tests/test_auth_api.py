from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from authlib.integrations.starlette_client import OAuthError
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.responses import RedirectResponse

from backend.api import create_app
from backend.routes import auth as auth_routes


@pytest.fixture(autouse=True)
def clear_oauth_cache() -> Iterator[None]:
    auth_routes.get_oauth.cache_clear()
    yield
    auth_routes.get_oauth.cache_clear()


def _make_client() -> tuple[FastAPI, AsyncClient]:
    app = create_app()

    @app.get("/_test/session")
    async def read_session(request: Request) -> dict[str, object | None]:
        return {"user": request.session.get("user")}

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return app, client


@pytest.mark.asyncio
async def test_login_returns_503_when_oauth_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("OAUTH_CLIENT_SECRET", raising=False)

    _, client = _make_client()
    async with client:
        resp = await client.get("/auth/login")

    assert resp.status_code == 503
    assert resp.json() == {"detail": auth_routes.OAUTH_NOT_CONFIGURED}


@pytest.mark.asyncio
async def test_login_redirects_to_google_and_uses_callback_url() -> None:
    _, client = _make_client()
    redirect = RedirectResponse(url="https://accounts.google.com/o/oauth2/auth")
    authorize_redirect = AsyncMock(return_value=redirect)
    google_client = SimpleNamespace(authorize_redirect=authorize_redirect)

    with patch.object(
        auth_routes, "get_google_client", return_value=google_client
    ):
        async with client:
            resp = await client.get("/auth/login")

    await_args = authorize_redirect.await_args
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://accounts.google.com/o/oauth2/auth"
    assert authorize_redirect.await_count == 1
    assert await_args is not None
    assert await_args.args[1] == "http://test/auth/callback"


@pytest.mark.asyncio
async def test_login_returns_500_when_oauth_does_not_return_redirect() -> None:
    _, client = _make_client()
    authorize_redirect = AsyncMock(return_value="not-a-redirect")
    google_client = SimpleNamespace(authorize_redirect=authorize_redirect)

    with patch.object(
        auth_routes, "get_google_client", return_value=google_client
    ):
        async with client:
            resp = await client.get("/auth/login")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Failed to create redirect response"}


@pytest.mark.asyncio
async def test_callback_stores_userinfo_in_session() -> None:
    _, client = _make_client()
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
        "name": "Test User",
    }
    authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})
    google_client = SimpleNamespace(authorize_access_token=authorize_access_token)

    with patch.object(
        auth_routes, "get_google_client", return_value=google_client
    ):
        async with client:
            resp = await client.get("/auth/callback")
            session_resp = await client.get("/_test/session")

    assert resp.status_code == 307
    assert resp.headers["location"] == "/"
    assert session_resp.json() == {"user": userinfo}


@pytest.mark.asyncio
async def test_callback_returns_400_when_oauth_fails() -> None:
    _, client = _make_client()
    authorize_access_token = AsyncMock(
        side_effect=OAuthError(error="access_denied", description="Denied")
    )
    google_client = SimpleNamespace(authorize_access_token=authorize_access_token)

    with patch.object(
        auth_routes, "get_google_client", return_value=google_client
    ):
        async with client:
            resp = await client.get("/auth/callback")

    assert resp.status_code == 400
    assert resp.json() == {"detail": "OAuth authentication failed"}


@pytest.mark.asyncio
async def test_logout_clears_session_and_redirects_home() -> None:
    _, client = _make_client()
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
        "name": "Test User",
    }
    authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})
    google_client = SimpleNamespace(authorize_access_token=authorize_access_token)

    with patch.object(
        auth_routes, "get_google_client", return_value=google_client
    ):
        async with client:
            await client.get("/auth/callback")
            before_logout = await client.get("/_test/session")
            resp = await client.get("/auth/logout")
            after_logout = await client.get("/_test/session")

    assert before_logout.json() == {"user": userinfo}
    assert resp.status_code == 307
    assert resp.headers["location"] == "/"
    assert after_logout.json() == {"user": None}


def test_build_frontend_settings_normalizes_frontend_url() -> None:
    settings = build_frontend_settings("https://frontend.example.com/create?x=1")

    assert settings.primary_origin == "https://frontend.example.com"
    assert settings.allowed_origins == (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://frontend.example.com",
    )


@pytest.mark.asyncio
async def test_callback_redirects_to_configured_frontend_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example.com/app")

    _, client = _make_client()
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
        "name": "Test User",
    }
    authorize_redirect = AsyncMock(
        return_value=RedirectResponse(url="https://accounts.google.com/o/oauth2/auth")
    )
    authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})
    google_client = SimpleNamespace(
        authorize_access_token=authorize_access_token,
        authorize_redirect=authorize_redirect,
    )

    with patch.object(
        auth_routes, "get_google_client", return_value=google_client
    ):
        async with client:
            await client.get(
                "http://test/auth/login?next=https://frontend.example.com/create"
            )
            resp = await client.get("/auth/callback")

    assert resp.status_code == 307
    assert resp.headers["location"] == "https://frontend.example.com/create"
