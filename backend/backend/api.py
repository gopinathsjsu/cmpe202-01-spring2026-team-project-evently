import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from os import getenv
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from starlette.middleware.sessions import SessionMiddleware

from backend.app_config import build_frontend_settings
from backend.routes.auth import router as auth_router
from backend.routes.contact import router as contact_router
from backend.routes.events import router as events_router
from backend.routes.users import UPLOAD_DIR
from backend.routes.users import router as users_router
from backend.seed import ensure_required_startup_users


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise ValueError("DATABASE_URL environment variable is not set")
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(url)
    app.state.db_client = client
    app.state.db = client["evently"]
    await ensure_required_startup_users(app.state.db)
    yield
    await client.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Evently API", lifespan=lifespan)
    app.state.frontend_settings = build_frontend_settings(getenv("FRONTEND_URL"))
    frontend_origin = app.state.frontend_settings.primary_origin or ""
    session_https_only = frontend_origin.startswith("https://")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(app.state.frontend_settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if not (session_secret_key := getenv("SESSION_SECRET_KEY")):
        raise ValueError("SESSION_SECRET_KEY environment variable is not set")
    app.add_middleware(
        middleware_class=SessionMiddleware,
        secret_key=session_secret_key,
        https_only=session_https_only,
        same_site="lax",
        session_cookie="evently_session",
    )

    app.include_router(events_router, prefix="/events", tags=["events"])
    app.include_router(users_router, prefix="/users", tags=["users"])
    app.include_router(contact_router, prefix="/contact", tags=["contact"])
    app.include_router(auth_router, prefix="/auth", tags=["auth"])

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

    return app


app = create_app()
