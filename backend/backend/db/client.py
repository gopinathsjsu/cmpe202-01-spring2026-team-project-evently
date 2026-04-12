from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.mongo_client import AsyncMongoClient


def get_mongo_client(url: str | None = None) -> AsyncMongoClient[dict[str, Any]]:
    """Returns an AsyncMongoClient instance.

    Falls back to the DATABASE_URL environment variable if no url is provided.
    """
    connection_url = url or os.getenv("DATABASE_URL", "")
    if not connection_url:
        raise ValueError("No database URL provided and DATABASE_URL env var is not set")
    return AsyncMongoClient(connection_url)


@asynccontextmanager
async def get_database(
    url: str | None = None,
    db_name: str = "evently",
) -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    """Async context manager that yields a MongoDB database handle.

    Falls back to the DATABASE_URL environment variable if no url is provided.
    """
    mongo_client = get_mongo_client(url)

    async with mongo_client as client:
        yield client[db_name]
