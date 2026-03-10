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
    await db["contact_submissions"].delete_many({})


# ---------------------------------------------------------------------------
# POST /contact/ — Submit contact form
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_contact_success(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/contact/",
            data={
                "subject": "Bug Report",
                "email": "user@example.com",
                "message": "Something is broken",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert "message" in body
    assert (
        body["message"]
        == "Your message has been received. We'll get back to you within 24 hours."
    )


@pytest.mark.asyncio
async def test_submit_contact_persists_in_db(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        await client.post(
            "/contact/",
            data={
                "subject": "General Inquiry",
                "email": "user@example.com",
                "message": "Hello, I need help",
            },
        )

    doc = await db["contact_submissions"].find_one({"email": "user@example.com"})
    assert doc is not None
    assert doc["subject"] == "General Inquiry"
    assert doc["message"] == "Hello, I need help"


@pytest.mark.asyncio
async def test_submit_contact_invalid_subject(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/contact/",
            data={
                "subject": "Invalid Subject",
                "email": "user@example.com",
                "message": "Hello",
            },
        )

    assert resp.status_code == 422
    assert "Invalid subject" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_submit_contact_invalid_email(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/contact/",
            data={
                "subject": "Bug Report",
                "email": "not-an-email",
                "message": "Hello",
            },
        )

    assert resp.status_code == 422
    assert "Invalid email" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_submit_contact_empty_message(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/contact/",
            data={
                "subject": "Bug Report",
                "email": "user@example.com",
                "message": "   ",
            },
        )

    assert resp.status_code == 422
    assert "Message cannot be empty" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_submit_contact_with_attachment(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    await _clean(db)

    fake_image = BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    _, client = _make_client(db)
    async with client:
        resp = await client.post(
            "/contact/",
            data={
                "subject": "Bug Report",
                "email": "user@example.com",
                "message": "Here is a screenshot",
            },
            files={"attachment": ("screenshot.png", fake_image, "image/png")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body

    doc = await db["contact_submissions"].find_one({"email": "user@example.com"})
    assert doc is not None
    assert doc["attachment_filename"] == "screenshot.png"


@pytest.mark.asyncio
async def test_submit_contact_all_valid_subjects(
    db: AsyncDatabase[dict[str, Any]],
) -> None:
    """All allowed subjects should be accepted."""
    await _clean(db)

    subjects = [
        "General Inquiry",
        "Ticketing Issue",
        "Payment Problem",
        "Event Creation Help",
        "Account Issue",
        "Bug Report",
        "Feature Request",
    ]

    _, client = _make_client(db)
    async with client:
        for subject in subjects:
            resp = await client.post(
                "/contact/",
                data={
                    "subject": subject,
                    "email": "user@example.com",
                    "message": f"Testing {subject}",
                },
            )
            assert resp.status_code == 201, f"Failed for subject: {subject}"
