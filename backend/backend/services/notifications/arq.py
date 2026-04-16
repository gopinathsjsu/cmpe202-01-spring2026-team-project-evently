import os
from datetime import datetime

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import Request

# TODO: create backfill function for app startup


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
        raise RuntimeError("ArqRedis not initialized")
    return arq_client
