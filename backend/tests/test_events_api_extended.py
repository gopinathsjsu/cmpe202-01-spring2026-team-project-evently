from datetime import datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo.asynchronous.database import AsyncDatabase

from backend.api import create_app
from backend.db import get_db


def _make_client(
    db: AsyncDatabase[dict[str, Any]],
) -> tuple[Any, AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return app, client


async def _clean(db: AsyncDatabase[dict[str, Any]]) -> None:
    for coll in ("events", "attendance", "event_favorites"):
        await db[coll].delete_many({})


# -----------------------------------------------------------------------
# Combined filters
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_by_category_and_city(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "category": "Music", "title": "SF Music"},
            {
                **event_data,
                "id": 2,
                "category": "Music",
                "title": "NY Music",
                "location": {**event_data["location"], "city": "New York"},
            },
            {**event_data, "id": 3, "category": "Sports", "title": "SF Sports"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get(
            "/events/", params={"category": "Music", "city": "San Francisco"}
        )

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "SF Music"


@pytest.mark.asyncio
async def test_filter_is_online_true(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "is_online": True, "title": "Online Event"},
            {**event_data, "id": 2, "is_online": False, "title": "In-Person"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"is_online": "true"})

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Online Event"


@pytest.mark.asyncio
async def test_filter_is_online_false(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "is_online": True, "title": "Online"},
            {**event_data, "id": 2, "is_online": False, "title": "In-Person"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"is_online": "false"})

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "In-Person"


@pytest.mark.asyncio
async def test_combined_price_and_online_filter(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {
                **event_data,
                "id": 1,
                "is_online": True,
                "price": 0.0,
                "title": "Free Online",
            },
            {
                **event_data,
                "id": 2,
                "is_online": True,
                "price": 50.0,
                "title": "Paid Online",
            },
            {
                **event_data,
                "id": 3,
                "is_online": False,
                "price": 0.0,
                "title": "Free InPerson",
            },
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get(
            "/events/", params={"is_online": "true", "price_type": "free"}
        )

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Free Online"


# -----------------------------------------------------------------------
# Search with special characters
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_with_regex_chars(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    """Search terms containing regex metacharacters should be escaped."""
    await _clean(db)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "title": "C++ Workshop"},
            {**event_data, "id": 2, "title": "Python Workshop"},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"q": "C++"})

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "C++ Workshop"


@pytest.mark.asyncio
async def test_search_no_match_returns_empty(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"q": "nonexistent_xyz"})

    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


# -----------------------------------------------------------------------
# Sort defaults
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_sort_is_start_time_asc(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many(
        [
            {
                **event_data,
                "id": 1,
                "title": "Later",
                "start_time": datetime(2026, 9, 1, 10, 0),
                "end_time": datetime(2026, 9, 1, 12, 0),
            },
            {
                **event_data,
                "id": 2,
                "title": "Earlier",
                "start_time": datetime(2026, 3, 1, 10, 0),
                "end_time": datetime(2026, 3, 1, 12, 0),
            },
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/")

    titles = [i["title"] for i in resp.json()["items"]]
    assert titles == ["Earlier", "Later"]


# -----------------------------------------------------------------------
# Page size boundary
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_page_size_exceeds_max(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"page_size": 101})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_page_size_zero(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/", params={"page_size": 0})
    assert resp.status_code == 422


# -----------------------------------------------------------------------
# Create event validation
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_event_negative_price(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    payload = {
        "title": "Bad Event",
        "about": "Should fail",
        "organizer_user_id": 1,
        "price": -10.0,
        "total_capacity": 100,
        "start_time": "2026-08-01T10:00:00",
        "end_time": "2026-08-01T18:00:00",
        "category": "Workshop",
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

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_event_end_before_start(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    payload = {
        "title": "Bad Event",
        "about": "End before start",
        "organizer_user_id": 1,
        "price": 10.0,
        "total_capacity": 100,
        "start_time": "2026-08-01T18:00:00",
        "end_time": "2026-08-01T10:00:00",
        "category": "Music",
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

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_event_zero_capacity(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    payload = {
        "title": "Zero Cap",
        "about": "Zero capacity",
        "organizer_user_id": 1,
        "price": 0.0,
        "total_capacity": 0,
        "start_time": "2026-08-01T10:00:00",
        "end_time": "2026-08-01T18:00:00",
        "category": "Music",
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

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/", json=payload)

    assert resp.status_code == 422


# -----------------------------------------------------------------------
# Favorites edge cases
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unfavorite_when_not_favorited(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    """Unfavoriting when the user never favorited should still succeed."""
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.request(
            "DELETE", "/events/1/favorites", json={"user_id": 999}
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "unfavorited"


@pytest.mark.asyncio
async def test_get_event_detail_zero_attending_and_favorites(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/events/1")

    body = resp.json()
    assert body["attending_count"] == 0
    assert body["favorites_count"] == 0
