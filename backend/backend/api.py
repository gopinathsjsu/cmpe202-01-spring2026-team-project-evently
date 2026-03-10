import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo.asynchronous.mongo_client import AsyncMongoClient

from backend.routes.contact import router as contact_router
from backend.routes.events import router as events_router
from backend.routes.users import UPLOAD_DIR
from backend.routes.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise ValueError("DATABASE_URL environment variable is not set")
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(url)
    app.state.db_client = client
    app.state.db = client["evently"]
    yield
    await client.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Evently API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(events_router, prefix="/events", tags=["events"])
    app.include_router(users_router, prefix="/users", tags=["users"])
    app.include_router(contact_router, prefix="/contact", tags=["contact"])

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    return app


app = create_app()
