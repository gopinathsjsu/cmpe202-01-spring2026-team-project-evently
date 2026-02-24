import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from pymongo.asynchronous.database import AsyncDatabase

from backend.db import get_database


@pytest_asyncio.fixture
async def db() -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    """Yield a handle to the ``evently_test`` database.

    Skips the test when DATABASE_URL is not set so the suite can still
    run in environments without a live MongoDB instance.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL is not set; skipping database tests")

    async with get_database(url, db_name="evently_test") as database:
        yield database
