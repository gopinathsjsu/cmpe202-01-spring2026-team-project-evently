import os
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

from backend.api import create_app
from backend.db import get_db
from backend.routes import events as events_routes
from backend.routes import users as users_routes
from backend.routes.auth import AuthSessionUser, require_authenticated_user


def _sort_key(doc: dict[str, object], field: str) -> datetime | int | float | str:
    value = doc.get(field)
    if isinstance(value, (datetime, int, float, str)):
        return value
    return ""


class _FakeCursor:
    def __init__(self, docs: list[dict[str, object]]) -> None:
        self._docs = docs

    def sort(self, field: str, direction: int) -> "_FakeCursor":
        self._docs = sorted(
            self._docs,
            key=lambda doc: _sort_key(doc, field),
            reverse=direction < 0,
        )
        return self

    def limit(self, amount: int) -> "_FakeCursor":
        self._docs = self._docs[:amount]
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, object]]:
        if length is None:
            return list(self._docs)
        return list(self._docs[:length])

    def __aiter__(self) -> "_FakeCursor":
        self._index = 0
        return self

    async def __anext__(self) -> dict[str, object]:
        if self._index >= len(self._docs):
            raise StopAsyncIteration
        item = self._docs[self._index]
        self._index += 1
        return item


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: list[dict[str, object]] = []
        self._next_id = 1

    def _matches(self, doc: dict[str, object], query: dict[str, object]) -> bool:
        for key, value in query.items():
            if key == "$or":
                if not isinstance(value, list) or not any(
                    self._matches(doc, cast(dict[str, object], part)) for part in value
                ):
                    return False
                continue

            if isinstance(value, dict):
                if "$exists" in value:
                    exists = key in doc
                    if exists is not bool(value["$exists"]):
                        return False
                    continue
                if "$in" in value:
                    options = value["$in"]
                    if not isinstance(options, list) or doc.get(key) not in options:
                        return False
                    continue
                return False

            if doc.get(key) != value:
                return False

        return True

    async def find_one(
        self,
        query: dict[str, object] | None = None,
        _projection: dict[str, int] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
    ) -> dict[str, object] | None:
        query = query or {}
        matches = [doc for doc in self._docs if self._matches(doc, query)]
        if not matches:
            return None

        if sort:
            field, direction = sort[0]
            matches = sorted(
                matches,
                key=lambda doc: _sort_key(doc, field),
                reverse=direction < 0,
            )

        return matches[0]

    def find(self, query: dict[str, object] | None = None) -> _FakeCursor:
        query = query or {}
        return _FakeCursor([doc for doc in self._docs if self._matches(doc, query)])

    async def insert_one(self, doc: dict[str, object]) -> None:
        stored = dict(doc)
        stored.setdefault("_id", self._next_id)
        self._next_id += 1
        self._docs.append(stored)

    async def update_one(
        self,
        query: dict[str, object],
        update: dict[str, dict[str, object]],
        *,
        upsert: bool = False,
    ) -> SimpleNamespace:
        doc = await self.find_one(query)
        if doc is None:
            if not upsert:
                return SimpleNamespace(matched_count=0)
            doc = dict(query)
            doc.setdefault("_id", self._next_id)
            self._next_id += 1
            self._docs.append(doc)

        for key, value in update.get("$set", {}).items():
            doc[key] = value

        return SimpleNamespace(matched_count=1)

    async def delete_one(self, query: dict[str, object]) -> SimpleNamespace:
        for index, doc in enumerate(self._docs):
            if self._matches(doc, query):
                self._docs.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class _FakeDb:
    def __init__(self) -> None:
        self._collections = {
            "users": _FakeCollection(),
            "events": _FakeCollection(),
            "attendance": _FakeCollection(),
            "user_calendar_entries": _FakeCollection(),
            "user_calendar_syncs": _FakeCollection(),
        }

    def __getitem__(self, name: str) -> _FakeCollection:
        return self._collections.setdefault(name, _FakeCollection())


def _make_client(
    db: _FakeDb,
    auth_user: AuthSessionUser | None = None,
    *,
    raise_app_exceptions: bool = True,
) -> tuple[FastAPI, AsyncClient]:
    app = create_app()
    app.state.db = db
    app.dependency_overrides[get_db] = lambda: db
    if auth_user is not None:
        app.dependency_overrides[require_authenticated_user] = lambda: auth_user

    transport = ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
    client = AsyncClient(transport=transport, base_url="http://test")
    return app, client


def _auth_user(user_id: int = 1) -> AuthSessionUser:
    return AuthSessionUser(
        id=user_id,
        email=f"user{user_id}@example.com",
        first_name="Test",
        last_name="User",
        name="Test User",
        roles=["user"],
    )


def _user_doc(user_id: int = 1) -> dict[str, object]:
    return {
        "id": user_id,
        "username": f"user{user_id}",
        "first_name": "Test",
        "last_name": "User",
        "email": f"user{user_id}@example.com",
        "roles": ["user"],
        "profile": {},
    }


def _event_doc() -> dict[str, object]:
    return {
        "id": 1,
        "title": "Test Concert",
        "about": "An amazing test concert",
        "organizer_user_id": 1,
        "price": 50.0,
        "total_capacity": 500,
        "start_time": "2026-06-15T19:00:00+00:00",
        "end_time": "2026-06-15T22:00:00+00:00",
        "category": "Music",
        "is_online": False,
        "image_url": None,
        "schedule": [],
        "location": {
            "longitude": -122.4194,
            "latitude": 37.7749,
            "venue_name": "The Fillmore",
            "address": "1805 Geary Blvd",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94115",
        },
    }


@pytest.mark.asyncio
async def test_add_event_to_app_calendar_saves_event_locally() -> None:
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.post("/events/1/calendar")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_id": 1,
        "status": "added",
        "google_synced": False,
    }
    saved = await db["user_calendar_entries"].find_one({"user_id": 7, "event_id": 1})
    assert saved is not None
    assert saved.get("google_calendar_event_id") is None


@pytest.mark.asyncio
async def test_get_user_calendar_lists_saved_items_and_sync_state() -> None:
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["user_calendar_entries"].insert_one(
        {
            "user_id": 7,
            "event_id": 1,
            "added_at": datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        }
    )
    await db["user_calendar_syncs"].insert_one(
        {"user_id": 7, "google_sync_enabled": True}
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.get("/users/7/calendar")

    assert resp.status_code == 200
    assert resp.json() == {
        "items": [
            {
                "event_id": 1,
                "event_title": "Test Concert",
                "event_image_url": None,
                "start_time": "2026-06-15T19:00:00Z",
                "end_time": "2026-06-15T22:00:00Z",
                "added_at": "2026-05-01T12:00:00Z",
                "google_synced": False,
                "google_calendar_event_url": None,
            }
        ],
        "google_sync_enabled": True,
    }


@pytest.mark.asyncio
async def test_get_user_calendar_backfills_existing_registrations() -> None:
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.get("/users/7/calendar")

    assert resp.status_code == 200
    assert resp.json()["items"][0]["event_id"] == 1
    saved = await db["user_calendar_entries"].find_one({"user_id": 7, "event_id": 1})
    assert saved is not None


@pytest.mark.asyncio
async def test_get_event_calendar_status_backfills_existing_registration() -> None:
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.get("/events/1/calendar")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_id": 1,
        "in_calendar": True,
        "google_sync_enabled": False,
    }
    saved = await db["user_calendar_entries"].find_one({"user_id": 7, "event_id": 1})
    assert saved is not None


@pytest.mark.asyncio
async def test_sync_saved_calendar_to_google_backfills_existing_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example.com/app")
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["user_calendar_entries"].insert_one(
        {"user_id": 7, "event_id": 1, "added_at": datetime.now(tz=UTC)}
    )

    _, client = _make_client(db, _auth_user(7))
    create_google_calendar_event = AsyncMock(
        return_value={
            "id": "google-event-1",
            "htmlLink": "https://calendar.google.com/calendar/event?eid=1",
        }
    )

    with (
        patch.object(
            users_routes,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            users_routes,
            "create_google_calendar_event",
            create_google_calendar_event,
        ),
    ):
        async with client:
            resp = await client.post("/users/7/calendar/sync/google")

    assert resp.status_code == 200
    assert resp.json() == {
        "google_sync_enabled": True,
        "synced_count": 1,
        "skipped_count": 0,
        "status": "enabled",
    }

    saved = await db["user_calendar_entries"].find_one({"user_id": 7, "event_id": 1})
    assert saved is not None
    assert saved["google_calendar_event_id"] == "google-event-1"
    assert (
        saved["google_calendar_event_url"]
        == "https://calendar.google.com/calendar/event?eid=1"
    )

    await_args = create_google_calendar_event.await_args
    assert await_args is not None
    assert await_args.args[0] == "google-access-token"
    assert await_args.args[1] == {
        "summary": "Test Concert",
        "description": (
            "An amazing test concert\n\n"
            "View this event on Evently: https://frontend.example.com/events/1"
        ),
        "location": "The Fillmore, 1805 Geary Blvd, San Francisco, CA 94115",
        "start": {"dateTime": "2026-06-15T19:00:00+00:00"},
        "end": {"dateTime": "2026-06-15T22:00:00+00:00"},
    }


@pytest.mark.asyncio
async def test_sync_saved_calendar_to_google_backfills_existing_registration_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.example.com/app")
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )

    _, client = _make_client(db, _auth_user(7))
    create_google_calendar_event = AsyncMock(
        return_value={
            "id": "google-event-1",
            "htmlLink": "https://calendar.google.com/calendar/event?eid=1",
        }
    )

    with (
        patch.object(
            users_routes,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            users_routes,
            "create_google_calendar_event",
            create_google_calendar_event,
        ),
    ):
        async with client:
            resp = await client.post("/users/7/calendar/sync/google")

    assert resp.status_code == 200
    assert resp.json() == {
        "google_sync_enabled": True,
        "synced_count": 1,
        "skipped_count": 0,
        "status": "enabled",
    }
    saved = await db["user_calendar_entries"].find_one({"user_id": 7, "event_id": 1})
    assert saved is not None
    assert saved["google_calendar_event_id"] == "google-event-1"
    create_google_calendar_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_saved_calendar_to_google_skips_invalid_event_records() -> None:
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["events"].insert_one(
        {
            "id": 2,
            "title": "Broken Event",
            "organizer_user_id": 1,
        }
    )
    await db["user_calendar_entries"].insert_one(
        {"user_id": 7, "event_id": 1, "added_at": datetime.now(tz=UTC)}
    )
    await db["user_calendar_entries"].insert_one(
        {"user_id": 7, "event_id": 2, "added_at": datetime.now(tz=UTC)}
    )

    _, client = _make_client(db, _auth_user(7))
    create_google_calendar_event = AsyncMock(return_value={"id": "google-event-1"})

    with (
        patch.object(
            users_routes,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            users_routes,
            "create_google_calendar_event",
            create_google_calendar_event,
        ),
    ):
        async with client:
            resp = await client.post("/users/7/calendar/sync/google")

    assert resp.status_code == 200
    assert resp.json() == {
        "google_sync_enabled": True,
        "synced_count": 1,
        "skipped_count": 1,
        "status": "enabled",
    }
    create_google_calendar_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_unsync_google_calendar_removes_synced_events_and_disables_sync() -> None:
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["user_calendar_entries"].insert_one(
        {
            "user_id": 7,
            "event_id": 1,
            "added_at": datetime.now(tz=UTC),
            "google_calendar_event_id": "google-event-1",
            "google_calendar_event_url": "https://calendar.google.com/calendar/event?eid=1",
        }
    )
    await db["user_calendar_syncs"].insert_one(
        {"user_id": 7, "google_sync_enabled": True}
    )

    _, client = _make_client(db, _auth_user(7))
    delete_google_calendar_event = AsyncMock(return_value=None)

    with (
        patch.object(
            users_routes,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            users_routes,
            "delete_google_calendar_event",
            delete_google_calendar_event,
        ),
    ):
        async with client:
            resp = await client.delete("/users/7/calendar/sync/google")

    assert resp.status_code == 200
    assert resp.json() == {
        "google_sync_enabled": False,
        "unsynced_count": 1,
        "status": "disabled",
    }
    saved = await db["user_calendar_entries"].find_one({"user_id": 7, "event_id": 1})
    assert saved is not None
    assert saved["google_calendar_event_id"] is None
    assert saved["google_calendar_event_url"] is None
    sync_state = await db["user_calendar_syncs"].find_one({"user_id": 7})
    assert sync_state is not None
    assert sync_state["google_sync_enabled"] is False
    delete_google_calendar_event.assert_awaited_once_with(
        "google-access-token",
        "google-event-1",
    )


@pytest.mark.asyncio
async def test_unsync_google_calendar_disables_sync_when_no_google_events_exist() -> (
    None
):
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["user_calendar_entries"].insert_one(
        {"user_id": 7, "event_id": 1, "added_at": datetime.now(tz=UTC)}
    )
    await db["user_calendar_syncs"].insert_one(
        {"user_id": 7, "google_sync_enabled": True}
    )

    _, client = _make_client(db, _auth_user(7))
    async with client:
        resp = await client.delete("/users/7/calendar/sync/google")

    assert resp.status_code == 200
    assert resp.json() == {
        "google_sync_enabled": False,
        "unsynced_count": 0,
        "status": "disabled",
    }
    sync_state = await db["user_calendar_syncs"].find_one({"user_id": 7})
    assert sync_state is not None
    assert sync_state["google_sync_enabled"] is False


@pytest.mark.asyncio
async def test_add_event_to_app_calendar_syncs_when_google_sync_enabled() -> None:
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["user_calendar_syncs"].insert_one(
        {"user_id": 7, "google_sync_enabled": True}
    )

    _, client = _make_client(db, _auth_user(7))
    with (
        patch.object(
            events_routes,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            events_routes,
            "create_google_calendar_event",
            AsyncMock(return_value={"id": "google-event-1"}),
        ),
    ):
        async with client:
            resp = await client.post("/events/1/calendar")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_id": 1,
        "status": "added",
        "google_synced": True,
    }

    saved = await db["user_calendar_entries"].find_one({"user_id": 7, "event_id": 1})
    assert saved is not None
    assert saved["google_calendar_event_id"] == "google-event-1"


@pytest.mark.asyncio
async def test_add_event_to_app_calendar_rolls_back_google_event_on_local_insert_failure() -> (
    None
):
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["user_calendar_syncs"].insert_one(
        {"user_id": 7, "google_sync_enabled": True}
    )

    _, client = _make_client(db, _auth_user(7))
    delete_google_calendar_event = AsyncMock(return_value=None)

    with (
        patch.object(
            events_routes,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            events_routes,
            "create_google_calendar_event",
            AsyncMock(return_value={"id": "google-event-1"}),
        ),
        patch.object(
            events_routes,
            "delete_google_calendar_event",
            delete_google_calendar_event,
        ),
        patch.object(
            db["user_calendar_entries"],
            "insert_one",
            AsyncMock(side_effect=RuntimeError("db write failed")),
        ),
    ):
        async with client:
            response = await client.post("/events/1/calendar")

    assert response.status_code == 500

    delete_google_calendar_event.assert_awaited_once_with(
        "google-access-token",
        "google-event-1",
    )


@pytest.mark.asyncio
async def test_add_event_to_app_calendar_returns_502_on_unexpected_google_sync_error() -> (
    None
):
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["user_calendar_syncs"].insert_one(
        {"user_id": 7, "google_sync_enabled": True}
    )

    _, client = _make_client(db, _auth_user(7))

    with (
        patch.object(
            events_routes,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            events_routes,
            "create_google_calendar_event",
            AsyncMock(side_effect=RuntimeError("unexpected boom")),
        ),
    ):
        async with client:
            response = await client.post("/events/1/calendar")

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Could not sync this event to Google Calendar. Please try again."
    }


@pytest.mark.asyncio
async def test_remove_event_from_app_calendar_removes_google_event_when_synced() -> (
    None
):
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["user_calendar_entries"].insert_one(
        {
            "user_id": 7,
            "event_id": 1,
            "added_at": datetime.now(tz=UTC),
            "google_calendar_event_id": "google-event-1",
        }
    )

    _, client = _make_client(db, _auth_user(7))
    delete_google_calendar_event = AsyncMock(return_value=None)

    with (
        patch.object(
            events_routes,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            events_routes,
            "delete_google_calendar_event",
            delete_google_calendar_event,
        ),
    ):
        async with client:
            resp = await client.delete("/events/1/calendar")

    assert resp.status_code == 200
    assert resp.json() == {
        "event_id": 1,
        "status": "removed",
        "google_synced": True,
    }
    assert (
        await db["user_calendar_entries"].find_one({"user_id": 7, "event_id": 1})
        is None
    )
    delete_google_calendar_event.assert_awaited_once_with(
        "google-access-token",
        "google-event-1",
    )


@pytest.mark.asyncio
async def test_sync_saved_calendar_to_google_rolls_back_google_event_on_local_update_failure() -> (
    None
):
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["user_calendar_entries"].insert_one(
        {"user_id": 7, "event_id": 1, "added_at": datetime.now(tz=UTC)}
    )

    _, client = _make_client(db, _auth_user(7))
    delete_google_calendar_event = AsyncMock(return_value=None)

    with (
        patch.object(
            users_routes,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            users_routes,
            "create_google_calendar_event",
            AsyncMock(
                return_value={
                    "id": "google-event-1",
                    "htmlLink": "https://calendar.google.com/calendar/event?eid=1",
                }
            ),
        ),
        patch.object(
            users_routes,
            "delete_google_calendar_event",
            delete_google_calendar_event,
        ),
        patch.object(
            db["user_calendar_entries"],
            "update_one",
            AsyncMock(side_effect=RuntimeError("db update failed")),
        ),
    ):
        async with client:
            response = await client.post("/users/7/calendar/sync/google")
            assert response.status_code == 502

    delete_google_calendar_event.assert_awaited_once_with(
        "google-access-token",
        "google-event-1",
    )


@pytest.mark.asyncio
async def test_sync_saved_calendar_to_google_returns_502_on_unexpected_google_error() -> (
    None
):
    db = _FakeDb()
    await db["users"].insert_one(_user_doc(7))
    await db["events"].insert_one(_event_doc())
    await db["user_calendar_entries"].insert_one(
        {"user_id": 7, "event_id": 1, "added_at": datetime.now(tz=UTC)}
    )

    _, client = _make_client(db, _auth_user(7))

    with (
        patch.object(
            users_routes,
            "get_google_calendar_access_token",
            AsyncMock(return_value="google-access-token"),
        ),
        patch.object(
            users_routes,
            "create_google_calendar_event",
            AsyncMock(side_effect=RuntimeError("unexpected boom")),
        ),
    ):
        async with client:
            response = await client.post(
                "/users/7/calendar/sync/google",
                headers={"Origin": "http://localhost:3000"},
            )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Could not sync your calendar to Google Calendar. Please try again."
    }
