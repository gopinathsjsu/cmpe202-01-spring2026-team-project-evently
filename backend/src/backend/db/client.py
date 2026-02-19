from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.mongo_client import AsyncMongoClient


@asynccontextmanager
async def get_database(
    url: str | None = None,
    db_name: str = "evently",
) -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    """Async context manager that yields a MongoDB database handle.

    Falls back to the DATABASE_URL environment variable if no url is provided.
    """
    connection_url = url or os.getenv("DATABASE_URL", "")
    if not connection_url:
        raise ValueError("No database URL provided and DATABASE_URL env var is not set")
    client: AsyncMongoClient[dict[str, Any]]
    async with AsyncMongoClient(connection_url) as client:
        yield client[db_name]
