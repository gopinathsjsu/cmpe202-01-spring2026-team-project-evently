from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo.asynchronous.database import AsyncDatabase

from backend.api import create_app
from backend.db import get_db
from backend.routes.auth import AuthSessionUser, require_authenticated_user
from backend.services.notifications.arq import get_arq
from backend.services.notifications.email import get_email_notif_service


def _make_client(
    db: AsyncDatabase[dict[str, Any]],
    auth_user: AuthSessionUser | None = None,
) -> tuple[Any, AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_arq] = lambda: AsyncMock()
    app.dependency_overrides[get_email_notif_service] = lambda: AsyncMock()
    if auth_user is not None:
        app.dependency_overrides[require_authenticated_user] = lambda: auth_user
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return app, client


def _auth_user(user_id: int = 1, roles: list[str] | None = None) -> AuthSessionUser:
    return AuthSessionUser(
        id=user_id,
        email=f"user{user_id}@example.com",
        first_name="Test",
        last_name="User",
        name="Test User",
        roles=roles or ["user"],
    )


async def _clean(db: AsyncDatabase[dict[str, Any]]) -> None:
    for coll in ("events", "attendance", "event_favorites", "counters"):
        await db[coll].delete_many({})


@pytest.mark.asyncio
async def test_list_pending_events_requires_admin(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "status": "pending"})

    _, client = _make_client(db, _auth_user())
    async with client:
        resp = await client.get("/events/pending")

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_pending_events_returns_only_pending(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "title": "Pending", "status": "pending"},
            {**event_data, "id": 2, "title": "Approved", "status": "approved"},
        ]
    )

    _, client = _make_client(db, _auth_user(roles=["user", "admin"]))
    async with client:
        resp = await client.get("/events/pending")

    assert resp.status_code == 200
    body = resp.json()
    assert [item["title"] for item in body] == ["Pending"]


@pytest.mark.asyncio
async def test_approve_event_updates_status(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "status": "pending"})

    _, client = _make_client(db, _auth_user(roles=["user", "admin"]))
    async with client:
        resp = await client.post("/events/1/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    saved = await db["events"].find_one({"id": 1})
    assert saved is not None
    assert saved["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_event_updates_status(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "status": "pending"})

    _, client = _make_client(db, _auth_user(roles=["user", "admin"]))
    async with client:
        resp = await client.post("/events/1/reject")

    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"
    saved = await db["events"].find_one({"id": 1})
    assert saved is not None
    assert saved["status"] == "rejected"
