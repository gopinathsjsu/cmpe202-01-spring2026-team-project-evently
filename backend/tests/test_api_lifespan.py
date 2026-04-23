from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI

import backend.api as api_module


class _FakeMongoClient:
    def __init__(self) -> None:
        self.closed = False
        self.databases: dict[str, dict[str, str]] = {}

    def __getitem__(self, name: str) -> dict[str, str]:
        database = {"name": name}
        self.databases[name] = database
        return database

    async def close(self) -> None:
        self.closed = True


class _FakeArq:
    def __init__(self) -> None:
        self.closed = False
        self.schedule_all_upcoming_event_reminders = AsyncMock()

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_lifespan_wires_database_arq_and_email_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    mongo_client = _FakeMongoClient()
    arq = _FakeArq()
    email_service = object()

    get_mongo_client = Mock(return_value=mongo_client)
    ensure_required_startup_users = AsyncMock()
    create_arq_client = AsyncMock(return_value=arq)
    create_email_notification_service = Mock(return_value=email_service)

    monkeypatch.setattr(api_module, "get_mongo_client", get_mongo_client)
    monkeypatch.setattr(
        api_module,
        "ensure_required_startup_users",
        ensure_required_startup_users,
    )
    monkeypatch.setattr(api_module, "create_arq_client", create_arq_client)
    monkeypatch.setattr(
        api_module,
        "create_email_notification_service",
        create_email_notification_service,
    )

    async with api_module.lifespan(app):
        assert app.state.db_client is mongo_client
        assert app.state.db is mongo_client.databases["evently"]
        assert app.state.arq is arq
        assert app.state.email_notification_service is email_service
        assert mongo_client.closed is False
        assert arq.closed is False

    get_mongo_client.assert_called_once_with()
    ensure_required_startup_users.assert_awaited_once_with(app.state.db)
    create_arq_client.assert_awaited_once_with()
    create_email_notification_service.assert_called_once_with(allow_missing=True)
    arq.schedule_all_upcoming_event_reminders.assert_awaited_once_with(app.state.db)
    assert mongo_client.closed is True
    assert arq.closed is True


@pytest.mark.asyncio
async def test_lifespan_closes_started_resources_when_startup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    mongo_client = _FakeMongoClient()
    arq = _FakeArq()
    email_service = object()

    get_mongo_client = Mock(return_value=mongo_client)
    ensure_required_startup_users = AsyncMock()
    create_arq_client = AsyncMock(return_value=arq)
    create_email_notification_service = Mock(return_value=email_service)
    arq.schedule_all_upcoming_event_reminders.side_effect = RuntimeError(
        "scheduler failed"
    )

    monkeypatch.setattr(api_module, "get_mongo_client", get_mongo_client)
    monkeypatch.setattr(
        api_module,
        "ensure_required_startup_users",
        ensure_required_startup_users,
    )
    monkeypatch.setattr(api_module, "create_arq_client", create_arq_client)
    monkeypatch.setattr(
        api_module,
        "create_email_notification_service",
        create_email_notification_service,
    )

    with pytest.raises(RuntimeError, match="scheduler failed"):
        async with api_module.lifespan(app):
            pass

    create_email_notification_service.assert_called_once_with(allow_missing=True)
    assert mongo_client.closed is True
    assert arq.closed is True


@pytest.mark.asyncio
async def test_lifespan_starts_without_arq_when_redis_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    mongo_client = _FakeMongoClient()
    email_service = object()

    get_mongo_client = Mock(return_value=mongo_client)
    ensure_required_startup_users = AsyncMock()
    create_arq_client = AsyncMock(side_effect=ConnectionError("no redis"))
    create_email_notification_service = Mock(return_value=email_service)

    monkeypatch.setattr(api_module, "get_mongo_client", get_mongo_client)
    monkeypatch.setattr(
        api_module,
        "ensure_required_startup_users",
        ensure_required_startup_users,
    )
    monkeypatch.setattr(api_module, "create_arq_client", create_arq_client)
    monkeypatch.setattr(
        api_module,
        "create_email_notification_service",
        create_email_notification_service,
    )

    async with api_module.lifespan(app):
        assert app.state.arq is None
        assert app.state.email_notification_service is email_service

    create_arq_client.assert_awaited_once_with()
    create_email_notification_service.assert_called_once_with(allow_missing=True)
    assert mongo_client.closed is True
