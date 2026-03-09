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
    for coll in ("users", "events", "attendance"):
        await db[coll].delete_many({})


@pytest.mark.asyncio
async def test_get_user_detail(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["username"] == "testuser"
    assert body["first_name"] == "Test"
    assert body["last_name"] == "User"
    assert body["email"] == "testuser@example.com"
    assert body["phone_number"] == "+1234567890"
    assert body["roles"] == ["user"]
    assert body["profile"]["bio"] == "Test bio"
    assert body["profile"]["location"] == "San Francisco"
    assert body["profile"]["twitter_handle"] == "testuser"
    assert body["events_created_count"] == 0
    assert body["events_attended_count"] == 0


@pytest.mark.asyncio
async def test_get_user_not_found(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/9999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


@pytest.mark.asyncio
async def test_get_user_with_events_created(
    db: AsyncDatabase[dict[str, Any]],
    user_data: dict[str, Any],
    event_data: dict[str, Any],
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)
    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "organizer_user_id": 1},
            {**event_data, "id": 2, "organizer_user_id": 1},
            {**event_data, "id": 3, "organizer_user_id": 2},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1")

    body = resp.json()
    assert body["events_created_count"] == 2


@pytest.mark.asyncio
async def test_get_user_with_events_attended(
    db: AsyncDatabase[dict[str, Any]],
    user_data: dict[str, Any],
    event_data: dict[str, Any],
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)
    await db["events"].insert_one({**event_data, "id": 1})
    await db["attendance"].insert_many(
        [
            {"event_id": 1, "user_id": 1, "status": "going", "checked_in_at": None},
            {"event_id": 1, "user_id": 1, "status": "maybe", "checked_in_at": None},
            {"event_id": 1, "user_id": 1, "status": "cancelled", "checked_in_at": None},
            {"event_id": 1, "user_id": 2, "status": "going", "checked_in_at": None},
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1")

    body = resp.json()
    assert body["events_attended_count"] == 2


@pytest.mark.asyncio
async def test_get_user_with_profile_social_handles(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    await db["users"].insert_one(
        {
            "id": 1,
            "username": "socialuser",
            "first_name": "Social",
            "last_name": "User",
            "email": "social@example.com",
            "phone_number": None,
            "roles": ["user"],
            "profile": {
                "bio": "Social media enthusiast",
                "location": "New York",
                "website": "https://social.example.com",
                "twitter_handle": "socialuser",
                "instagram_handle": "socialinsta",
                "facebook_handle": "socialfb",
                "linkedin_handle": "sociallinkedin",
                "interests": ["photography", "travel"],
            },
        }
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1")

    body = resp.json()
    assert body["profile"]["instagram_handle"] == "socialinsta"
    assert body["profile"]["facebook_handle"] == "socialfb"
    assert body["profile"]["linkedin_handle"] == "sociallinkedin"
    assert body["profile"]["interests"] == ["photography", "travel"]


@pytest.mark.asyncio
async def test_get_user_with_admin_role(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    await db["users"].insert_one(
        {
            "id": 1,
            "username": "admin",
            "first_name": "Admin",
            "last_name": "User",
            "email": "admin@example.com",
            "phone_number": None,
            "roles": ["user", "admin"],
            "profile": {
                "bio": None,
                "location": None,
                "website": None,
                "twitter_handle": None,
                "instagram_handle": None,
                "facebook_handle": None,
                "linkedin_handle": None,
                "interests": [],
            },
        }
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1")

    body = resp.json()
    assert "admin" in body["roles"]


@pytest.mark.asyncio
async def test_get_user_minimal_profile(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    await db["users"].insert_one(
        {
            "id": 1,
            "username": "minimal",
            "first_name": "Min",
            "last_name": "Mal",
            "email": "minimal@example.com",
            "phone_number": None,
            "roles": ["user"],
            "profile": {
                "bio": None,
                "location": None,
                "website": None,
                "twitter_handle": None,
                "instagram_handle": None,
                "facebook_handle": None,
                "linkedin_handle": None,
                "interests": [],
            },
        }
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1")

    body = resp.json()
    assert body["profile"]["bio"] is None
    assert body["profile"]["website"] is None
    assert body["profile"]["interests"] == []
