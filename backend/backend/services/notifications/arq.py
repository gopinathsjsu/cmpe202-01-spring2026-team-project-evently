import os

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from fastapi import Request


def get_redis_settings(url: str | None = None) -> RedisSettings:
    """Returns Redis settings for ARQ.

    Falls back to REDIS_URL if no url is provided, then to ARQ's local
    Redis default when neither is set.
    """
    connection_url = url or os.getenv("REDIS_URL", "")
    if connection_url:
        return RedisSettings.from_dsn(connection_url)
    return RedisSettings()


async def create_arq_pool(url: str | None = None) -> ArqRedis:
    """Create an ArqRedis pool using the shared Redis settings."""
    return await create_pool(get_redis_settings(url))


def get_arq(request: Request) -> ArqRedis:
    """FastAPI dependency that returns the shared ArqRedis job queue interface."""
    arq_redis: ArqRedis | None = getattr(request.app.state, "arq", None)
    if arq_redis is None:
        raise RuntimeError("ArqRedis not initialized")
    return arq_redis
