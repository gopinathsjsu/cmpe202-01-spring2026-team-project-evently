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
    """Build an app with the DB dependency overridden."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return app, client


async def _clean(db: AsyncDatabase[dict[str, Any]]) -> None:
    for coll in ("events", "attendance", "event_favorites"):
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
    await db["attendance"].insert_many([
        {"event_id": 1, "user_id": i, "status": "going", "checked_in_at": None}
        for i in range(1, 6)
    ])
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


# -----------------------------------------------------------------------
# Search
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_by_title(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_many([
        {**event_data, "id": 1, "title": "Summer Music Festival"},
        {**event_data, "id": 2, "title": "Tech Conference"},
    ])

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
    await db["events"].insert_many([
        {**event_data, "id": 1, "about": "A wonderful jazz evening"},
        {**event_data, "id": 2, "about": "Boring meeting"},
    ])

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
    await db["events"].insert_many([
        {**event_data, "id": 1, "category": "Music"},
        {**event_data, "id": 2, "category": "Sports"},
    ])

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
    await db["events"].insert_many([
        {**event_data, "id": 1, "is_online": False},
        {**event_data, "id": 2, "is_online": True, "title": "Webinar"},
    ])

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
    await db["events"].insert_many([
        {**event_data, "id": 1, "price": 0.0, "title": "Free Event"},
        {**event_data, "id": 2, "price": 50.0, "title": "Paid Event"},
    ])

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
    await db["events"].insert_many([
        {**event_data, "id": 1, "price": 0.0, "title": "Free Event"},
        {**event_data, "id": 2, "price": 50.0, "title": "Paid Event"},
    ])

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
    await db["events"].insert_many([
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
    ])

    _, client = _make_client(db)
    async with client:
        resp = await client.get(
            "/events/",
            params={"start_from": "2026-06-01T00:00:00", "start_to": "2026-12-31T23:59:59"},
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
    await db["events"].insert_many([
        {**event_data, "id": 1, "title": "Cheap", "price": 10.0},
        {**event_data, "id": 2, "title": "Expensive", "price": 100.0},
    ])

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
    await db["events"].insert_many([
        {**event_data, "id": 1, "title": "Zebra"},
        {**event_data, "id": 2, "title": "Alpha"},
    ])

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
    await db["attendance"].insert_many([
        {"event_id": 1, "user_id": i, "status": "going", "checked_in_at": None}
        for i in range(1, 4)
    ])
    await db["event_favorites"].insert_many([
        {"event_id": 1, "user_id": i} for i in range(1, 3)
    ])

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
        "organizer_user_id": 1,
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

    _, client = _make_client(db)
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


@pytest.mark.asyncio
async def test_create_event_auto_increments_id(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    payload = {
        "title": "Second Event",
        "about": "Another event",
        "organizer_user_id": 1,
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

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/", json=payload)

    assert resp.status_code == 201
    assert resp.json()["id"] == 2


@pytest.mark.asyncio
async def test_create_event_validation_error(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/", json={"title": "incomplete"})
    assert resp.status_code == 422


# -----------------------------------------------------------------------
# Favorites
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_and_remove_favorite(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["events"].insert_one(event_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/1/favorites", json={"user_id": 42})
    assert resp.status_code == 201
    assert resp.json()["status"] == "favorited"

    count = await db["event_favorites"].count_documents({"event_id": 1, "user_id": 42})
    assert count == 1

    _, client = _make_client(db)
    async with client:
        resp = await client.request(
            "DELETE", "/events/1/favorites", json={"user_id": 42}
        )
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

    _, client = _make_client(db)
    async with client:
        await client.post("/events/1/favorites", json={"user_id": 1})
        await client.post("/events/1/favorites", json={"user_id": 1})

    count = await db["event_favorites"].count_documents({"event_id": 1, "user_id": 1})
    assert count == 1


@pytest.mark.asyncio
async def test_favorite_nonexistent_event(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post("/events/9999/favorites", json={"user_id": 1})
    assert resp.status_code == 404
