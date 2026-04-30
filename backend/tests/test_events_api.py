from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

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
    """Build an app with the DB dependency overridden."""
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


def _user_doc(
    user_id: int,
    *,
    first_name: str = "Test",
    last_name: str = "User",
    email: str | None = None,
) -> dict[str, Any]:
    return {
        "id": user_id,
        "username": f"user{user_id}",
        "first_name": first_name,
        "last_name": last_name,
        "email": email or f"user{user_id}@example.com",
        "phone_number": None,
        "roles": ["user"],
        "profile": {},
        "profile_photo_url": None,
    }


async def _clean(db: AsyncDatabase[dict[str, Any]]) -> None:
    for coll in (
        "users",
        "events",
        "attendance",
        "event_favorites",
        "counters",
        "user_calendar_entries",
        "user_calendar_syncs",
        "event_user_locks",
    ):
        await db[coll].delete_many({})


# -----------------------------------------------------------------------
# Listing basics
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_events_basic(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["title"] == event_data["title"]
    assert item["category"] == event_data["category"]
    assert item["is_online"] is False
    assert item["location"]["city"] == "San Francisco"
    assert item["attending_count"] == 0


@pytest.mark.asyncio
async def test_list_includes_attending_count(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)
    await db["attendance"].insert_many(
        [
            {"event_id": 1, "user_id": i, "status": "going", "checked_in_at": None}
            for i in range(1, 6)
        ]
    )
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 99, "status": "cancelled", "checked_in_at": None}
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/")

    body = resp.json()
    assert body["items"][0]["attending_count"] == 5


@pytest.mark.asyncio
async def test_empty_collection_returns_no_items(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/")

    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.asyncio
async def test_get_event_attendance_status_for_authenticated_user(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.get("/events/1/attendance")

    assert resp.status_code == 200
    assert resp.json() == {"event_id": 1, "user_id": 7, "status": "going"}


@pytest.mark.asyncio
async def test_get_event_attendance_status_returns_none_when_missing(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.get("/events/1/attendance")

    assert resp.status_code == 200
    assert resp.json() == {"event_id": 1, "user_id": 7, "status": None}


@pytest.mark.asyncio
async def test_register_event_attendance_creates_registration(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "registered_count": 0})

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.post("/events/1/attendance")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_id": 1,
        "user_id": 7,
        "status": "going",
        "in_calendar": True,
        "google_synced": False,
    }

    saved = await db["attendance"].find_one({"event_id": 1, "user_id": 7})
    assert saved is not None
    assert saved["status"] == "going"
    event = await db["events"].find_one({"id": 1})
    assert event is not None
    assert event["registered_count"] == 1
    calendar_entry = await db["user_calendar_entries"].find_one(
        {"event_id": 1, "user_id": 7}
    )
    assert calendar_entry is not None


@pytest.mark.asyncio
async def test_register_event_attendance_restores_cancelled_registration(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "registered_count": 0})
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "cancelled", "checked_in_at": None}
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.post("/events/1/attendance")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_id": 1,
        "user_id": 7,
        "status": "going",
        "in_calendar": True,
        "google_synced": False,
    }

    saved = await db["attendance"].find_one({"event_id": 1, "user_id": 7})
    assert saved is not None
    assert saved["status"] == "going"
    event = await db["events"].find_one({"id": 1})
    assert event is not None
    assert event["registered_count"] == 1
    calendar_entry = await db["user_calendar_entries"].find_one(
        {"event_id": 1, "user_id": 7}
    )
    assert calendar_entry is not None


@pytest.mark.asyncio
async def test_register_event_attendance_rejects_organizer(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, _auth_user(1))
    async with client:
        resp = await client.post("/events/1/attendance")

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Organizers cannot register for their own events"


@pytest.mark.asyncio
async def test_register_event_attendance_rejects_sold_out_event(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(
        {**event_data, "total_capacity": 1, "registered_count": 1}
    )
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 5, "status": "going", "checked_in_at": None}
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.post("/events/1/attendance")

    assert resp.status_code == 400
    assert resp.json()["detail"] == "This event is sold out"


@pytest.mark.asyncio
async def test_register_event_attendance_hides_pending_event(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "status": "pending"})

    _, client = _make_client(db, auth_user=_auth_user(7))
    async with client:
        resp = await client.post("/events/1/attendance")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_register_event_attendance_requires_authentication(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/1/attendance")

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication required"


@pytest.mark.asyncio
async def test_cancel_event_attendance_marks_registration_cancelled(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "registered_count": 1})
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )
    await db["user_calendar_entries"].insert_one(
        {"event_id": 1, "user_id": 7, "added_at": datetime(2026, 6, 1, 12, 0, 0)}
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.delete("/events/1/attendance")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_id": 1,
        "user_id": 7,
        "status": "cancelled",
        "in_calendar": False,
        "google_synced": False,
    }

    saved = await db["attendance"].find_one({"event_id": 1, "user_id": 7})
    assert saved is not None
    assert saved["status"] == "cancelled"
    assert saved["checked_in_at"] is None
    event = await db["events"].find_one({"id": 1})
    assert event is not None
    assert event["registered_count"] == 0
    calendar_entry = await db["user_calendar_entries"].find_one(
        {"event_id": 1, "user_id": 7}
    )
    assert calendar_entry is None


@pytest.mark.asyncio
async def test_register_event_attendance_syncs_google_calendar_when_enabled(
    db: AsyncDatabase[dict[str, Any]],
    event_data: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _clean(db)
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example.com/app")
    await db["events"].insert_one({**event_data, "registered_count": 0})
    await db["user_calendar_syncs"].insert_one(
        {"user_id": 7, "google_sync_enabled": True}
    )

    _, client = _make_client(db, _auth_user(7))
    with (
        patch.object(
            events_route,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            events_route,
            "create_google_calendar_event",
            AsyncMock(return_value={"id": "google-event-1"}),
        ),
    ):
        async with client:
            resp = await client.post("/events/1/attendance")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_id": 1,
        "user_id": 7,
        "status": "going",
        "in_calendar": True,
        "google_synced": True,
    }

    calendar_entry = await db["user_calendar_entries"].find_one(
        {"event_id": 1, "user_id": 7}
    )
    assert calendar_entry is not None
    assert calendar_entry["google_calendar_event_id"] == "google-event-1"


@pytest.mark.asyncio
async def test_cancel_event_attendance_removes_google_calendar_event_when_synced(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "registered_count": 1})
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )
    await db["user_calendar_entries"].insert_one(
        {
            "event_id": 1,
            "user_id": 7,
            "added_at": datetime(2026, 6, 1, 12, 0, 0),
            "google_calendar_event_id": "google-event-1",
        }
    )

    _, client = _make_client(db, _auth_user(7))
    delete_google_calendar_event = AsyncMock(return_value=None)
    with (
        patch.object(
            events_route,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            events_route,
            "delete_google_calendar_event",
            delete_google_calendar_event,
        ),
    ):
        async with client:
            resp = await client.delete("/events/1/attendance")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_id": 1,
        "user_id": 7,
        "status": "cancelled",
        "in_calendar": False,
        "google_synced": True,
    }
    delete_google_calendar_event.assert_awaited_once_with(
        "google-access-token",
        "google-event-1",
    )


@pytest.mark.asyncio
async def test_cancel_event_attendance_returns_404_when_missing(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.delete("/events/1/attendance")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Registration not found"


@pytest.mark.asyncio
async def test_cancel_event_attendance_returns_409_when_event_user_is_locked(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "registered_count": 1})
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )
    await db["event_user_locks"].insert_one(
        {
            "_id": "1:7",
            "event_id": 1,
            "user_id": 7,
            "acquired_at": datetime.now(),
        }
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.delete("/events/1/attendance")

    assert resp.status_code == 409
    saved = await db["attendance"].find_one({"event_id": 1, "user_id": 7})
    assert saved is not None
    assert saved["status"] == "going"
    event = await db["events"].find_one({"id": 1})
    assert event is not None
    assert event["registered_count"] == 1


@pytest.mark.asyncio
async def test_remove_attendee_removes_calendar_and_google_calendar_event(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "registered_count": 1})
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "checked_in", "checked_in_at": None}
    )
    await db["user_calendar_entries"].insert_one(
        {
            "event_id": 1,
            "user_id": 7,
            "added_at": datetime(2026, 6, 1, 12, 0, 0),
            "google_calendar_event_id": "google-event-1",
        }
    )

    _, client = _make_client(db, _auth_user(1))
    delete_google_calendar_event = AsyncMock(return_value=None)
    with (
        patch.object(
            events_route,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            events_route,
            "delete_google_calendar_event",
            delete_google_calendar_event,
        ),
    ):
        async with client:
            resp = await client.delete("/events/1/attendees/7")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_id": 1,
        "user_id": 7,
        "status": "cancelled",
        "in_calendar": False,
        "google_synced": True,
    }
    saved = await db["attendance"].find_one({"event_id": 1, "user_id": 7})
    assert saved is not None
    assert saved["status"] == "cancelled"
    event = await db["events"].find_one({"id": 1})
    assert event is not None
    assert event["registered_count"] == 0
    calendar_entry = await db["user_calendar_entries"].find_one(
        {"event_id": 1, "user_id": 7}
    )
    assert calendar_entry is None
    delete_google_calendar_event.assert_awaited_once_with(
        "google-access-token",
        "google-event-1",
    )


# -----------------------------------------------------------------------
# Attendee management
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_event_attendees_returns_latest_active_attendees_for_organizer(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    checked_in_at = datetime(2026, 6, 15, 19, 30, 0)
    await db["events"].insert_one({**event_data, "registered_count": 2})
    await db["users"].insert_many(
        [
            _user_doc(7, first_name="Avery", last_name="Zephyr"),
            _user_doc(8, first_name="Blake", last_name="Yellow"),
            _user_doc(9, first_name="Casey", last_name="Xavier"),
        ]
    )
    await db["attendance"].insert_many(
        [
            {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None},
            {
                "event_id": 1,
                "user_id": 8,
                "status": "checked_in",
                "checked_in_at": checked_in_at,
            },
            {"event_id": 1, "user_id": 9, "status": "going", "checked_in_at": None},
            {
                "event_id": 1,
                "user_id": 9,
                "status": "cancelled",
                "checked_in_at": None,
            },
            {"event_id": 1, "user_id": 10, "status": "going", "checked_in_at": None},
        ]
    )

    _, client = _make_client(db, _auth_user(1))
    async with client:
        resp = await client.get("/events/1/attendees")

    assert resp.status_code == 200
    body = resp.json()
    assert body["event_id"] == 1
    assert body["event_title"] == "Test Concert"
    assert body["total_capacity"] == 500
    assert body["going_count"] == 1
    assert body["checked_in_count"] == 1
    assert [attendee["user_id"] for attendee in body["attendees"]] == [8, 7]
    assert body["attendees"][0]["status"] == "checked_in"
    assert body["attendees"][0]["checked_in_at"] == "2026-06-15T19:30:00"
    assert body["attendees"][1]["status"] == "going"


@pytest.mark.asyncio
async def test_get_event_attendees_allows_admin(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, _auth_user(99, roles=["user", "admin"]))
    async with client:
        resp = await client.get("/events/1/attendees")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_event_attendees_rejects_non_organizer(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.get("/events/1/attendees")

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Organizer or administrator access required"


@pytest.mark.asyncio
async def test_check_in_attendee_updates_attendance_for_organizer(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )

    _, client = _make_client(db, _auth_user(1))
    async with client:
        resp = await client.post("/events/1/attendees/7/check-in")

    assert resp.status_code == 200
    body = resp.json()
    assert body["event_id"] == 1
    assert body["user_id"] == 7
    assert body["status"] == "checked_in"
    saved = await db["attendance"].find_one({"event_id": 1, "user_id": 7})
    assert saved is not None
    assert saved["status"] == "checked_in"
    assert isinstance(saved["checked_in_at"], datetime)


@pytest.mark.asyncio
async def test_check_in_attendee_rejects_non_organizer(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.post("/events/1/attendees/7/check-in")

    assert resp.status_code == 403
    saved = await db["attendance"].find_one({"event_id": 1, "user_id": 7})
    assert saved is not None
    assert saved["status"] == "going"


@pytest.mark.asyncio
async def test_undo_check_in_attendee_updates_attendance_for_admin(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    checked_in_at = datetime(2026, 6, 15, 19, 30, 0)
    await db["events"].insert_one(event_data)
    await db["attendance"].insert_one(
        {
            "event_id": 1,
            "user_id": 7,
            "status": "checked_in",
            "checked_in_at": checked_in_at,
        }
    )

    _, client = _make_client(db, _auth_user(99, roles=["user", "admin"]))
    async with client:
        resp = await client.delete("/events/1/attendees/7/check-in")

    assert resp.status_code == 200
    assert resp.json() == {"event_id": 1, "user_id": 7, "status": "going"}
    saved = await db["attendance"].find_one({"event_id": 1, "user_id": 7})
    assert saved is not None
    assert saved["status"] == "going"
    assert saved["checked_in_at"] is None


@pytest.mark.asyncio
async def test_undo_check_in_attendee_rejects_non_organizer(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    checked_in_at = datetime(2026, 6, 15, 19, 30, 0)
    await db["events"].insert_one(event_data)
    await db["attendance"].insert_one(
        {
            "event_id": 1,
            "user_id": 7,
            "status": "checked_in",
            "checked_in_at": checked_in_at,
        }
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.delete("/events/1/attendees/7/check-in")

    assert resp.status_code == 403
    saved = await db["attendance"].find_one({"event_id": 1, "user_id": 7})
    assert saved is not None
    assert saved["status"] == "checked_in"
    assert saved["checked_in_at"] == checked_in_at


@pytest.mark.asyncio
async def test_remove_attendee_rejects_non_organizer(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "registered_count": 1})
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )
    await db["user_calendar_entries"].insert_one(
        {"event_id": 1, "user_id": 7, "added_at": datetime(2026, 6, 1, 12, 0, 0)}
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.delete("/events/1/attendees/7")

    assert resp.status_code == 403
    saved = await db["attendance"].find_one({"event_id": 1, "user_id": 7})
    assert saved is not None
    assert saved["status"] == "going"
    event = await db["events"].find_one({"id": 1})
    assert event is not None
    assert event["registered_count"] == 1
    calendar_entry = await db["user_calendar_entries"].find_one(
        {"event_id": 1, "user_id": 7}
    )
    assert calendar_entry is not None


# -----------------------------------------------------------------------
# Search
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_by_title(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "title": "Summer Music Festival"},
            {**event_data, "id": 2, "title": "Tech Conference"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"q": "summer"})

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Summer Music Festival"


@pytest.mark.asyncio
async def test_search_by_about(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "about": "A wonderful jazz evening"},
            {**event_data, "id": 2, "about": "Boring meeting"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"q": "jazz"})

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["about"] == "A wonderful jazz evening"


# -----------------------------------------------------------------------
# Filters
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_by_category(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "category": "Music"},
            {**event_data, "id": 2, "category": "Sports"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"category": "Music"})

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "Music"


@pytest.mark.asyncio
async def test_filter_by_city(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    sf = {**event_data, "id": 1}
    ny = {
        **event_data,
        "id": 2,
        "title": "NY Event",
        "location": {**event_data["location"], "city": "New York"},
    }
    await db["events"].insert_many([sf, ny])

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"city": "new york"})

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "NY Event"


@pytest.mark.asyncio
async def test_filter_by_is_online(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "is_online": False},
            {**event_data, "id": 2, "is_online": True, "title": "Webinar"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"is_online": "true"})

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Webinar"


@pytest.mark.asyncio
async def test_filter_by_price_type_free(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "price": 0.0, "title": "Free Event"},
            {**event_data, "id": 2, "price": 50.0, "title": "Paid Event"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"price_type": "free"})

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Free Event"


@pytest.mark.asyncio
async def test_filter_by_price_type_paid(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "price": 0.0, "title": "Free Event"},
            {**event_data, "id": 2, "price": 50.0, "title": "Paid Event"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"price_type": "paid"})

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Paid Event"


@pytest.mark.asyncio
async def test_filter_by_date_range(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {
                **event_data,
                "id": 1,
                "title": "Early",
                "start_time": datetime(2026, 3, 1, 10, 0),
                "end_time": datetime(2026, 3, 1, 12, 0),
            },
            {
                **event_data,
                "id": 2,
                "title": "Late",
                "start_time": datetime(2026, 9, 1, 10, 0),
                "end_time": datetime(2026, 9, 1, 12, 0),
            },
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get(
            "/events/",
            params={
                "start_from": "2026-06-01T00:00:00",
                "start_to": "2026-12-31T23:59:59",
            },
        )

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Late"


# -----------------------------------------------------------------------
# Sorting
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sort_by_price_desc(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "title": "Cheap", "price": 10.0},
            {**event_data, "id": 2, "title": "Expensive", "price": 100.0},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get(
            "/events/", params={"sort_by": "price", "sort_order": "desc"}
        )

    titles = [i["title"] for i in resp.json()["items"]]
    assert titles == ["Expensive", "Cheap"]


@pytest.mark.asyncio
async def test_sort_by_title_asc(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "title": "Zebra"},
            {**event_data, "id": 2, "title": "Alpha"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get(
            "/events/", params={"sort_by": "title", "sort_order": "asc"}
        )

    titles = [i["title"] for i in resp.json()["items"]]
    assert titles == ["Alpha", "Zebra"]


# -----------------------------------------------------------------------
# Pagination
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_paginate_events(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    docs = [
        {
            **event_data,
            "id": i,
            "title": f"Event {i:02d}",
            "start_time": datetime(2026, 1, 1, 10, 0),
            "end_time": datetime(2026, 1, 1, 12, 0),
        }
        for i in range(1, 21)
    ]
    await db["events"].insert_many(docs)

    _, client = _make_client(db)
    async with client:
        resp = await client.get(
            "/events/",
            params={"page": 2, "page_size": 5, "sort_by": "title", "sort_order": "asc"},
        )

    body = resp.json()
    assert body["total"] == 20
    assert body["page"] == 2
    assert body["page_size"] == 5
    assert len(body["items"]) == 5
    assert body["items"][0]["title"] == "Event 06"


@pytest.mark.asyncio
async def test_invalid_page_returns_422(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"page": 0})
    assert resp.status_code == 422


# -----------------------------------------------------------------------
# GET /events/{event_id}  — Detail
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_event_detail(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)
    await db["attendance"].insert_many(
        [
            {"event_id": 1, "user_id": i, "status": "going", "checked_in_at": None}
            for i in range(1, 4)
        ]
    )
    await db["event_favorites"].insert_many(
        [{"event_id": 1, "user_id": i} for i in range(1, 3)]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["title"] == "Test Concert"
    assert body["attending_count"] == 3
    assert body["favorites_count"] == 2
    assert len(body["schedule"]) == 2
    assert body["location"]["city"] == "San Francisco"


@pytest.mark.asyncio
async def test_get_event_not_found(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_event_hides_pending_event(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "status": "pending"})

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/1")

    assert resp.status_code == 404


# -----------------------------------------------------------------------
# POST /events/  — Create
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_event(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    payload = {
        "title": "New Event",
        "about": "A brand new event",
        "price": 25.0,
        "total_capacity": 200,
        "start_time": "2026-08-01T10:00:00",
        "end_time": "2026-08-01T18:00:00",
        "category": "Workshop",
        "is_online": False,
        "schedule": [],
        "location": {
            "longitude": -122.4194,
            "latitude": 37.7749,
            "address": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94102",
        },
    }

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.post("/events/", json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == 1
    assert body["title"] == "New Event"
    assert body["attending_count"] == 0
    assert body["favorites_count"] == 0

    stored = await db["events"].find_one({"id": 1})
    assert stored is not None
    assert stored["title"] == "New Event"
    assert stored["organizer_user_id"] == 1
    assert stored["registered_count"] == 0
    assert stored["status"] == "pending"


@pytest.mark.asyncio
async def test_upload_event_image_allows_organizer(
    db: AsyncDatabase[dict[str, Any]],
    event_data: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _clean(db)
    monkeypatch.setattr(events_route, "UPLOAD_DIR", str(tmp_path))
    await db["events"].insert_one({**event_data, "organizer_user_id": 7})

    _, client = _make_client(db, auth_user=_auth_user(7))
    async with client:
        resp = await client.post(
            "/events/1/image",
            files={"file": ("banner.png", BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        )

    assert resp.status_code == 200
    image_url = resp.json()["image_url"]
    assert image_url.startswith("/uploads/event_1_")
    assert image_url.endswith(".png")
    assert (tmp_path / image_url.rsplit("/", 1)[-1]).exists()

    stored = await db["events"].find_one({"id": 1})
    assert stored is not None
    assert stored["image_url"] == image_url


@pytest.mark.asyncio
async def test_upload_event_image_allows_admin(
    db: AsyncDatabase[dict[str, Any]],
    event_data: dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _clean(db)
    monkeypatch.setattr(events_route, "UPLOAD_DIR", str(tmp_path))
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, auth_user=_auth_user(99, roles=["user", "admin"]))
    async with client:
        resp = await client.post(
            "/events/1/image",
            files={"file": ("banner.jpg", BytesIO(b"fake-jpeg"), "image/jpeg")},
        )

    assert resp.status_code == 200
    assert resp.json()["image_url"].startswith("/uploads/event_1_")


@pytest.mark.asyncio
async def test_upload_event_image_rejects_non_organizer(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, auth_user=_auth_user(2))
    async with client:
        resp = await client.post(
            "/events/1/image",
            files={"file": ("banner.png", BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
        )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Organizer or administrator access required"


@pytest.mark.asyncio
async def test_get_event_for_management_allows_organizer(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "status": "pending"})

    _, client = _make_client(db, auth_user=_auth_user(1))
    async with client:
        resp = await client.get("/events/1/manage")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_update_event_allows_admin(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, auth_user=_auth_user(99, roles=["user", "admin"]))
    async with client:
        resp = await client.patch(
            "/events/1",
            json={
                "title": "Updated Event",
                "price": 12.5,
                "total_capacity": 250,
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Updated Event"
    assert body["price"] == 12.5
    assert body["total_capacity"] == 250

    stored = await db["events"].find_one({"id": 1})
    assert stored is not None
    assert stored["title"] == "Updated Event"


@pytest.mark.asyncio
async def test_update_event_rejects_non_organizer(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, auth_user=_auth_user(2))
    async with client:
        resp = await client.patch("/events/1", json={"title": "Nope"})

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Organizer or administrator access required"


@pytest.mark.asyncio
async def test_create_event_auto_increments_id(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    payload = {
        "title": "Second Event",
        "about": "Another event",
        "price": 0.0,
        "total_capacity": 50,
        "start_time": "2026-09-01T10:00:00",
        "end_time": "2026-09-01T12:00:00",
        "category": "Music",
        "schedule": [],
        "location": {
            "longitude": -73.9654,
            "latitude": 40.7829,
            "address": "Central Park West",
            "city": "New York",
            "state": "NY",
            "zip_code": "10024",
        },
    }

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.post("/events/", json=payload)

    assert resp.status_code == 201
    assert resp.json()["id"] == 2


@pytest.mark.asyncio
async def test_create_event_validation_error(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.post("/events/", json={"title": "incomplete"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_event_requires_authentication(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/events/",
            json={
                "title": "New Event",
                "about": "A brand new event",
                "price": 25.0,
                "total_capacity": 200,
                "start_time": "2026-08-01T10:00:00",
                "end_time": "2026-08-01T18:00:00",
                "category": "Workshop",
                "is_online": False,
                "schedule": [],
                "location": {
                    "longitude": -122.4194,
                    "latitude": 37.7749,
                    "address": "123 Main St",
                    "city": "San Francisco",
                    "state": "CA",
                    "zip_code": "94102",
                },
            },
        )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication required"


# -----------------------------------------------------------------------
# Favorites
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_and_remove_favorite(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, auth_user=_auth_user(42))
    async with client:
        resp = await client.post("/events/1/favorites")
    assert resp.status_code == 201
    assert resp.json()["status"] == "favorited"

    count = await db["event_favorites"].count_documents({"event_id": 1, "user_id": 42})
    assert count == 1

    _, client = _make_client(db, auth_user=_auth_user(42))
    async with client:
        resp = await client.request("DELETE", "/events/1/favorites")
    assert resp.status_code == 200
    assert resp.json()["status"] == "unfavorited"

    count = await db["event_favorites"].count_documents({"event_id": 1, "user_id": 42})
    assert count == 0


@pytest.mark.asyncio
async def test_favorite_idempotent(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        await client.post("/events/1/favorites")
        await client.post("/events/1/favorites")

    count = await db["event_favorites"].count_documents({"event_id": 1, "user_id": 1})
    assert count == 1


@pytest.mark.asyncio
async def test_favorite_nonexistent_event(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.post("/events/9999/favorites")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_favorite_pending_event_hidden_from_public_access(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one({**event_data, "status": "pending"})

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.post("/events/1/favorites")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unfavorite_nonexistent_event(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.request("DELETE", "/events/9999/favorites")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_favorite_requires_authentication(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/1/favorites")

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication required"
