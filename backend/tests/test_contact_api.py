from io import BytesIO
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api import create_app
from backend.db import get_db


class _InsertOneResult:
    def __init__(self, inserted_id: str) -> None:
        self.inserted_id = inserted_id


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: list[dict[str, Any]] = []

    async def delete_many(self, _query: dict[str, Any]) -> None:
        self._docs.clear()

    async def insert_one(self, doc: dict[str, Any]) -> _InsertOneResult:
        inserted_id = str(len(self._docs) + 1)
        self._docs.append({"_id": inserted_id, **doc})
        return _InsertOneResult(inserted_id)

    async def find_one(
        self, query: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        if not query:
            return self._docs[0] if self._docs else None

        for doc in self._docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None


class _FakeDb:
    def __init__(self) -> None:
        self._collections = {"contact_submissions": _FakeCollection()}

    def __getitem__(self, name: str) -> _FakeCollection:
        return self._collections.setdefault(name, _FakeCollection())


def _make_client(db: _FakeDb) -> tuple[Any, AsyncClient]:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return app, client


async def _clean(db: _FakeDb) -> None:
    await db["contact_submissions"].delete_many({})


# ---------------------------------------------------------------------------
# POST /contact/ — Submit contact form
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_contact_success() -> None:
    db = _FakeDb()
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
async def test_submit_contact_persists_in_db() -> None:
    db = _FakeDb()
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
async def test_submit_contact_invalid_subject() -> None:
    db = _FakeDb()
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
async def test_submit_contact_invalid_email() -> None:
    db = _FakeDb()
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
async def test_submit_contact_empty_message() -> None:
    db = _FakeDb()
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
async def test_submit_contact_with_attachment() -> None:
    db = _FakeDb()
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
async def test_submit_contact_all_valid_subjects() -> None:
    db = _FakeDb()
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


@pytest.mark.asyncio
async def test_submit_contact_rate_limits_repeat_submissions() -> None:
    db = _FakeDb()
    await _clean(db)

    _, client = _make_client(db)
    async with client:
        for attempt in range(10):
            resp = await client.post(
                "/contact/",
                data={
                    "subject": "Bug Report",
                    "email": "user@example.com",
                    "message": f"Attempt {attempt}",
                },
            )
            assert resp.status_code == 201

        blocked = await client.post(
            "/contact/",
            data={
                "subject": "Bug Report",
                "email": "user@example.com",
                "message": "Blocked",
            },
        )

    assert blocked.status_code == 429
    assert "Too many contact submissions" in blocked.json()["detail"]
