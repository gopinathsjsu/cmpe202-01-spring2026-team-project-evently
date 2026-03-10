from datetime import datetime
from io import BytesIO
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
    for coll in ("users", "events", "attendance"):
        await db[coll].delete_many({})


# ---------------------------------------------------------------------------
# PATCH /users/{user_id} -- Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_user_invalid_email(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.patch("/users/1", json={"email": "not-an-email"})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_user_empty_body(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    """An empty patch body should return 200 with no changes."""
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.patch("/users/1", json={})

    assert resp.status_code == 200
    body = resp.json()
    assert body["first_name"] == "Test"
    assert body["last_name"] == "User"


@pytest.mark.asyncio
async def test_update_user_email(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.patch("/users/1", json={"email": "new@example.com"})

    assert resp.status_code == 200
    assert resp.json()["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_update_user_all_profile_fields(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    payload = {
        "bio": "Updated bio",
        "location": "New York",
        "website": "https://newsite.com",
        "twitter_handle": "@new",
        "instagram_handle": "@newinsta",
        "facebook_handle": "newfb",
        "linkedin_handle": "newli",
        "interests": ["AI", "Cooking"],
    }

    _, client = _make_client(db)
    async with client:
        resp = await client.patch("/users/1", json=payload)

    assert resp.status_code == 200
    profile = resp.json()["profile"]
    assert profile["bio"] == "Updated bio"
    assert profile["location"] == "New York"
    assert profile["website"] == "https://newsite.com"
    assert profile["twitter_handle"] == "@new"
    assert profile["instagram_handle"] == "@newinsta"
    assert profile["facebook_handle"] == "newfb"
    assert profile["linkedin_handle"] == "newli"
    assert profile["interests"] == ["AI", "Cooking"]


# ---------------------------------------------------------------------------
# POST /users/{user_id}/photo -- Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_photo_too_large(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    large_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024)
    big_file = BytesIO(large_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/users/1/photo",
            files={"file": ("big.png", big_file, "image/png")},
        )

    assert resp.status_code == 400
    assert "File too large" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_photo_invalid_extension(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    """Content-type is valid image but extension is not allowed."""
    await _clean(db)
    await db["users"].insert_one(user_data)

    fake_image = BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/users/1/photo",
            files={"file": ("evil.html", fake_image, "image/png")},
        )

    assert resp.status_code == 400
    assert "Invalid file extension" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_photo_replaces_old(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    img1 = BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    img2 = BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)

    _, client = _make_client(db)
    async with client:
        resp1 = await client.post(
            "/users/1/photo",
            files={"file": ("first.png", img1, "image/png")},
        )
        assert resp1.status_code == 200
        url1 = resp1.json()["profile_photo_url"]

        resp2 = await client.post(
            "/users/1/photo",
            files={"file": ("second.png", img2, "image/png")},
        )
        assert resp2.status_code == 200
        url2 = resp2.json()["profile_photo_url"]

    assert url1 != url2
    assert url2.startswith("/uploads/")


@pytest.mark.asyncio
async def test_upload_photo_jpeg(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    fake_jpeg = BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/users/1/photo",
            files={"file": ("photo.jpg", fake_jpeg, "image/jpeg")},
        )

    assert resp.status_code == 200
    assert resp.json()["profile_photo_url"].endswith(".jpg")


# ---------------------------------------------------------------------------
# DELETE /users/{user_id}/photo -- Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_photo_when_none_exists(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    """Deleting a photo when the user has none should still succeed (204)."""
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.delete("/users/1/photo")

    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# GET /users/{user_id}/activity -- Extended tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_activity_custom_limit(
    db: AsyncDatabase[dict[str, Any]],
    user_data: dict[str, Any],
    event_data: dict[str, Any],
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    events = [
        {**event_data, "id": i, "organizer_user_id": 1, "title": f"Event {i}"}
        for i in range(1, 6)
    ]
    await db["events"].insert_many(events)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1/activity", params={"limit": 3})

    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 3


@pytest.mark.asyncio
async def test_activity_limit_zero_rejected(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1/activity", params={"limit": 0})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_activity_limit_exceeds_max_rejected(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1/activity", params={"limit": 51})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_activity_with_registered_and_attended(
    db: AsyncDatabase[dict[str, Any]],
    user_data: dict[str, Any],
    event_data: dict[str, Any],
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)
    await db["events"].insert_many(
        [
            {
                **event_data,
                "id": 1,
                "organizer_user_id": 2,
                "title": "Registered Event",
            },
            {**event_data, "id": 2, "organizer_user_id": 2, "title": "Attended Event"},
        ]
    )
    await db["attendance"].insert_many(
        [
            {
                "event_id": 1,
                "user_id": 1,
                "status": "going",
                "checked_in_at": None,
            },
            {
                "event_id": 2,
                "user_id": 1,
                "status": "checked_in",
                "checked_in_at": datetime(2026, 6, 15, 20, 0),
            },
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1/activity")

    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    actions = {item["action"] for item in items}
    assert actions == {"registered", "attended"}


@pytest.mark.asyncio
async def test_activity_sorts_by_date_desc(
    db: AsyncDatabase[dict[str, Any]],
    user_data: dict[str, Any],
    event_data: dict[str, Any],
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)
    await db["events"].insert_many(
        [
            {
                **event_data,
                "id": 1,
                "organizer_user_id": 1,
                "title": "Old Event",
                "start_time": datetime(2026, 1, 1, 10, 0),
                "end_time": datetime(2026, 1, 1, 12, 0),
            },
            {
                **event_data,
                "id": 2,
                "organizer_user_id": 1,
                "title": "New Event",
                "start_time": datetime(2026, 12, 1, 10, 0),
                "end_time": datetime(2026, 12, 1, 12, 0),
            },
        ]
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1/activity")

    items = resp.json()["items"]
    assert items[0]["event_title"] == "New Event"
    assert items[1]["event_title"] == "Old Event"


@pytest.mark.asyncio
async def test_activity_orphaned_attendance_skipped(
    db: AsyncDatabase[dict[str, Any]],
    user_data: dict[str, Any],
) -> None:
    """Attendance records referencing a deleted event should be skipped."""
    await _clean(db)
    await db["users"].insert_one(user_data)
    await db["attendance"].insert_one(
        {
            "event_id": 9999,
            "user_id": 1,
            "status": "going",
            "checked_in_at": None,
        }
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1/activity")

    assert resp.status_code == 200
    assert resp.json()["items"] == []
