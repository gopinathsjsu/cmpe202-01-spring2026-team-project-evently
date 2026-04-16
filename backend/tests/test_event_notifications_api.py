from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo.asynchronous.database import AsyncDatabase

from backend.api import create_app
from backend.db import get_db
from backend.models.event import Event
from backend.routes.auth import AuthSessionUser, require_authenticated_user
from backend.services.notifications.arq import get_arq
from backend.services.notifications.email import (
    REMINDER_LEAD_TIME_MINUTES,
    get_email_notif_service,
)


class _MockArq:
    def __init__(self) -> None:
        self.schedule_event_reminder = AsyncMock()


class _MockEmailNotificationService:
    def __init__(self) -> None:
        self.send_event_creation_confirmation = AsyncMock()
        self.send_registration_confirmation = AsyncMock()


def _auth_user() -> AuthSessionUser:
    return AuthSessionUser(
        id=7,
        email="organizer@example.com",
        first_name="Event",
        last_name="Organizer",
        name="Event Organizer",
        roles=["user"],
    )


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Notification Event",
        "about": "A new event that should send notifications",
        "price": 25.0,
        "total_capacity": 100,
        "start_time": "2026-08-01T10:00:00",
        "end_time": "2026-08-01T12:00:00",
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
    payload.update(overrides)
    return payload


def _event_doc(**overrides: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "id": 1,
        "title": "Registration Event",
        "about": "An event that should confirm registrations",
        "organizer_user_id": 1,
        "price": 25.0,
        "total_capacity": 100,
        "registered_count": 0,
        "start_time": datetime(2026, 8, 1, 10, 0, 0),
        "end_time": datetime(2026, 8, 1, 12, 0, 0),
        "category": "Workshop",
        "status": "approved",
        "is_online": False,
        "image_url": None,
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
    event.update(overrides)
    return event


async def _clean(db: AsyncDatabase[dict[str, Any]]) -> None:
    for coll in (
        "events",
        "attendance",
        "event_favorites",
        "counters",
        "user_calendar_entries",
        "user_calendar_syncs",
    ):
        await db[coll].delete_many({})


def _make_client(
    db: AsyncDatabase[dict[str, Any]],
    *,
    arq: _MockArq,
    email_notifs: _MockEmailNotificationService,
) -> AsyncClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_arq] = lambda: arq
    app.dependency_overrides[get_email_notif_service] = lambda: email_notifs
    app.dependency_overrides[require_authenticated_user] = _auth_user
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_create_event_enqueues_reminder_and_sends_confirmation(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    arq = _MockArq()
    email_notifs = _MockEmailNotificationService()
    payload = _valid_payload()

    client = _make_client(db, arq=arq, email_notifs=email_notifs)
    async with client:
        resp = await client.post("/events/", json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == 1

    arq.schedule_event_reminder.assert_awaited_once()
    reminder_call = arq.schedule_event_reminder.await_args
    assert reminder_call is not None
    assert reminder_call.args == (
        1,
        datetime(2026, 8, 1, 10, 0, 0) - timedelta(minutes=REMINDER_LEAD_TIME_MINUTES),
    )

    email_notifs.send_event_creation_confirmation.assert_awaited_once()
    confirmation_call = email_notifs.send_event_creation_confirmation.await_args
    assert confirmation_call is not None
    assert confirmation_call.args[0] == "organizer@example.com"
    event = confirmation_call.args[1]
    assert isinstance(event, Event)
    assert event.id == 1
    assert event.title == payload["title"]
    assert event.organizer_user_id == 7


@pytest.mark.asyncio
async def test_register_event_sends_registration_confirmation(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    await db["events"].insert_one(_event_doc())
    arq = _MockArq()
    email_notifs = _MockEmailNotificationService()

    client = _make_client(db, arq=arq, email_notifs=email_notifs)
    async with client:
        resp = await client.post("/events/1/attendance")

    assert resp.status_code == 200
    email_notifs.send_registration_confirmation.assert_awaited_once()
    confirmation_call = email_notifs.send_registration_confirmation.await_args
    assert confirmation_call is not None
    assert confirmation_call.args[0] == "organizer@example.com"
    event = confirmation_call.args[1]
    assert isinstance(event, Event)
    assert event.id == 1
    assert event.title == "Registration Event"
    email_notifs.send_event_creation_confirmation.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_event_restored_cancelled_registration_sends_confirmation(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    await db["events"].insert_one(_event_doc())
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "cancelled", "checked_in_at": None}
    )
    arq = _MockArq()
    email_notifs = _MockEmailNotificationService()

    client = _make_client(db, arq=arq, email_notifs=email_notifs)
    async with client:
        resp = await client.post("/events/1/attendance")

    assert resp.status_code == 200
    email_notifs.send_registration_confirmation.assert_awaited_once()


@pytest.mark.asyncio
async def test_register_event_existing_active_registration_does_not_confirm_again(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    await db["events"].insert_one(_event_doc(registered_count=1))
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 7, "status": "going", "checked_in_at": None}
    )
    arq = _MockArq()
    email_notifs = _MockEmailNotificationService()

    client = _make_client(db, arq=arq, email_notifs=email_notifs)
    async with client:
        resp = await client.post("/events/1/attendance")

    assert resp.status_code == 200
    email_notifs.send_registration_confirmation.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_event_rejection_does_not_send_registration_confirmation(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    await db["events"].insert_one(_event_doc(total_capacity=1, registered_count=1))
    await db["attendance"].insert_one(
        {"event_id": 1, "user_id": 5, "status": "going", "checked_in_at": None}
    )
    arq = _MockArq()
    email_notifs = _MockEmailNotificationService()

    client = _make_client(db, arq=arq, email_notifs=email_notifs)
    async with client:
        resp = await client.post("/events/1/attendance")

    assert resp.status_code == 400
    email_notifs.send_registration_confirmation.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_event_validation_error_does_not_notify(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    arq = _MockArq()
    email_notifs = _MockEmailNotificationService()

    client = _make_client(db, arq=arq, email_notifs=email_notifs)
    async with client:
        resp = await client.post("/events/", json={"title": "incomplete"})

    assert resp.status_code == 422
    arq.schedule_event_reminder.assert_not_awaited()
    email_notifs.send_event_creation_confirmation.assert_not_awaited()
    email_notifs.send_registration_confirmation.assert_not_awaited()
