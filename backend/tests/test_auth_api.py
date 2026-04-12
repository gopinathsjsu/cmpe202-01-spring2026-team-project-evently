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
from backend.app_config import build_frontend_settings
from backend.db import get_db
from backend.models.user import User
from backend.routes import auth as auth_routes


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: list[dict[str, object]] = []

    async def find_one(
        self,
        query: dict[str, object] | None = None,
        _projection: dict[str, int] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
    ) -> dict[str, object] | None:
        if sort:
            field, direction = sort[0]
            if not self._docs:
                return None
            reverse = direction < 0
            return sorted(
                self._docs,
                key=lambda doc: cast(int, doc.get(field, 0)),
                reverse=reverse,
            )[0]

        if not query:
            return self._docs[0] if self._docs else None

        for doc in self._docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None

    async def insert_one(self, doc: dict[str, object]) -> None:
        self._docs.append(doc)

    async def count_documents(
        self, query: dict[str, object] | None = None, *, limit: int | None = None
    ) -> int:
        if not query:
            count = len(self._docs)
        else:
            count = sum(
                1
                for doc in self._docs
                if all(doc.get(key) == value for key, value in query.items())
            )
        if limit is not None:
            return min(count, limit)
        return count

    async def delete_one(self, query: dict[str, object]) -> None:
        for idx, doc in enumerate(self._docs):
            if all(doc.get(key) == value for key, value in query.items()):
                self._docs.pop(idx)
                return

    async def update_one(
        self,
        query: dict[str, object],
        update: dict[str, dict[str, object]],
        *,
        upsert: bool = False,
    ) -> None:
        doc = await self.find_one(query)
        if doc is None:
            if not upsert:
                return
            doc = dict(query)
            self._docs.append(doc)

        for key, value in update.get("$set", {}).items():
            doc[key] = value

    async def find_one_and_update(
        self,
        query: dict[str, object],
        update: dict[str, dict[str, object]],
        *,
        upsert: bool = False,
        return_document: object | None = None,
    ) -> dict[str, object] | None:
        doc = await self.find_one(query)
        if doc is None:
            if not upsert:
                return None
            doc = dict(query)
            self._docs.append(doc)

        for key, value in update.get("$inc", {}).items():
            doc[key] = cast(int, doc.get(key, 0)) + cast(int, value)
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        return doc


class _FakeDb:
    def __init__(self) -> None:
        self._collections = {"users": _FakeCollection()}

    def __getitem__(self, name: str) -> _FakeCollection:
        return self._collections.setdefault(name, _FakeCollection())


@pytest.fixture(autouse=True)
def clear_oauth_cache() -> Iterator[None]:
    auth_routes.get_oauth.cache_clear()
    yield
    auth_routes.get_oauth.cache_clear()


def _session_state(
    *,
    oauth_user: object | None = None,
    oauth_token_session_id: object | None = None,
    evently_user_id: object | None = None,
    pending_signup: object | None = None,
    post_auth_redirect: object | None = None,
) -> dict[str, object | None]:
    return {
        auth_routes._OAUTH_USER_SESSION_KEY: oauth_user,
        auth_routes._OAUTH_TOKEN_SESSION_ID_KEY: oauth_token_session_id,
        auth_routes._EVENTLY_USER_SESSION_KEY: evently_user_id,
        auth_routes._PENDING_SIGNUP_SESSION_KEY: pending_signup,
        auth_routes._POST_AUTH_REDIRECT_KEY: post_auth_redirect,
    }


def _make_client(base_url: str = "http://test") -> tuple[FastAPI, AsyncClient]:
    app = create_app()
    fake_db = _FakeDb()
    app.state.db = fake_db
    app.dependency_overrides[get_db] = lambda: fake_db

    @app.get("/_test/session")
    async def read_session(request: Request) -> dict[str, object | None]:
        return {
            auth_routes._OAUTH_USER_SESSION_KEY: request.session.get(
                auth_routes._OAUTH_USER_SESSION_KEY
            ),
            auth_routes._OAUTH_TOKEN_SESSION_ID_KEY: request.session.get(
                auth_routes._OAUTH_TOKEN_SESSION_ID_KEY
            ),
            auth_routes._EVENTLY_USER_SESSION_KEY: request.session.get(
                auth_routes._EVENTLY_USER_SESSION_KEY
            ),
            auth_routes._PENDING_SIGNUP_SESSION_KEY: request.session.get(
                auth_routes._PENDING_SIGNUP_SESSION_KEY
            ),
            auth_routes._POST_AUTH_REDIRECT_KEY: request.session.get(
                auth_routes._POST_AUTH_REDIRECT_KEY
            ),
        }

    @app.post("/_test/session")
    async def write_session(
        request: Request, payload: dict[str, object | None]
    ) -> dict[str, object | None]:
        for key, value in payload.items():
            if value is None:
                request.session.pop(key, None)
                continue
            request.session[key] = value
        return await read_session(request)

    @app.get("/_test/oauth-token")
    async def read_oauth_token(request: Request) -> dict[str, object | None]:
        session_id = request.session.get(auth_routes._OAUTH_TOKEN_SESSION_ID_KEY)
        if not isinstance(session_id, str):
            return {"token": None}
        stored = await fake_db[auth_routes._OAUTH_TOKEN_COLLECTION].find_one(
            {"_id": session_id}
        )
        if stored is None:
            return {"token": None}
        return {"token": stored.get("token")}

    @app.post("/_test/oauth-token")
    async def write_oauth_token(
        request: Request, payload: dict[str, object | None]
    ) -> dict[str, object | None]:
        session_id = payload.get("session_id")
        token = payload.get("token")
        if not isinstance(session_id, str):
            return {"token": None}
        request.session[auth_routes._OAUTH_TOKEN_SESSION_ID_KEY] = session_id
        if token is None:
            await fake_db[auth_routes._OAUTH_TOKEN_COLLECTION].delete_one(
                {"_id": session_id}
            )
            return {"token": None}
        await fake_db[auth_routes._OAUTH_TOKEN_COLLECTION].update_one(
            {"_id": session_id},
            {"$set": {"token": token}},
            upsert=True,
        )
        return {"token": token}

    @app.get("/_test/google-calendar-access-token")
    async def read_google_calendar_access_token(request: Request) -> dict[str, str]:
        return {
            "access_token": await auth_routes.get_google_calendar_access_token(request)
        }

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url=base_url)
    return app, client


@pytest.mark.asyncio
async def test_login_returns_503_when_oauth_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("OAUTH_CLIENT_SECRET", raising=False)

    _, client = _make_client(base_url="https://test")
    async with client:
        resp = await client.get("/auth/login")

    assert resp.status_code == 503
    assert resp.json() == {"detail": auth_routes.OAUTH_NOT_CONFIGURED}


@pytest.mark.asyncio
async def test_login_redirects_to_google_and_uses_callback_url() -> None:
    _, client = _make_client(base_url="https://test")
    redirect = RedirectResponse(url="https://accounts.google.com/o/oauth2/auth")
    authorize_redirect = AsyncMock(return_value=redirect)
    google_client = SimpleNamespace(authorize_redirect=authorize_redirect)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            resp = await client.get("/auth/login")

    await_args = authorize_redirect.await_args
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://accounts.google.com/o/oauth2/auth"
    assert authorize_redirect.await_count == 1
    assert await_args is not None
    assert await_args.args[1] == "https://test/auth/callback"
    assert await_args.kwargs == {
        "access_type": "offline",
        "include_granted_scopes": "true",
    }
    set_cookie = resp.headers.get("set-cookie", "")
    assert "evently_session=" in set_cookie
    assert "samesite=lax" in set_cookie


@pytest.mark.asyncio
async def test_login_returns_500_when_oauth_does_not_return_redirect() -> None:
    _, client = _make_client(base_url="https://test")
    authorize_redirect = AsyncMock(return_value="not-a-redirect")
    google_client = SimpleNamespace(authorize_redirect=authorize_redirect)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            resp = await client.get("/auth/login")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Failed to create redirect response"}


@pytest.mark.asyncio
async def test_callback_stores_pending_signup_session_for_new_google_user() -> None:
    _, client = _make_client(base_url="https://test")
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
        "email_verified": True,
        "name": "Test User",
    }
    oauth_token = {
        "access_token": "google-access-token",
        "refresh_token": "google-refresh-token",
        "token_type": "Bearer",
        "scope": auth_routes.GOOGLE_OAUTH_SCOPE,
        "expires_in": 3600,
    }
    authorize_access_token = AsyncMock(
        return_value={"userinfo": userinfo, **oauth_token}
    )
    google_client = SimpleNamespace(authorize_access_token=authorize_access_token)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            resp = await client.get("/auth/callback")
            session_resp = await client.get("/_test/session")
            token_store_resp = await client.get("/_test/oauth-token")

    assert resp.status_code == 307
    assert resp.headers["location"] == "/complete-signup"
    session_data = session_resp.json()
    assert session_data == _session_state(
        oauth_user=userinfo,
        oauth_token_session_id=session_data[auth_routes._OAUTH_TOKEN_SESSION_ID_KEY],
        pending_signup=True,
    )
    stored_token = token_store_resp.json()["token"]
    assert isinstance(session_data[auth_routes._OAUTH_TOKEN_SESSION_ID_KEY], str)
    assert stored_token == {
        "access_token": "google-access-token",
        "refresh_token": "google-refresh-token",
        "token_type": "Bearer",
        "scope": auth_routes.GOOGLE_OAUTH_SCOPE,
        "expires_at": stored_token["expires_at"],
    }
    assert isinstance(stored_token["expires_at"], int)


@pytest.mark.asyncio
async def test_google_calendar_access_token_refreshes_when_session_token_is_expired() -> (
    None
):
    _, client = _make_client(base_url="https://test")
    expired_token = {
        "access_token": "expired-access-token",
        "refresh_token": "refresh-token",
        "expires_at": 1,
        "scope": auth_routes.GOOGLE_OAUTH_SCOPE,
    }
    refreshed_token = {
        "access_token": "fresh-access-token",
        "refresh_token": "refresh-token",
        "expires_at": 9999999999,
        "scope": auth_routes.GOOGLE_OAUTH_SCOPE,
    }

    with patch.object(
        auth_routes,
        "_refresh_oauth_token",
        AsyncMock(return_value=refreshed_token),
    ) as refresh_oauth_token:
        async with client:
            await client.post(
                "/_test/oauth-token",
                json={"session_id": "token-session-1", "token": expired_token},
            )
            await client.post(
                "/_test/session",
                json=_session_state(oauth_token_session_id="token-session-1"),
            )
            token_resp = await client.get("/_test/google-calendar-access-token")
            session_resp = await client.get("/_test/session")
            stored_token_resp = await client.get("/_test/oauth-token")

    assert refresh_oauth_token.await_count == 1
    assert token_resp.status_code == 200
    assert token_resp.json() == {"access_token": "fresh-access-token"}
    assert session_resp.json() == _session_state(
        oauth_token_session_id="token-session-1"
    )
    assert stored_token_resp.json() == {"token": refreshed_token}


@pytest.mark.asyncio
async def test_callback_reuses_existing_user_with_case_insensitive_email() -> None:
    app, client = _make_client(base_url="https://test")
    await app.state.db["users"].insert_one(
        {
            "id": 7,
            "username": "existing",
            "first_name": "Existing",
            "last_name": "User",
            "email": "user@example.com",
            "roles": ["user"],
            "profile": {},
        }
    )
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "User@Example.com",
        "email_verified": True,
        "name": "Existing User",
    }
    authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})
    google_client = SimpleNamespace(authorize_access_token=authorize_access_token)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            resp = await client.get("/auth/callback")

    assert resp.status_code == 307
    users = app.state.db["users"]._docs
    assert len(users) == 1
    assert users[0]["id"] == 7
    assert users[0]["google_sub"] == "google-oauth2|123"
    assert users[0]["first_name"] == "Existing"
    assert users[0]["last_name"] == "User"


@pytest.mark.asyncio
async def test_callback_refreshes_existing_user_name_and_picture_from_google() -> None:
    app, client = _make_client(base_url="https://test")
    await app.state.db["users"].insert_one(
        {
            "id": 7,
            "username": "existing",
            "first_name": "Old",
            "last_name": "Name",
            "email": "user@example.com",
            "roles": ["user"],
            "profile_photo_url": "https://example.com/old.png",
            "profile": {},
        }
    )
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
        "email_verified": True,
        "given_name": "Fresh",
        "family_name": "User",
        "picture": "https://example.com/new.png",
    }
    authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})
    google_client = SimpleNamespace(authorize_access_token=authorize_access_token)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            callback_resp = await client.get("/auth/callback")
            session_resp = await client.get("/auth/session")

    updated_user = await app.state.db["users"].find_one({"id": 7})

    assert callback_resp.status_code == 307
    assert updated_user is not None
    assert updated_user["google_sub"] == "google-oauth2|123"
    assert updated_user["first_name"] == "Fresh"
    assert updated_user["last_name"] == "User"
    assert updated_user["profile_photo_url"] == "https://example.com/new.png"
    assert session_resp.json()["user"]["name"] == "Fresh User"


@pytest.mark.asyncio
async def test_callback_rejects_google_identity_without_verified_email() -> None:
    _, client = _make_client(base_url="https://test")
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
        "email_verified": False,
        "name": "Test User",
    }
    authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})
    google_client = SimpleNamespace(authorize_access_token=authorize_access_token)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            resp = await client.get("/auth/callback")
            session_resp = await client.get("/_test/session")

    assert resp.status_code == 400
    assert resp.json() == {"detail": auth_routes.OAUTH_INVALID_IDENTITY}
    assert session_resp.json() == _session_state()


@pytest.mark.asyncio
async def test_callback_returns_400_when_oauth_fails() -> None:
    _, client = _make_client(base_url="https://test")
    authorize_access_token = AsyncMock(
        side_effect=OAuthError(error="access_denied", description="Denied")
    )
    google_client = SimpleNamespace(authorize_access_token=authorize_access_token)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
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
    oauth_token = {"access_token": "google-access-token"}
    async with client:
        await client.post(
            "/_test/oauth-token",
            json={"session_id": "token-session-logout", "token": oauth_token},
        )
        before_logout = await client.post(
            "/_test/session",
            json=_session_state(
                oauth_user=userinfo,
                oauth_token_session_id="token-session-logout",
                evently_user_id=7,
                post_auth_redirect="http://localhost:3000/create",
            ),
        )
        resp = await client.get("/auth/logout")
        after_logout = await client.get("/_test/session")
        token_store_resp = await client.get("/_test/oauth-token")

    assert before_logout.json() == _session_state(
        oauth_user=userinfo,
        oauth_token_session_id="token-session-logout",
        evently_user_id=7,
        post_auth_redirect="http://localhost:3000/create",
    )
    assert resp.status_code == 307
    assert resp.headers["location"] == "/"
    assert after_logout.json() == _session_state()
    assert token_store_resp.json() == {"token": None}


@pytest.mark.asyncio
async def test_callback_redirects_back_to_frontend_and_exposes_session_user() -> None:
    _, client = _make_client()
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
        "email_verified": True,
        "name": "Test User",
        "given_name": "Test",
        "family_name": "User",
        "picture": "https://example.com/avatar.png",
    }
    local_user = User(
        id=7,
        username="testuser",
        first_name="Test",
        last_name="User",
        email="user@example.com",
    )
    authorize_redirect = AsyncMock(
        return_value=RedirectResponse(url="https://accounts.google.com/o/oauth2/auth")
    )
    authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})
    google_client = SimpleNamespace(
        authorize_access_token=authorize_access_token,
        authorize_redirect=authorize_redirect,
    )

    with (
        patch.object(auth_routes, "get_google_client", return_value=google_client),
        patch.object(
            auth_routes,
            "_resolve_existing_local_user",
            AsyncMock(return_value=local_user),
        ),
    ):
        async with client:
            await client.get("http://test/auth/login?next=http://localhost:3000/create")
            resp = await client.get("/auth/callback")
            stored_session = await client.get("/_test/session")
            session_resp = await client.get("/auth/session")

    assert resp.status_code == 307
    assert resp.headers["location"] == "http://localhost:3000/create"
    assert stored_session.json() == _session_state(
        oauth_user=userinfo,
        evently_user_id=7,
    )
    assert session_resp.status_code == 200
    assert session_resp.json() == {
        "user": {
            "id": 7,
            "email": "user@example.com",
            "first_name": "Test",
            "last_name": "User",
            "name": "Test User",
            "roles": ["user"],
            "picture": "https://example.com/avatar.png",
        }
    }


def test_build_frontend_settings_normalizes_frontend_url() -> None:
    settings = build_frontend_settings("https://frontend.example.com/create?x=1")

    assert settings.primary_origin == "https://frontend.example.com"
    assert settings.allowed_origins == (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://frontend.example.com",
    )


@pytest.mark.asyncio
async def test_callback_redirects_new_user_to_configured_complete_signup_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example.com/app")

    _, client = _make_client(base_url="https://test")
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
        "email_verified": True,
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

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            await client.get("/auth/login?next=https://frontend.example.com/create")
            resp = await client.get("/auth/callback")

    assert resp.status_code == 307
    assert resp.headers["location"] == "https://frontend.example.com/complete-signup"


@pytest.mark.asyncio
async def test_login_uses_secure_session_cookie_for_https_frontend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example.com/app")

    _, client = _make_client(base_url="https://test")
    redirect = RedirectResponse(url="https://accounts.google.com/o/oauth2/auth")
    authorize_redirect = AsyncMock(return_value=redirect)
    google_client = SimpleNamespace(authorize_redirect=authorize_redirect)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            resp = await client.get("/auth/login")

    set_cookie = resp.headers.get("set-cookie", "")
    assert "evently_session=" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "secure" in set_cookie


@pytest.mark.asyncio
async def test_login_uses_allowed_referer_as_post_auth_redirect() -> None:
    _, client = _make_client(base_url="https://test")
    authorize_redirect = AsyncMock(
        return_value=RedirectResponse(url="https://accounts.google.com/o/oauth2/auth")
    )
    google_client = SimpleNamespace(authorize_redirect=authorize_redirect)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            await client.get(
                "/auth/login",
                headers={"referer": "http://localhost:3000/events/42"},
            )
            session_resp = await client.get("/_test/session")

    assert session_resp.json() == _session_state(
        post_auth_redirect="http://localhost:3000/events/42"
    )


@pytest.mark.asyncio
async def test_login_rejects_disallowed_next_and_falls_back_to_primary_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example.com/app")

    _, client = _make_client(base_url="https://test")
    authorize_redirect = AsyncMock(
        return_value=RedirectResponse(url="https://accounts.google.com/o/oauth2/auth")
    )
    google_client = SimpleNamespace(authorize_redirect=authorize_redirect)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            await client.get("/auth/login?next=https://evil.example.com/phish")
            session_resp = await client.get("/_test/session")

    assert session_resp.json() == _session_state(
        post_auth_redirect="https://frontend.example.com"
    )


@pytest.mark.asyncio
async def test_auth_session_uses_existing_local_user_without_recreating() -> None:
    app, client = _make_client()
    stored_user = User(
        id=7,
        username="testuser",
        first_name="Test",
        last_name="User",
        email="user@example.com",
        profile_photo_url="https://example.com/profile.png",
    )
    await app.state.db["users"].insert_one(stored_user.model_dump(mode="json"))
    resolve_existing_local_user = AsyncMock()

    with patch.object(
        auth_routes,
        "_resolve_existing_local_user",
        resolve_existing_local_user,
    ):
        async with client:
            await client.post(
                "/_test/session",
                json={
                    auth_routes._OAUTH_USER_SESSION_KEY: {
                        "sub": "google-oauth2|123",
                        "email": "user@example.com",
                        "email_verified": True,
                        "picture": "https://example.com/oauth.png",
                    },
                    auth_routes._EVENTLY_USER_SESSION_KEY: 7,
                },
            )
            resp = await client.get("/auth/session")

    assert resolve_existing_local_user.await_count == 0
    assert resp.status_code == 200
    assert resp.json() == {
        "user": {
            "id": 7,
            "email": "user@example.com",
            "first_name": "Test",
            "last_name": "User",
            "name": "Test User",
            "roles": ["user"],
            "picture": "https://example.com/oauth.png",
        }
    }


@pytest.mark.asyncio
async def test_auth_session_keeps_pending_signup_user_unauthenticated() -> None:
    _, client = _make_client()
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
        "email_verified": True,
        "given_name": "Test",
        "family_name": "User",
        "picture": "https://example.com/oauth.png",
    }
    resolve_existing_local_user = AsyncMock(return_value=None)

    with patch.object(
        auth_routes,
        "_resolve_existing_local_user",
        resolve_existing_local_user,
    ):
        async with client:
            await client.post(
                "/_test/session",
                json={
                    auth_routes._OAUTH_USER_SESSION_KEY: userinfo,
                    auth_routes._PENDING_SIGNUP_SESSION_KEY: True,
                },
            )
            resp = await client.get("/auth/session")
            session_resp = await client.get("/_test/session")

    assert resolve_existing_local_user.await_count == 1
    assert resp.status_code == 200
    assert resp.json() == {"user": None}
    assert session_resp.json() == _session_state(
        oauth_user=userinfo,
        pending_signup=True,
    )


@pytest.mark.asyncio
async def test_pending_signup_endpoint_returns_google_profile_defaults() -> None:
    _, client = _make_client()

    async with client:
        await client.post(
            "/_test/session",
            json={
                auth_routes._OAUTH_USER_SESSION_KEY: {
                    "sub": "google-oauth2|123",
                    "email": "future.user@example.com",
                    "email_verified": True,
                    "given_name": "Future",
                    "family_name": "User",
                    "picture": "https://example.com/pending.png",
                },
                auth_routes._PENDING_SIGNUP_SESSION_KEY: True,
            },
        )
        resp = await client.get("/auth/pending-signup")

    assert resp.status_code == 200
    assert resp.json() == {
        "pending": {
            "email": "future.user@example.com",
            "first_name": "Future",
            "last_name": "User",
            "suggested_username": "futureuser",
            "picture": "https://example.com/pending.png",
        }
    }


@pytest.mark.asyncio
async def test_complete_signup_creates_local_user_and_redirect_target() -> None:
    app, client = _make_client()

    async with client:
        await client.post(
            "/_test/session",
            json=_session_state(
                oauth_user={
                    "sub": "google-oauth2|999",
                    "email": "future.user@example.com",
                    "email_verified": True,
                    "given_name": "Future",
                    "family_name": "User",
                },
                pending_signup=True,
                post_auth_redirect="http://localhost:3000/create",
            ),
        )
        resp = await client.post(
            "/auth/complete-signup",
            json={
                "username": "futureuser",
                "first_name": "Future",
                "last_name": "User",
                "bio": "Ready to join Evently.",
                "interests": ["Technology", "Community"],
            },
        )
        session_resp = await client.get("/_test/session")

    stored = await app.state.db["users"].find_one({"email": "future.user@example.com"})

    assert resp.status_code == 200
    assert stored is not None
    assert stored["username"] == "futureuser"
    assert stored["google_sub"] == "google-oauth2|999"
    assert stored["profile"]["bio"] == "Ready to join Evently."
    assert stored["profile"]["interests"] == ["Technology", "Community"]
    assert resp.json()["redirect_to"] == "http://localhost:3000/create"
    assert session_resp.json() == _session_state(
        oauth_user={
            "sub": "google-oauth2|999",
            "email": "future.user@example.com",
            "email_verified": True,
            "given_name": "Future",
            "family_name": "User",
        },
        evently_user_id=1,
    )


@pytest.mark.asyncio
async def test_auth_session_reconciles_stale_local_user_with_current_oauth_user() -> (
    None
):
    app, client = _make_client()
    stale_user = User(
        id=7,
        username="sarah",
        first_name="Sarah",
        last_name="Johnson",
        email="sarah@example.com",
    )
    current_user = User(
        id=8,
        username="lucas",
        first_name="Lucas",
        last_name="Nguyen",
        email="lucas.h.nguyen@sjsu.edu",
    )
    await app.state.db["users"].insert_one(stale_user.model_dump(mode="json"))
    await app.state.db["users"].insert_one(current_user.model_dump(mode="json"))

    async with client:
        await client.post(
            "/_test/session",
            json={
                auth_routes._OAUTH_USER_SESSION_KEY: {
                    "sub": "google-oauth2|321",
                    "email": "lucas.h.nguyen@sjsu.edu",
                    "email_verified": True,
                    "given_name": "Lucas",
                    "family_name": "Nguyen",
                },
                auth_routes._EVENTLY_USER_SESSION_KEY: 7,
            },
        )
        resp = await client.get("/auth/session")
        session_resp = await client.get("/_test/session")

    assert resp.status_code == 200
    assert resp.json()["user"]["id"] == 8
    assert resp.json()["user"]["name"] == "Lucas Nguyen"
    assert session_resp.json() == _session_state(
        oauth_user={
            "sub": "google-oauth2|321",
            "email": "lucas.h.nguyen@sjsu.edu",
            "email_verified": True,
            "given_name": "Lucas",
            "family_name": "Nguyen",
        },
        evently_user_id=8,
    )


@pytest.mark.asyncio
async def test_create_local_user_from_oauth_stores_roles_as_list() -> None:
    db = _FakeDb()

    user = await auth_routes._create_local_user_from_oauth(
        cast(Any, db),
        {
            "sub": "google-oauth2|123",
            "email": "new-user@example.com",
            "email_verified": True,
            "given_name": "New",
            "family_name": "User",
        },
        auth_routes.CompleteSignupRequest(username="newuser"),
    )

    stored = await db["users"].find_one({"email": "new-user@example.com"})

    assert user is not None
    assert stored is not None
    assert stored["google_sub"] == "google-oauth2|123"
    assert stored["roles"] == ["user"]


@pytest.mark.asyncio
async def test_create_local_user_from_oauth_assigns_admin_role_from_admin_emails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com, other@example.com")
    db = _FakeDb()

    user = await auth_routes._create_local_user_from_oauth(
        cast(Any, db),
        {
            "sub": "google-oauth2|123",
            "email": "Admin@Example.com",
            "email_verified": True,
            "given_name": "Admin",
            "family_name": "User",
        },
        auth_routes.CompleteSignupRequest(username="adminuser"),
    )

    stored = await db["users"].find_one()

    assert user is not None
    assert stored is not None
    assert sorted(role.value for role in user.roles) == ["admin", "user"]
    assert stored["roles"] == ["admin", "user"]


@pytest.mark.asyncio
async def test_create_local_user_from_oauth_assigns_admin_role_from_quoted_admin_emails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", '"lucas.h.nguyen@sjsu.edu,admin2@example.com"')
    db = _FakeDb()

    user = await auth_routes._create_local_user_from_oauth(
        cast(Any, db),
        {
            "sub": "google-oauth2|123",
            "email": "lucas.h.nguyen@sjsu.edu",
            "email_verified": True,
            "given_name": "Lucas",
            "family_name": "Nguyen",
        },
        auth_routes.CompleteSignupRequest(username="lucasnguyen"),
    )

    stored = await db["users"].find_one()

    assert user is not None
    assert stored is not None
    assert sorted(role.value for role in user.roles) == ["admin", "user"]
    assert stored["roles"] == ["admin", "user"]


@pytest.mark.asyncio
async def test_resolve_existing_local_user_backfills_google_subject_for_existing_email() -> (
    None
):
    db = _FakeDb()
    await db["users"].insert_one(
        {
            "id": 7,
            "username": "existing",
            "first_name": "Existing",
            "last_name": "User",
            "email": "user@example.com",
            "roles": ["user"],
            "profile": {},
        }
    )

    user = await auth_routes._resolve_existing_local_user(
        cast(Any, db),
        {
            "sub": "google-oauth2|123",
            "email": "user@example.com",
            "email_verified": True,
            "given_name": "Existing",
            "family_name": "User",
        },
    )

    stored = await db["users"].find_one({"id": 7})

    assert user is not None
    assert stored is not None
    assert user.google_sub == "google-oauth2|123"
    assert stored["google_sub"] == "google-oauth2|123"


@pytest.mark.asyncio
async def test_resolve_existing_local_user_prefers_google_subject_over_email() -> None:
    db = _FakeDb()
    await db["users"].insert_one(
        {
            "id": 7,
            "username": "existing",
            "first_name": "Existing",
            "last_name": "User",
            "email": "old@example.com",
            "google_sub": "google-oauth2|123",
            "roles": ["user"],
            "profile": {},
        }
    )

    user = await auth_routes._resolve_existing_local_user(
        cast(Any, db),
        {
            "sub": "google-oauth2|123",
            "email": "new@example.com",
            "email_verified": True,
            "given_name": "Existing",
            "family_name": "User",
        },
    )

    users = db["users"]._docs

    assert user is not None
    assert len(users) == 1
    assert user.email == "new@example.com"
    assert users[0]["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_auth_session_updates_existing_user_roles_from_admin_email_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    app, client = _make_client()
    stored_user = User(
        id=7,
        username="adminuser",
        first_name="Admin",
        last_name="User",
        email="admin@example.com",
    )
    await app.state.db["users"].insert_one(stored_user.model_dump(mode="json"))

    async with client:
        await client.post(
            "/_test/session",
            json={auth_routes._EVENTLY_USER_SESSION_KEY: 7},
        )
        resp = await client.get("/auth/session")

    updated = await app.state.db["users"].find_one({"id": 7})

    assert resp.status_code == 200
    assert resp.json() == {
        "user": {
            "id": 7,
            "email": "admin@example.com",
            "first_name": "Admin",
            "last_name": "User",
            "name": "Admin User",
            "roles": ["admin", "user"],
            "picture": None,
        }
    }
    assert updated is not None
    assert updated["roles"] == ["admin", "user"]
