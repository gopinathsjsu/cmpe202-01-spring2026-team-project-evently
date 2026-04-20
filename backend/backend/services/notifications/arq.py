import os
from datetime import UTC, datetime, timedelta
from typing import Any

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase

from .email import REMINDER_LEAD_TIME_MINUTES


def utc_naive_datetime(value: datetime) -> datetime:
    """Normalize datetimes to naive UTC for reminder scheduling."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


class ArqClient:
    def __init__(self, arq_redis: ArqRedis) -> None:
        self._arq_redis = arq_redis

    async def close(self) -> None:
        await self._arq_redis.aclose()

    async def schedule_event_reminder(self, event_id: int, run_at: datetime) -> None:
        """Schedule a background task to send an event reminder."""
        await self._arq_redis.enqueue_job(
            "send_event_reminder",
            event_id=event_id,
            _defer_until=run_at,
            _job_id=f"event_reminder_{event_id}",
        )

    async def schedule_all_upcoming_event_reminders(
        self, db: AsyncDatabase[dict[str, Any]]
    ) -> None:
        """Schedule background tasks for all upcoming event reminders."""
        now = datetime.now(UTC).replace(tzinfo=None)
        async for event_dict in db["events"].find({"start_time": {"$gt": now}}):
            event_id = event_dict["id"]
            start_time = utc_naive_datetime(event_dict["start_time"])
            reminder_time = start_time - timedelta(minutes=REMINDER_LEAD_TIME_MINUTES)
            if reminder_time > now:
                await self.schedule_event_reminder(event_id, reminder_time)


def get_redis_settings(url: str | None = None) -> RedisSettings:
    """Returns Redis settings for ARQ.

    Falls back to REDIS_URL if no url is provided, then to ARQ's local
    Redis default when neither is set.
    """
    connection_url = url or os.getenv("REDIS_URL", "")
    if connection_url:
        return RedisSettings.from_dsn(connection_url)
    return RedisSettings()


async def create_arq_client(url: str | None = None) -> ArqClient:
    """Create an ArqRedis pool using the shared Redis settings."""
    return ArqClient(await create_pool(get_redis_settings(url)))


def get_arq(request: Request) -> ArqClient:
    """FastAPI dependency that returns the shared ArqClient."""
    arq_client: ArqClient | None = getattr(request.app.state, "arq", None)
    if arq_client is None:
        raise RuntimeError("ArqClient not initialized")
    return arq_client
