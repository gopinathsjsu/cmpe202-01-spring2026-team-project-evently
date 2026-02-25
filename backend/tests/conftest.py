import os
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

import pytest
import pytest_asyncio
from pymongo.asynchronous.database import AsyncDatabase

from backend.db import get_database


@pytest.fixture
def user_data() -> dict[str, Any]:
    return {
        "id": 1,
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
        "email": "testuser@example.com",
        "phone_number": "+1234567890",
        "roles": ["user"],
        "profile": {
            "bio": "Test bio",
            "location": "San Francisco",
            "website": "https://example.com",
            "twitter_handle": "testuser",
            "instagram_handle": "testuser",
            "facebook_handle": "testuser",
            "linkedin_handle": "testuser",
            "interests": ["music", "tech"],
        },
    }


@pytest.fixture
def event_data() -> dict[str, Any]:
    return {
        "id": 1,
        "title": "Test Concert",
        "about": "An amazing test concert",
        "organizer_user_id": 1,
        "price": 50.0,
        "total_capacity": 500,
        "start_time": datetime(2026, 6, 15, 19, 0, 0),
        "end_time": datetime(2026, 6, 15, 22, 0, 0),
        "category": "Music",
        "schedule": [
            {
                "start_time": datetime(2026, 6, 15, 19, 0, 0),
                "description": "Doors open",
            },
            {"start_time": datetime(2026, 6, 15, 20, 0, 0), "description": "Main act"},
        ],
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


@pytest.fixture
def ticket_data() -> dict[str, Any]:
    return {
        "id": 1,
        "event_id": 1,
        "attendee_id": 1,
        "price": 50.0,
        "purchase_time": datetime(2026, 6, 1, 12, 0, 0),
    }


@pytest.fixture
def attendance_data() -> dict[str, Any]:
    return {
        "event_id": 1,
        "user_id": 1,
        "status": "going",
        "checked_in_at": None,
    }


@pytest.fixture
def event_favorite_data() -> dict[str, Any]:
    return {
        "event_id": 1,
        "user_id": 1,
    }


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    """Yield a handle to the ``evently_test`` database.

    Skips the test when DATABASE_URL is not set so the suite can still
    run in environments without a live MongoDB instance.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is not set; skipping database tests")

    async with get_database(url, db_name="evently_test") as database:
        yield database
