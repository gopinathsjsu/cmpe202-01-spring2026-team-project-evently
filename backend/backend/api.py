from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI  # type: ignore[import-untyped]
from pymongo.asynchronous.database import AsyncDatabase

from backend.db import get_database
from backend.routes.events import router as events_router


async def get_db() -> AsyncIterator[AsyncDatabase[dict[str, Any]]]:
    """FastAPI dependency that yields a MongoDB database handle."""
    async with get_database() as database:
        yield database


def create_app() -> FastAPI:
    app = FastAPI(title="Evently API")
    app.include_router(events_router, prefix="/events", tags=["events"])
    return app


app = create_app()
