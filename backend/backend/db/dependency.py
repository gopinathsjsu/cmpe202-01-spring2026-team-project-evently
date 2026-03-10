from typing import Any

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase


def get_db(request: Request) -> AsyncDatabase[dict[str, Any]]:
    """FastAPI dependency that returns the shared MongoDB database handle."""
    db: AsyncDatabase[dict[str, Any]] | None = getattr(request.app.state, "db", None)
    if db is None:
        raise RuntimeError(
            "Database not initialized. Ensure the app lifespan has started "
            "and DATABASE_URL is set."
        )
    return db
