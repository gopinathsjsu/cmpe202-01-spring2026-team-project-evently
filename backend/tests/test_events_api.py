from datetime import datetime
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo.asynchronous.database import AsyncDatabase

from backend.api import create_app
from backend.routes.events import _get_db


def _make_client(
    db: AsyncDatabase[dict[str, Any]],
) -> tuple[Any, AsyncClient]:
    """Build an app with the DB dependency overridden and return both."""
    app = create_app()
    app.dependency_overrides[_get_db] = lambda: db
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return app, client


@pytest.mark.asyncio
async def test_list_events_basic(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]
    await collection.delete_many({})
    await collection.insert_one(event_data)

    _, client = _make_client(db)
    async with client:
        response = await client.get("/events/")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == event_data["title"]
    assert body["items"][0]["category"] == event_data["category"]


@pytest.mark.asyncio
async def test_search_events_by_query(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]
    await collection.delete_many({})

    await collection.insert_many([
        {**event_data, "id": 1, "title": "Summer Music Festival"},
        {**event_data, "id": 2, "title": "Tech Conference"},
    ])

    _, client = _make_client(db)
    async with client:
        response = await client.get("/events/", params={"q": "summer"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Summer Music Festival"


@pytest.mark.asyncio
async def test_search_events_by_about(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]
    await collection.delete_many({})

    await collection.insert_many([
        {**event_data, "id": 1, "about": "A wonderful jazz evening"},
        {**event_data, "id": 2, "about": "Boring meeting"},
    ])

    _, client = _make_client(db)
    async with client:
        response = await client.get("/events/", params={"q": "jazz"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["about"] == "A wonderful jazz evening"


@pytest.mark.asyncio
async def test_filter_events_by_category(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]
    await collection.delete_many({})

    await collection.insert_many([
        {**event_data, "id": 1, "category": "Music"},
        {**event_data, "id": 2, "category": "Sports"},
    ])

    _, client = _make_client(db)
    async with client:
        response = await client.get("/events/", params={"category": "Music"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "Music"


@pytest.mark.asyncio
async def test_filter_events_by_date_range(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]
    await collection.delete_many({})

    early = {
        **event_data,
        "id": 1,
        "title": "Early Event",
        "start_time": datetime(2026, 3, 1, 10, 0),
        "end_time": datetime(2026, 3, 1, 12, 0),
    }
    late = {
        **event_data,
        "id": 2,
        "title": "Late Event",
        "start_time": datetime(2026, 9, 1, 10, 0),
        "end_time": datetime(2026, 9, 1, 12, 0),
    }
    await collection.insert_many([early, late])

    _, client = _make_client(db)
    async with client:
        response = await client.get(
            "/events/",
            params={
                "start_from": "2026-06-01T00:00:00",
                "start_to": "2026-12-31T23:59:59",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Late Event"


@pytest.mark.asyncio
async def test_sort_events_by_price_desc(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]
    await collection.delete_many({})

    await collection.insert_many([
        {**event_data, "id": 1, "title": "Cheap Event", "price": 10.0},
        {**event_data, "id": 2, "title": "Expensive Event", "price": 100.0},
    ])

    _, client = _make_client(db)
    async with client:
        response = await client.get(
            "/events/", params={"sort_by": "price", "sort_order": "desc"}
        )

    assert response.status_code == 200
    body = response.json()
    titles = [item["title"] for item in body["items"]]
    assert titles == ["Expensive Event", "Cheap Event"]


@pytest.mark.asyncio
async def test_sort_events_by_title_asc(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]
    await collection.delete_many({})

    await collection.insert_many([
        {**event_data, "id": 1, "title": "Zebra Party"},
        {**event_data, "id": 2, "title": "Alpha Gathering"},
    ])

    _, client = _make_client(db)
    async with client:
        response = await client.get(
            "/events/", params={"sort_by": "title", "sort_order": "asc"}
        )

    assert response.status_code == 200
    body = response.json()
    titles = [item["title"] for item in body["items"]]
    assert titles == ["Alpha Gathering", "Zebra Party"]


@pytest.mark.asyncio
async def test_paginate_events(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]
    await collection.delete_many({})

    base_start = datetime(2026, 1, 1, 10, 0, 0)
    base_end = datetime(2026, 1, 1, 12, 0, 0)

    documents = [
        {
            **event_data,
            "id": i,
            "title": f"Event {i:02d}",
            "start_time": base_start,
            "end_time": base_end,
        }
        for i in range(1, 21)
    ]
    await collection.insert_many(documents)

    _, client = _make_client(db)
    async with client:
        response = await client.get(
            "/events/",
            params={"page": 2, "page_size": 5, "sort_by": "title", "sort_order": "asc"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 20
    assert body["page"] == 2
    assert body["page_size"] == 5
    assert len(body["items"]) == 5
    assert body["items"][0]["title"] == "Event 06"


@pytest.mark.asyncio
async def test_empty_collection_returns_no_items(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    collection = db["events"]
    await collection.delete_many({})

    _, client = _make_client(db)
    async with client:
        response = await client.get("/events/")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


@pytest.mark.asyncio
async def test_invalid_page_returns_422(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    _, client = _make_client(db)
    async with client:
        response = await client.get("/events/", params={"page": 0})

    assert response.status_code == 422
