from typing import Any, cast

import pytest

from backend.seed import REQUIRED_STARTUP_USERS, ensure_required_startup_users


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: list[dict[str, object]] = []

    async def find_one(
        self,
        query: dict[str, object] | None = None,
        _projection: dict[str, int] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
    ) -> dict[str, object] | None:
        if sort:
            field, direction = sort[0]
            if not self._docs:
                return None
            reverse = direction < 0
            return sorted(
                self._docs,
                key=lambda doc: cast(int, doc.get(field, 0)),
                reverse=reverse,
            )[0]

        if not query:
            return self._docs[0] if self._docs else None

        for doc in self._docs:
            if all(doc.get(key) == value for key, value in query.items()):
                return doc
        return None

    async def insert_one(self, doc: dict[str, object]) -> None:
        self._docs.append(doc)

    async def update_one(
        self,
        query: dict[str, object],
        update: dict[str, dict[str, object]],
        *,
        upsert: bool = False,
    ) -> None:
        doc = await self.find_one(query)
        if doc is None:
            if not upsert:
                return
            doc = dict(query)
            self._docs.append(doc)

        for key, value in update.get("$set", {}).items():
            doc[key] = value


class _FakeDb:
    def __init__(self) -> None:
        self._collections = {"users": _FakeCollection()}

    def __getitem__(self, name: str) -> _FakeCollection:
        return self._collections.setdefault(name, _FakeCollection())


@pytest.mark.asyncio
async def test_ensure_required_startup_users_inserts_missing_accounts() -> None:
    db = _FakeDb()

    await ensure_required_startup_users(cast(Any, db))

    for required in REQUIRED_STARTUP_USERS:
        stored = await db["users"].find_one({"email": required["email"]})
        assert stored is not None
        assert stored["username"] == required["username"]
        assert stored["first_name"] == required["first_name"]
        assert stored["last_name"] == required["last_name"]


@pytest.mark.asyncio
async def test_ensure_required_startup_users_rejects_username_collision() -> None:
    db = _FakeDb()
    await db["users"].insert_one(
        {
            "id": 99,
            "username": "lucasnguyen",
            "first_name": "Other",
            "last_name": "Person",
            "email": "other@example.com",
            "roles": ["user"],
            "profile": {},
        }
    )

    with pytest.raises(
        RuntimeError, match="Cannot safely provision required startup user"
    ):
        await ensure_required_startup_users(cast(Any, db))
