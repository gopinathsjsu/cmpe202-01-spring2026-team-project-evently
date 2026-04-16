from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from arq import ArqRedis
from pymongo.asynchronous.database import AsyncDatabase

from backend.models.attendance import AttendanceStatus
from backend.models.event import Event
from backend.services.notifications.arq import ArqClient
from backend.services.notifications.email import REMINDER_LEAD_TIME_MINUTES
from backend.services.notifications.worker import Context, send_event_reminder

_DEFAULT_EVENT = object()


class _ToListCursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    async def to_list(self, length: int | None) -> list[dict[str, Any]]:
        return self._docs


class _AttendanceCollection:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs
        self.distinct_key: str | None = None
        self.distinct_filter: dict[str, Any] | None = None

    async def distinct(self, key: str, filter: dict[str, Any]) -> list[int]:
        self.distinct_key = key
        self.distinct_filter = filter
        values: list[int] = []
        for doc in self._docs:
            if not _matches_filter(doc, filter):
                continue
            value = doc[key]
            if value not in values:
                values.append(value)
        return values


def _matches_filter(doc: dict[str, Any], filter: dict[str, Any]) -> bool:
    for key, expected in filter.items():
        if isinstance(expected, dict):
            if "$ne" in expected and doc.get(key) == expected["$ne"]:
                return False
            if "$in" in expected and doc.get(key) not in expected["$in"]:
                return False
        elif doc.get(key) != expected:
            return False
    return True


class _UsersCollection:
    def __init__(self, users: list[dict[str, Any]]) -> None:
        self._users = users
        self.find_filter: dict[str, Any] | None = None

    def find(self, filter: dict[str, Any]) -> _ToListCursor:
        self.find_filter = filter
        return _ToListCursor(
            [user for user in self._users if _matches_filter(user, filter)]
        )


class _EventsCollection:
    def __init__(self, event: dict[str, Any] | None) -> None:
        self._event = event
        self.find_one_filter: dict[str, Any] | None = None

    async def find_one(self, filter: dict[str, Any]) -> dict[str, Any] | None:
        self.find_one_filter = filter
        return self._event


class _ReminderDb:
    def __init__(
        self,
        *,
        event: dict[str, Any] | None | object = _DEFAULT_EVENT,
        attendance_docs: list[dict[str, Any]] | None = None,
    ) -> None:
        self.attendance = _AttendanceCollection(
            attendance_docs
            or [
                {
                    "event_id": 11,
                    "user_id": 7,
                    "status": AttendanceStatus.Going.value,
                    "checked_in_at": None,
                },
                {
                    "event_id": 11,
                    "user_id": 8,
                    "status": AttendanceStatus.CheckedIn.value,
                    "checked_in_at": datetime(2026, 8, 1, 9, 30, 0),
                },
            ]
        )
        self.users = _UsersCollection(
            [
                {"id": 7, "email": "first@example.com"},
                {"id": 8, "email": "second@example.com"},
                {"id": 9, "email": "cancelled@example.com"},
            ]
        )
        event_doc = (
            {
                "_id": "mongo-event-id",
                "id": 11,
                "title": "Reminder Event",
                "about": "A reminder should use Evently ids",
                "organizer_user_id": 1,
                "price": 0.0,
                "total_capacity": 100,
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
            if event is _DEFAULT_EVENT
            else event
        )
        self.events = _EventsCollection(cast(dict[str, Any] | None, event_doc))

    def __getitem__(self, name: str) -> object:
        collections: dict[str, object] = {
            "attendance": self.attendance,
            "users": self.users,
            "events": self.events,
        }
        return collections[name]


class _ReminderEmail:
    def __init__(self) -> None:
        self.sent: list[tuple[str, Event]] = []

    async def send_event_reminder(self, recipient_email: str, event: Event) -> None:
        self.sent.append((recipient_email, event))


@pytest.mark.asyncio
async def test_reminder_worker_uses_evently_ids_for_event_and_recipients() -> None:
    db = _ReminderDb()
    email = _ReminderEmail()
    ctx = cast(Context, {"db": db, "email": email})

    await send_event_reminder(ctx, 11)

    assert db.attendance.distinct_key == "user_id"
    assert db.attendance.distinct_filter == {
        "event_id": 11,
        "status": {"$ne": AttendanceStatus.Cancelled.value},
    }
    assert db.users.find_filter == {"id": {"$in": [7, 8]}}
    assert db.events.find_one_filter == {"id": 11}
    assert [(recipient, event.id) for recipient, event in email.sent] == [
        ("first@example.com", 11),
        ("second@example.com", 11),
    ]


@pytest.mark.asyncio
async def test_reminder_worker_excludes_cancelled_attendance() -> None:
    db = _ReminderDb(
        attendance_docs=[
            {
                "event_id": 11,
                "user_id": 7,
                "status": AttendanceStatus.Going.value,
                "checked_in_at": None,
            },
            {
                "event_id": 11,
                "user_id": 8,
                "status": AttendanceStatus.CheckedIn.value,
                "checked_in_at": datetime(2026, 8, 1, 9, 30, 0),
            },
            {
                "event_id": 11,
                "user_id": 9,
                "status": AttendanceStatus.Cancelled.value,
                "checked_in_at": None,
            },
        ]
    )
    email = _ReminderEmail()
    ctx = cast(Context, {"db": db, "email": email})

    await send_event_reminder(ctx, 11)

    assert db.users.find_filter == {"id": {"$in": [7, 8]}}
    assert [recipient for recipient, _ in email.sent] == [
        "first@example.com",
        "second@example.com",
    ]


@pytest.mark.asyncio
async def test_reminder_worker_logs_and_skips_when_event_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    db = _ReminderDb(event=None)
    email = _ReminderEmail()
    ctx = cast(Context, {"db": db, "email": email})

    with caplog.at_level("ERROR"):
        await send_event_reminder(ctx, 11)

    assert "Event with id 11 not found for reminder job" in caplog.text
    assert email.sent == []


class _UpcomingEventsCursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def __aiter__(self) -> AsyncIterator[dict[str, Any]]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[dict[str, Any]]:
        for doc in self._docs:
            yield doc


class _UpcomingEventsCollection:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs
        self.find_filter: dict[str, Any] | None = None

    def find(self, filter: dict[str, Any]) -> _UpcomingEventsCursor:
        self.find_filter = filter
        return _UpcomingEventsCursor(self._docs)


class _UpcomingEventsDb:
    def __init__(self, events: _UpcomingEventsCollection) -> None:
        self.events = events

    def __getitem__(self, name: str) -> _UpcomingEventsCollection:
        if name != "events":
            raise KeyError(name)
        return self.events


class _RecordingArqClient(ArqClient):
    def __init__(self) -> None:
        self.scheduled: list[tuple[int, datetime]] = []

    async def schedule_event_reminder(self, event_id: int, run_at: datetime) -> None:
        self.scheduled.append((event_id, run_at))


class _FakeArqRedis:
    def __init__(self) -> None:
        self.enqueue_job = AsyncMock()
        self.aclose = AsyncMock()


@pytest.mark.asyncio
async def test_schedule_event_reminder_enqueues_arq_job() -> None:
    redis = _FakeArqRedis()
    arq = ArqClient(cast(ArqRedis, redis))
    run_at = datetime(2026, 8, 1, 9, 0, 0)

    await arq.schedule_event_reminder(42, run_at)

    redis.enqueue_job.assert_awaited_once_with(
        "send_event_reminder",
        event_id=42,
        _defer_until=run_at,
        _job_id="event_reminder_42",
    )


@pytest.mark.asyncio
async def test_startup_reschedules_reminders_with_evently_event_id() -> None:
    start_time = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=2)
    events = _UpcomingEventsCollection(
        [{"_id": "mongo-event-id", "id": 42, "start_time": start_time}]
    )
    db = _UpcomingEventsDb(events)
    arq = _RecordingArqClient()

    await arq.schedule_all_upcoming_event_reminders(
        cast(AsyncDatabase[dict[str, Any]], db)
    )

    assert events.find_filter is not None
    assert events.find_filter.keys() == {"start_time"}
    assert arq.scheduled == [
        (42, start_time - timedelta(minutes=REMINDER_LEAD_TIME_MINUTES))
    ]


@pytest.mark.asyncio
async def test_startup_rescheduling_skips_events_inside_reminder_window() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    near_start_time = now + timedelta(minutes=30)
    later_start_time = now + timedelta(hours=2)
    events = _UpcomingEventsCollection(
        [
            {"_id": "near-mongo-id", "id": 41, "start_time": near_start_time},
            {"_id": "later-mongo-id", "id": 42, "start_time": later_start_time},
        ]
    )
    db = _UpcomingEventsDb(events)
    arq = _RecordingArqClient()

    await arq.schedule_all_upcoming_event_reminders(
        cast(AsyncDatabase[dict[str, Any]], db)
    )

    assert arq.scheduled == [
        (42, later_start_time - timedelta(minutes=REMINDER_LEAD_TIME_MINUTES))
    ]
