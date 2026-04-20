from datetime import UTC, datetime, tzinfo
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo.asynchronous.database import AsyncDatabase

from backend.api import create_app
from backend.db import get_db
from backend.routes import events as events_route
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


def _auth_user(user_id: int = 7) -> AuthSessionUser:
    return AuthSessionUser(
        id=user_id,
        email=f"user{user_id}@example.com",
        first_name="Test",
        last_name="User",
        name="Test User",
        roles=["user"],
    )


async def _clean(db: AsyncDatabase[dict[str, Any]]) -> None:
    for coll in ("events", "attendance", "event_favorites", "counters"):
        await db[coll].delete_many({})


@pytest.mark.asyncio
async def test_cancel_attendance_only_updates_latest_record(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "registered_count": 1})
    await db["attendance"].insert_many(
        [
            {
                "event_id": 1,
                "user_id": 7,
                "status": "checked_in",
                "checked_in_at": datetime(2026, 6, 15, 19, 30, 0),
            },
            {
                "event_id": 1,
                "user_id": 7,
                "status": "going",
                "checked_in_at": None,
            },
        ]
    )

    _, client = _make_client(db, _auth_user())
    async with client:
        resp = await client.delete("/events/1/attendance")

    assert resp.status_code == 200

    records = await (
        db["attendance"].find({"event_id": 1, "user_id": 7}).sort("_id", 1).to_list(10)
    )
    assert records[0]["status"] == "checked_in"
    assert records[0]["checked_in_at"] is not None
    assert records[1]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_today_preset_excludes_start_of_tomorrow(
    db: AsyncDatabase[dict[str, Any]],
    event_data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _clean(db)
    now = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UTC)

    await db["events"].insert_many(
        [
            {
                **event_data,
                "id": 1,
                "title": "Today Event",
                "start_time": datetime(2026, 6, 15, 18, 0, 0, tzinfo=UTC),
                "end_time": datetime(2026, 6, 15, 20, 0, 0, tzinfo=UTC),
            },
            {
                **event_data,
                "id": 2,
                "title": "Tomorrow Midnight Event",
                "start_time": datetime(2026, 6, 16, 0, 0, 0, tzinfo=UTC),
                "end_time": datetime(2026, 6, 16, 2, 0, 0, tzinfo=UTC),
            },
        ]
    )

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> "FrozenDateTime":
            frozen = now if tz is not None else now.replace(tzinfo=None)
            return cls.fromtimestamp(frozen.timestamp(), tz=frozen.tzinfo)

    monkeypatch.setattr(events_route, "datetime", FrozenDateTime)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"date_preset": "today"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert [item["title"] for item in body["items"]] == ["Today Event"]
