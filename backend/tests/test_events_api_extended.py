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
# Create event — full round-trip
# -----------------------------------------------------------------------


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    """Return a valid EventCreate payload, with optional field overrides."""
    base: dict[str, Any] = {
        "title": "Round-Trip Event",
        "about": "Test full create-then-read cycle",
        "organizer_user_id": 1,
        "price": 15.0,
        "total_capacity": 300,
        "start_time": "2026-08-01T10:00:00",
        "end_time": "2026-08-01T18:00:00",
        "category": "Workshop",
        "is_online": False,
        "image_url": None,
        "schedule": [],
        "location": {
            "longitude": -122.4194,
            "latitude": 37.7749,
            "venue_name": None,
            "address": "123 Main St",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94102",
        },
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_create_then_get_returns_all_fields(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    """Create an event and GET it back — every field must match."""
    await _clean(db)

    payload = _valid_payload()

    _, client = _make_client(db)
    async with client:
        create_resp = await client.post("/events/", json=payload)
        assert create_resp.status_code == 201
        created = create_resp.json()

        get_resp = await client.get(f"/events/{created['id']}")
        assert get_resp.status_code == 200
        fetched = get_resp.json()

    assert fetched["title"] == payload["title"]
    assert fetched["about"] == payload["about"]
    assert fetched["organizer_user_id"] == payload["organizer_user_id"]
    assert fetched["price"] == payload["price"]
    assert fetched["total_capacity"] == payload["total_capacity"]
    assert fetched["category"] == payload["category"]
    assert fetched["is_online"] == payload["is_online"]
    assert fetched["image_url"] == payload["image_url"]
    assert fetched["schedule"] == payload["schedule"]
    assert fetched["location"]["city"] == "San Francisco"
    assert fetched["location"]["state"] == "CA"
    assert fetched["attending_count"] == 0
    assert fetched["favorites_count"] == 0


@pytest.mark.asyncio
async def test_created_event_appears_in_listing(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    """A newly created event must be returned by the list endpoint."""
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        await client.post("/events/", json=_valid_payload(title="Listed Event"))

        resp = await client.get("/events/")

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Listed Event"


@pytest.mark.asyncio
async def test_create_online_event(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/events/", json=_valid_payload(is_online=True, title="Webinar")
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["is_online"] is True
    assert body["title"] == "Webinar"


@pytest.mark.asyncio
async def test_create_event_with_schedule(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    sched = [
        {"start_time": "2026-08-01T10:00:00", "description": "Doors open"},
        {"start_time": "2026-08-01T11:00:00", "description": "Keynote"},
        {"start_time": "2026-08-01T14:00:00", "description": "Workshop"},
    ]

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/", json=_valid_payload(schedule=sched))

    assert resp.status_code == 201
    body = resp.json()
    assert len(body["schedule"]) == 3
    assert body["schedule"][0]["description"] == "Doors open"
    assert body["schedule"][2]["description"] == "Workshop"


@pytest.mark.asyncio
async def test_create_event_with_image_url(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    url = "https://example.com/banner.jpg"
    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/", json=_valid_payload(image_url=url))

    assert resp.status_code == 201
    assert resp.json()["image_url"] == url


@pytest.mark.asyncio
async def test_create_event_with_venue_name(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    location = {
        "longitude": -122.4194,
        "latitude": 37.7749,
        "venue_name": "The Grand Ballroom",
        "address": "456 Event Ave",
        "city": "San Jose",
        "state": "CA",
        "zip_code": "95112",
    }

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/", json=_valid_payload(location=location))

    assert resp.status_code == 201
    assert resp.json()["location"]["venue_name"] == "The Grand Ballroom"


@pytest.mark.asyncio
async def test_create_free_event(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/", json=_valid_payload(price=0.0))

    assert resp.status_code == 201
    assert resp.json()["price"] == 0.0


@pytest.mark.asyncio
async def test_create_event_all_categories(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    """Every valid category string should be accepted."""
    await _clean(db)

    categories = [
        "Music", "Business", "Arts", "Food", "Sports", "Education",
        "Theater", "Comedy", "Festival", "Conference", "Workshop", "Other",
    ]

    _, client = _make_client(db)
    async with client:
        for cat in categories:
            resp = await client.post(
                "/events/", json=_valid_payload(category=cat, title=f"{cat} Event")
            )
            assert resp.status_code == 201, f"Category {cat!r} should be accepted"
            assert resp.json()["category"] == cat

    stored_count = await db["events"].count_documents({})
    assert stored_count == len(categories)


@pytest.mark.asyncio
async def test_create_event_invalid_category(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/events/", json=_valid_payload(category="NotACategory")
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_event_missing_location_fields(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    bad_location = {"longitude": -122.0, "latitude": 37.0}

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/events/", json=_valid_payload(location=bad_location)
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_event_equal_start_end_time(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    """start_time == end_time should be rejected (end must be *after* start)."""
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/events/",
            json=_valid_payload(
                start_time="2026-08-01T10:00:00",
                end_time="2026-08-01T10:00:00",
            ),
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_event_persists_to_database(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    """Verify the document written to MongoDB matches the payload."""
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/events/",
            json=_valid_payload(title="DB Check", price=42.0, total_capacity=999),
        )

    assert resp.status_code == 201
    event_id = resp.json()["id"]

    doc = await db["events"].find_one({"id": event_id})
    assert doc is not None
    assert doc["title"] == "DB Check"
    assert doc["price"] == 42.0
    assert doc["total_capacity"] == 999


@pytest.mark.asyncio
async def test_create_multiple_events_sequential_ids(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    """Creating three events should yield IDs 1, 2, 3."""
    await _clean(db)

    _, client = _make_client(db)
    ids = []
    async with client:
        for i in range(1, 4):
            resp = await client.post(
                "/events/", json=_valid_payload(title=f"Event {i}")
            )
            assert resp.status_code == 201
            ids.append(resp.json()["id"])

    assert ids == [1, 2, 3]


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
