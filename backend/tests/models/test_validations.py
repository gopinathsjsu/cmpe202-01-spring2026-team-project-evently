from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.models.attendance import AttendanceStatus, EventAttendance
from backend.models.event import Event, EventCategory, Location


class TestEventValidation:
    def test_end_time_must_be_after_start_time(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Event(
                id=1,
                title="Test Event",
                about="Description",
                organizer_user_id=1,
                price=10.0,
                total_capacity=100,
                start_time=datetime(2026, 6, 15, 20, 0, 0),
                end_time=datetime(2026, 6, 15, 19, 0, 0),
                category=EventCategory.Music,
                schedule=[],
                location=Location(
                    longitude=-122.4194,
                    latitude=37.7749,
                    address="123 Main St",
                    city="San Francisco",
                    state="CA",
                    zip_code="94102",
                ),
            )
        assert "End time must be after start time" in str(exc_info.value)

    def test_end_time_equal_to_start_time_fails(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Event(
                id=1,
                title="Test Event",
                about="Description",
                organizer_user_id=1,
                price=10.0,
                total_capacity=100,
                start_time=datetime(2026, 6, 15, 19, 0, 0),
                end_time=datetime(2026, 6, 15, 19, 0, 0),
                category=EventCategory.Music,
                schedule=[],
                location=Location(
                    longitude=-122.4194,
                    latitude=37.7749,
                    address="123 Main St",
                    city="San Francisco",
                    state="CA",
                    zip_code="94102",
                ),
            )
        assert "End time must be after start time" in str(exc_info.value)

    def test_price_cannot_be_negative(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Event(
                id=1,
                title="Test Event",
                about="Description",
                organizer_user_id=1,
                price=-10.0,
                total_capacity=100,
                start_time=datetime(2026, 6, 15, 19, 0, 0),
                end_time=datetime(2026, 6, 15, 20, 0, 0),
                category=EventCategory.Music,
                schedule=[],
                location=Location(
                    longitude=-122.4194,
                    latitude=37.7749,
                    address="123 Main St",
                    city="San Francisco",
                    state="CA",
                    zip_code="94102",
                ),
            )
        assert "Price must be non-negative" in str(exc_info.value)

    def test_zero_price_is_valid(self) -> None:
        event = Event(
            id=1,
            title="Free Event",
            about="Description",
            organizer_user_id=1,
            price=0.0,
            total_capacity=100,
            start_time=datetime(2026, 6, 15, 19, 0, 0),
            end_time=datetime(2026, 6, 15, 20, 0, 0),
            category=EventCategory.Music,
            schedule=[],
            location=Location(
                longitude=-122.4194,
                latitude=37.7749,
                address="123 Main St",
                city="San Francisco",
                state="CA",
                zip_code="94102",
            ),
        )
        assert event.price == 0.0

    def test_capacity_must_be_positive(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Event(
                id=1,
                title="Test Event",
                about="Description",
                organizer_user_id=1,
                price=10.0,
                total_capacity=0,
                start_time=datetime(2026, 6, 15, 19, 0, 0),
                end_time=datetime(2026, 6, 15, 20, 0, 0),
                category=EventCategory.Music,
                schedule=[],
                location=Location(
                    longitude=-122.4194,
                    latitude=37.7749,
                    address="123 Main St",
                    city="San Francisco",
                    state="CA",
                    zip_code="94102",
                ),
            )
        assert "Total capacity must be positive" in str(exc_info.value)

    def test_capacity_cannot_be_negative(self) -> None:
        with pytest.raises(ValidationError):
            Event(
                id=1,
                title="Test Event",
                about="Description",
                organizer_user_id=1,
                price=10.0,
                total_capacity=-5,
                start_time=datetime(2026, 6, 15, 19, 0, 0),
                end_time=datetime(2026, 6, 15, 20, 0, 0),
                category=EventCategory.Music,
                schedule=[],
                location=Location(
                    longitude=-122.4194,
                    latitude=37.7749,
                    address="123 Main St",
                    city="San Francisco",
                    state="CA",
                    zip_code="94102",
                ),
            )


class TestLocationValidation:
    def test_latitude_bounds_valid(self) -> None:
        location = Location(
            longitude=-122.4194,
            latitude=37.7749,
            address="123 Main St",
            city="San Francisco",
            state="CA",
            zip_code="94102",
        )
        assert location.latitude == 37.7749

    def test_latitude_too_high_fails(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Location(
                longitude=-122.4194,
                latitude=91.0,
                address="123 Main St",
                city="San Francisco",
                state="CA",
                zip_code="94102",
            )
        assert "Latitude must be between -90 and 90" in str(exc_info.value)

    def test_latitude_too_low_fails(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Location(
                longitude=-122.4194,
                latitude=-91.0,
                address="123 Main St",
                city="San Francisco",
                state="CA",
                zip_code="94102",
            )
        assert "Latitude must be between -90 and 90" in str(exc_info.value)

    def test_longitude_too_high_fails(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Location(
                longitude=181.0,
                latitude=37.7749,
                address="123 Main St",
                city="San Francisco",
                state="CA",
                zip_code="94102",
            )
        assert "Longitude must be between -180 and 180" in str(exc_info.value)

    def test_longitude_too_low_fails(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Location(
                longitude=-181.0,
                latitude=37.7749,
                address="123 Main St",
                city="San Francisco",
                state="CA",
                zip_code="94102",
            )
        assert "Longitude must be between -180 and 180" in str(exc_info.value)


class TestAttendanceValidation:
    def test_checked_in_requires_checked_in_at(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            EventAttendance(
                event_id=1,
                user_id=1,
                status=AttendanceStatus.CheckedIn,
                checked_in_at=None,
            )
        assert "checked_in_at is required when status is checked_in" in str(
            exc_info.value
        )

    def test_checked_in_with_checked_in_at_succeeds(self) -> None:
        attendance = EventAttendance(
            event_id=1,
            user_id=1,
            status=AttendanceStatus.CheckedIn,
            checked_in_at=datetime(2026, 6, 15, 19, 30, 0),
        )
        assert attendance.status == AttendanceStatus.CheckedIn

    def test_going_status_does_not_require_checked_in_at(self) -> None:
        attendance = EventAttendance(
            event_id=1,
            user_id=1,
            status=AttendanceStatus.Going,
            checked_in_at=None,
        )
        assert attendance.status == AttendanceStatus.Going

    def test_cancelled_status_does_not_require_checked_in_at(self) -> None:
        attendance = EventAttendance(
            event_id=1,
            user_id=1,
            status=AttendanceStatus.Cancelled,
            checked_in_at=None,
        )
        assert attendance.status == AttendanceStatus.Cancelled
