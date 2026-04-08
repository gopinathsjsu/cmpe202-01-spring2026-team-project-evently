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
                1 for doc in self._docs if all(doc.get(key) == value for key, value in query.items())
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
        self, query: dict[str, object], update: dict[str, dict[str, object]]
    ) -> None:
        doc = await self.find_one(query)
        if doc is None:
            return

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
            auth_routes._EVENTLY_USER_SESSION_KEY: request.session.get(
                auth_routes._EVENTLY_USER_SESSION_KEY
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
async def test_callback_stores_userinfo_in_session() -> None:
    _, client = _make_client(base_url="https://test")
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
        "name": "Test User",
    }
    authorize_access_token = AsyncMock(return_value={"userinfo": userinfo})
    google_client = SimpleNamespace(authorize_access_token=authorize_access_token)

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            resp = await client.get("/auth/callback")
            session_resp = await client.get("/_test/session")

    assert resp.status_code == 307
    assert resp.headers["location"] == "/"
    assert session_resp.json() == {
        auth_routes._OAUTH_USER_SESSION_KEY: userinfo,
        auth_routes._EVENTLY_USER_SESSION_KEY: 1,
        auth_routes._POST_AUTH_REDIRECT_KEY: None,
    }


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
    async with client:
        before_logout = await client.post(
            "/_test/session",
            json={
                auth_routes._OAUTH_USER_SESSION_KEY: userinfo,
                auth_routes._EVENTLY_USER_SESSION_KEY: 7,
                auth_routes._POST_AUTH_REDIRECT_KEY: "http://localhost:3000/create",
            },
        )
        resp = await client.get("/auth/logout")
        after_logout = await client.get("/_test/session")

    assert before_logout.json() == {
        auth_routes._OAUTH_USER_SESSION_KEY: userinfo,
        auth_routes._EVENTLY_USER_SESSION_KEY: 7,
        auth_routes._POST_AUTH_REDIRECT_KEY: "http://localhost:3000/create",
    }
    assert resp.status_code == 307
    assert resp.headers["location"] == "/"
    assert after_logout.json() == {
        auth_routes._OAUTH_USER_SESSION_KEY: None,
        auth_routes._EVENTLY_USER_SESSION_KEY: None,
        auth_routes._POST_AUTH_REDIRECT_KEY: None,
    }


@pytest.mark.asyncio
async def test_callback_redirects_back_to_frontend_and_exposes_session_user() -> None:
    _, client = _make_client()
    userinfo = {
        "sub": "google-oauth2|123",
        "email": "user@example.com",
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
            "_resolve_or_create_local_user",
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
    assert stored_session.json() == {
        auth_routes._OAUTH_USER_SESSION_KEY: userinfo,
        auth_routes._EVENTLY_USER_SESSION_KEY: 7,
        auth_routes._POST_AUTH_REDIRECT_KEY: None,
    }
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
async def test_callback_redirects_to_configured_frontend_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example.com/app")

    _, client = _make_client(base_url="https://test")
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

    with patch.object(auth_routes, "get_google_client", return_value=google_client):
        async with client:
            await client.get("/auth/login?next=https://frontend.example.com/create")
            resp = await client.get("/auth/callback")

    assert resp.status_code == 307
    assert resp.headers["location"] == "https://frontend.example.com/create"


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

    assert session_resp.json() == {
        auth_routes._OAUTH_USER_SESSION_KEY: None,
        auth_routes._EVENTLY_USER_SESSION_KEY: None,
        auth_routes._POST_AUTH_REDIRECT_KEY: "http://localhost:3000/events/42",
    }


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

    assert session_resp.json() == {
        auth_routes._OAUTH_USER_SESSION_KEY: None,
        auth_routes._EVENTLY_USER_SESSION_KEY: None,
        auth_routes._POST_AUTH_REDIRECT_KEY: "https://frontend.example.com",
    }


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
    resolve_or_create_local_user = AsyncMock()

    with patch.object(
        auth_routes,
        "_resolve_or_create_local_user",
        resolve_or_create_local_user,
    ):
        async with client:
            await client.post(
                "/_test/session",
                json={
                    auth_routes._OAUTH_USER_SESSION_KEY: {
                        "picture": "https://example.com/oauth.png"
                    },
                    auth_routes._EVENTLY_USER_SESSION_KEY: 7,
                },
            )
            resp = await client.get("/auth/session")

    assert resolve_or_create_local_user.await_count == 0
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
async def test_auth_session_creates_local_user_from_oauth_session() -> None:
    _, client = _make_client()
    userinfo = {
        "email": "user@example.com",
        "given_name": "Test",
        "family_name": "User",
        "picture": "https://example.com/oauth.png",
    }
    local_user = User(
        id=9,
        username="testuser",
        first_name="Test",
        last_name="User",
        email="user@example.com",
    )
    resolve_or_create_local_user = AsyncMock(return_value=local_user)

    with patch.object(
        auth_routes,
        "_resolve_or_create_local_user",
        resolve_or_create_local_user,
    ):
        async with client:
            await client.post(
                "/_test/session",
                json={auth_routes._OAUTH_USER_SESSION_KEY: userinfo},
            )
            resp = await client.get("/auth/session")
            session_resp = await client.get("/_test/session")

    assert resolve_or_create_local_user.await_count == 1
    assert resp.status_code == 200
    assert resp.json() == {
        "user": {
            "id": 9,
            "email": "user@example.com",
            "first_name": "Test",
            "last_name": "User",
            "name": "Test User",
            "roles": ["user"],
            "picture": "https://example.com/oauth.png",
        }
    }
    assert session_resp.json() == {
        auth_routes._OAUTH_USER_SESSION_KEY: userinfo,
        auth_routes._EVENTLY_USER_SESSION_KEY: 9,
        auth_routes._POST_AUTH_REDIRECT_KEY: None,
    }


@pytest.mark.asyncio
async def test_resolve_or_create_local_user_stores_roles_as_list() -> None:
    db = _FakeDb()

    user = await auth_routes._resolve_or_create_local_user(
        cast(Any, db),
        {
            "email": "new-user@example.com",
            "given_name": "New",
            "family_name": "User",
        },
    )

    stored = await db["users"].find_one({"email": "new-user@example.com"})

    assert user is not None
    assert stored is not None
    assert stored["roles"] == ["user"]


@pytest.mark.asyncio
async def test_resolve_or_create_local_user_assigns_admin_role_from_admin_emails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com, other@example.com")
    db = _FakeDb()

    user = await auth_routes._resolve_or_create_local_user(
        cast(Any, db),
        {
            "email": "Admin@Example.com",
            "given_name": "Admin",
            "family_name": "User",
        },
    )

    stored = await db["users"].find_one()

    assert user is not None
    assert stored is not None
    assert sorted(role.value for role in user.roles) == ["admin", "user"]
    assert stored["roles"] == ["admin", "user"]


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
