from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from backend.models.attendance import AttendanceStatus, EventAttendance
from backend.models.event import Event, EventCategory, EventScheduleEntry, Location
from backend.models.event_favorite import EventFavorite
from backend.models.ticket import Ticket
from backend.models.user import GlobalRole, User, UserProfile


def _valid_location(**overrides: Any) -> Location:
    defaults: dict[str, Any] = {
        "longitude": -122.4194,
        "latitude": 37.7749,
        "address": "123 Main St",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94102",
    }
    return Location(**{**defaults, **overrides})


def _valid_event(**overrides: Any) -> Event:
    defaults: dict[str, Any] = {
        "id": 1,
        "title": "Test Event",
        "about": "Description",
        "organizer_user_id": 1,
        "price": 10.0,
        "total_capacity": 100,
        "start_time": datetime(2026, 6, 15, 19, 0, 0),
        "end_time": datetime(2026, 6, 15, 20, 0, 0),
        "category": EventCategory.Music,
        "schedule": [],
        "location": _valid_location(),
    }
    return Event(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# Location boundary tests
# ---------------------------------------------------------------------------


class TestLocationBoundaries:
    def test_latitude_exactly_90(self) -> None:
        loc = _valid_location(latitude=90.0)
        assert loc.latitude == 90.0

    def test_latitude_exactly_neg90(self) -> None:
        loc = _valid_location(latitude=-90.0)
        assert loc.latitude == -90.0

    def test_longitude_exactly_180(self) -> None:
        loc = _valid_location(longitude=180.0)
        assert loc.longitude == 180.0

    def test_longitude_exactly_neg180(self) -> None:
        loc = _valid_location(longitude=-180.0)
        assert loc.longitude == -180.0

    def test_latitude_zero(self) -> None:
        loc = _valid_location(latitude=0.0)
        assert loc.latitude == 0.0

    def test_longitude_zero(self) -> None:
        loc = _valid_location(longitude=0.0)
        assert loc.longitude == 0.0

    def test_venue_name_optional(self) -> None:
        loc = _valid_location(venue_name=None)
        assert loc.venue_name is None

    def test_venue_name_present(self) -> None:
        loc = _valid_location(venue_name="The Fillmore")
        assert loc.venue_name == "The Fillmore"


# ---------------------------------------------------------------------------
# Event extended validation
# ---------------------------------------------------------------------------


class TestEventExtended:
    def test_free_event(self) -> None:
        event = _valid_event(price=0.0)
        assert event.price == 0.0

    def test_large_capacity(self) -> None:
        event = _valid_event(total_capacity=1_000_000)
        assert event.total_capacity == 1_000_000

    def test_capacity_of_one(self) -> None:
        event = _valid_event(total_capacity=1)
        assert event.total_capacity == 1

    def test_all_categories(self) -> None:
        for cat in EventCategory:
            event = _valid_event(category=cat)
            assert event.category == cat

    def test_is_online_default_false(self) -> None:
        event = _valid_event()
        assert event.is_online is False

    def test_is_online_true(self) -> None:
        event = _valid_event(is_online=True)
        assert event.is_online is True

    def test_image_url_none_by_default(self) -> None:
        event = _valid_event()
        assert event.image_url is None

    def test_image_url_set(self) -> None:
        event = _valid_event(image_url="https://example.com/img.jpg")
        assert event.image_url == "https://example.com/img.jpg"

    def test_schedule_with_entries(self) -> None:
        schedule = [
            EventScheduleEntry(
                start_time=datetime(2026, 6, 15, 19, 0), description="Doors"
            ),
            EventScheduleEntry(
                start_time=datetime(2026, 6, 15, 20, 0), description="Main"
            ),
        ]
        event = _valid_event(schedule=schedule)
        assert len(event.schedule) == 2


# ---------------------------------------------------------------------------
# User model tests
# ---------------------------------------------------------------------------


class TestUserModel:
    def test_default_role_is_user(self) -> None:
        user = User(
            id=1,
            username="test",
            first_name="A",
            last_name="B",
            email="test@example.com",
        )
        assert GlobalRole.User in user.roles
        assert len(user.roles) == 1

    def test_admin_role(self) -> None:
        user = User(
            id=1,
            username="admin",
            first_name="A",
            last_name="B",
            email="admin@example.com",
            roles={GlobalRole.User, GlobalRole.Admin},
        )
        assert GlobalRole.Admin in user.roles

    def test_default_profile_is_empty(self) -> None:
        user = User(
            id=1,
            username="test",
            first_name="A",
            last_name="B",
            email="test@example.com",
        )
        assert user.profile.bio is None
        assert user.profile.interests == []

    def test_phone_number_optional(self) -> None:
        user = User(
            id=1,
            username="test",
            first_name="A",
            last_name="B",
            email="test@example.com",
        )
        assert user.phone_number is None

    def test_invalid_email_rejected(self) -> None:
        with pytest.raises(ValidationError):
            User(
                id=1,
                username="test",
                first_name="A",
                last_name="B",
                email="not-valid",
            )

    def test_profile_photo_url_optional(self) -> None:
        user = User(
            id=1,
            username="test",
            first_name="A",
            last_name="B",
            email="test@example.com",
        )
        assert user.profile_photo_url is None


# ---------------------------------------------------------------------------
# UserProfile tests
# ---------------------------------------------------------------------------


class TestUserProfile:
    def test_all_fields_none(self) -> None:
        profile = UserProfile()
        assert profile.bio is None
        assert profile.location is None
        assert profile.website is None
        assert profile.twitter_handle is None
        assert profile.interests == []

    def test_with_interests(self) -> None:
        profile = UserProfile(interests=["Music", "Tech"])
        assert profile.interests == ["Music", "Tech"]


# ---------------------------------------------------------------------------
# Attendance extended tests
# ---------------------------------------------------------------------------


class TestAttendanceExtended:
    def test_all_statuses(self) -> None:
        for status in [AttendanceStatus.Going, AttendanceStatus.Cancelled]:
            att = EventAttendance(event_id=1, user_id=1, status=status)
            assert att.status == status

    def test_checked_in_with_time(self) -> None:
        att = EventAttendance(
            event_id=1,
            user_id=1,
            status=AttendanceStatus.CheckedIn,
            checked_in_at=datetime(2026, 1, 1, 12, 0),
        )
        assert att.checked_in_at is not None

    def test_default_status_is_going(self) -> None:
        att = EventAttendance(event_id=1, user_id=1)
        assert att.status == AttendanceStatus.Going


# ---------------------------------------------------------------------------
# EventFavorite tests
# ---------------------------------------------------------------------------


class TestEventFavoriteModel:
    def test_creation(self) -> None:
        fav = EventFavorite(event_id=1, user_id=2)
        assert fav.event_id == 1
        assert fav.user_id == 2


# ---------------------------------------------------------------------------
# Ticket model tests
# ---------------------------------------------------------------------------


class TestTicketModel:
    def test_creation(self) -> None:
        ticket = Ticket(
            id=1,
            event_id=1,
            attendee_id=1,
            price=25.0,
            purchase_time=datetime(2026, 6, 1, 12, 0),
        )
        assert ticket.id == 1
        assert ticket.price == 25.0

    def test_free_ticket(self) -> None:
        ticket = Ticket(
            id=1,
            event_id=1,
            attendee_id=1,
            price=0.0,
            purchase_time=datetime(2026, 6, 1, 12, 0),
        )
        assert ticket.price == 0.0
