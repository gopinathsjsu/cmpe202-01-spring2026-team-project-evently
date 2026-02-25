from collections.abc import AsyncIterator
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from .client import get_database


async def get_db() -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    """FastAPI dependency that yields a MongoDB database handle."""
    async with get_database() as database:
        yield database
