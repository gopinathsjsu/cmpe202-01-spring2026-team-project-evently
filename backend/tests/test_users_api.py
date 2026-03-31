from datetime import datetime
from io import BytesIO
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo.asynchronous.database import AsyncDatabase

from backend.api import create_app
from backend.db import get_db
from backend.models.attendance import AttendanceStatus, EventAttendance
from backend.models.user import GlobalRole, User, UserProfile
from backend.routes.auth import AuthSessionUser, require_authenticated_user


def _role_set_to_string_list(roles: set[GlobalRole]) -> list[str]:
    return [r.value for r in roles]


def _make_client(
    db: AsyncDatabase[dict[str, Any]],
    auth_user: AuthSessionUser | None = None,
) -> tuple[Any, AsyncClient]:
    """Build an app with the DB dependency overridden."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    if auth_user is not None:
        app.dependency_overrides[require_authenticated_user] = lambda: auth_user
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return app, client


def _auth_user(user_id: int = 1) -> AuthSessionUser:
    return AuthSessionUser(
        id=user_id,
        email=f"user{user_id}@example.com",
        first_name="Test",
        last_name="User",
        name="Test User",
        roles=["user"],
    )


async def _clean(db: AsyncDatabase[dict[str, Any]]) -> None:
    for coll in ("users", "events", "attendance"):
        await db[coll].delete_many({})


# ---------------------------------------------------------------------------
# GET /users/{user_id} (existing tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_detail(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db, auth_user=_auth_user())
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

    _, client = _make_client(db, auth_user=_auth_user())
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

    _, client = _make_client(db, auth_user=_auth_user())
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

    attendances = [
        EventAttendance(event_id=1, user_id=1, status=AttendanceStatus.Going),
        EventAttendance(
            event_id=1,
            user_id=1,
            status=AttendanceStatus.CheckedIn,
            checked_in_at=datetime(2026, 6, 15, 20, 0),
        ),
        EventAttendance(event_id=1, user_id=1, status=AttendanceStatus.Cancelled),
        EventAttendance(event_id=1, user_id=2, status=AttendanceStatus.Going),
    ]
    await db["attendance"].insert_many([a.model_dump() for a in attendances])

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.get("/users/1")

    body = resp.json()
    assert body["events_attended_count"] == 1


@pytest.mark.asyncio
async def test_get_user_with_profile_social_handles(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    user = User(
        id=1,
        username="socialuser",
        first_name="Social",
        last_name="User",
        email="social@example.com",
        phone_number=None,
        roles={GlobalRole.User},
        profile=UserProfile(
            bio="Social media enthusiast",
            location="New York",
            website="https://social.example.com",
            twitter_handle="socialuser",
            instagram_handle="socialinsta",
            facebook_handle="socialfb",
            linkedin_handle="sociallinkedin",
            interests=["photography", "travel"],
        ),
    )
    doc = user.model_dump()
    doc["roles"] = _role_set_to_string_list(doc["roles"])
    await db["users"].insert_one(doc)

    _, client = _make_client(db, auth_user=_auth_user())
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
    user = User(
        id=1,
        username="admin",
        first_name="Admin",
        last_name="User",
        email="admin@example.com",
        phone_number=None,
        roles={GlobalRole.User, GlobalRole.Admin},
        profile=UserProfile(),
    )
    doc = user.model_dump()
    doc["roles"] = _role_set_to_string_list(doc["roles"])
    await db["users"].insert_one(doc)

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.get("/users/1")

    body = resp.json()
    assert "admin" in body["roles"]


@pytest.mark.asyncio
async def test_get_user_minimal_profile(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)
    user = User(
        id=1,
        username="minimal",
        first_name="Min",
        last_name="Mal",
        email="minimal@example.com",
        phone_number=None,
        roles={GlobalRole.User},
        profile=UserProfile(),
    )
    doc = user.model_dump()
    doc["roles"] = _role_set_to_string_list(doc["roles"])
    await db["users"].insert_one(doc)

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.get("/users/1")

    body = resp.json()
    assert body["profile"]["bio"] is None
    assert body["profile"]["website"] is None
    assert body["profile"]["interests"] == []


# ---------------------------------------------------------------------------
# PATCH /users/{user_id} -- Update Profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_user_profile(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.patch(
            "/users/1",
            json={
                "first_name": "Updated",
                "last_name": "Name",
                "bio": "New bio text",
                "website": "https://new-site.com",
                "twitter_handle": "@newhandle",
                "interests": ["Sports", "Music"],
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["first_name"] == "Updated"
    assert body["last_name"] == "Name"
    assert body["profile"]["bio"] == "New bio text"
    assert body["profile"]["website"] == "https://new-site.com"
    assert body["profile"]["twitter_handle"] == "@newhandle"
    assert body["profile"]["interests"] == ["Sports", "Music"]


@pytest.mark.asyncio
async def test_update_user_partial(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    """Only the supplied fields should change; others stay intact."""
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.patch("/users/1", json={"first_name": "Patched"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["first_name"] == "Patched"
    assert body["last_name"] == "User"
    assert body["email"] == "testuser@example.com"
    assert body["profile"]["bio"] == "Test bio"
    assert body["profile"]["twitter_handle"] == "testuser"


@pytest.mark.asyncio
async def test_update_user_not_found(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db, auth_user=_auth_user(9999))
    async with client:
        resp = await client.patch("/users/9999", json={"first_name": "Ghost"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "User not found"


@pytest.mark.asyncio
async def test_update_user_requires_authentication(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.patch("/users/1", json={"first_name": "Updated"})

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication required"


@pytest.mark.asyncio
async def test_update_user_forbids_modifying_other_user(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db, auth_user=_auth_user(2))
    async with client:
        resp = await client.patch("/users/1", json={"first_name": "Updated"})

    assert resp.status_code == 403
    assert resp.json()["detail"] == "You can only modify your own user."


# ---------------------------------------------------------------------------
# POST /users/{user_id}/photo -- Upload Photo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_photo(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    fake_image = BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.post(
            "/users/1/photo",
            files={"file": ("avatar.png", fake_image, "image/png")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["profile_photo_url"] is not None
    assert body["profile_photo_url"].startswith("/uploads/")
    assert body["profile_photo_url"].endswith(".png")


@pytest.mark.asyncio
async def test_upload_photo_invalid_type(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    fake_file = BytesIO(b"not an image")

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        resp = await client.post(
            "/users/1/photo",
            files={"file": ("doc.pdf", fake_file, "application/pdf")},
        )

    assert resp.status_code == 400
    assert "Invalid file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_photo_not_found(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    fake_image = BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    _, client = _make_client(db, auth_user=_auth_user(9999))
    async with client:
        resp = await client.post(
            "/users/9999/photo",
            files={"file": ("avatar.png", fake_image, "image/png")},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_photo_requires_authentication(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    fake_image = BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/users/1/photo",
            files={"file": ("avatar.png", fake_image, "image/png")},
        )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication required"


@pytest.mark.asyncio
async def test_upload_photo_forbids_modifying_other_user(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    fake_image = BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    _, client = _make_client(db, auth_user=_auth_user(2))
    async with client:
        resp = await client.post(
            "/users/1/photo",
            files={"file": ("avatar.png", fake_image, "image/png")},
        )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "You can only modify your own user."


# ---------------------------------------------------------------------------
# DELETE /users/{user_id}/photo -- Remove Photo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_photo(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    fake_image = BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    _, client = _make_client(db, auth_user=_auth_user())
    async with client:
        upload_resp = await client.post(
            "/users/1/photo",
            files={"file": ("avatar.png", fake_image, "image/png")},
        )
        assert upload_resp.status_code == 200

        delete_resp = await client.delete("/users/1/photo")
        assert delete_resp.status_code == 204

        user_resp = await client.get("/users/1")
        assert user_resp.json()["profile_photo_url"] is None


@pytest.mark.asyncio
async def test_delete_photo_not_found(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db, auth_user=_auth_user(9999))
    async with client:
        resp = await client.delete("/users/9999/photo")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_photo_requires_authentication(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.delete("/users/1/photo")

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication required"


@pytest.mark.asyncio
async def test_delete_photo_forbids_modifying_other_user(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db, auth_user=_auth_user(2))
    async with client:
        resp = await client.delete("/users/1/photo")

    assert resp.status_code == 403
    assert resp.json()["detail"] == "You can only modify your own user."


# ---------------------------------------------------------------------------
# GET /users/{user_id}/activity -- Activity Feed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_activity(
    db: AsyncDatabase[dict[str, Any]],
    user_data: dict[str, Any],
    event_data: dict[str, Any],
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    await db["events"].insert_many(
        [
            {**event_data, "id": 1, "organizer_user_id": 1, "title": "Created Event"},
            {**event_data, "id": 2, "organizer_user_id": 2, "title": "Attended Event"},
        ]
    )
    await db["attendance"].insert_one(
        {
            "event_id": 2,
            "user_id": 1,
            "status": "checked_in",
            "checked_in_at": datetime(2026, 6, 15, 20, 0),
        }
    )

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1/activity")

    assert resp.status_code == 200
    body = resp.json()
    items = body["items"]
    assert len(items) == 2

    actions = {item["action"] for item in items}
    assert "created" in actions
    assert "attended" in actions


@pytest.mark.asyncio
async def test_get_user_activity_empty(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    await _clean(db)
    await db["users"].insert_one(user_data)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/1/activity")

    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []


@pytest.mark.asyncio
async def test_get_user_activity_not_found(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.get("/users/9999/activity")
    assert resp.status_code == 404
