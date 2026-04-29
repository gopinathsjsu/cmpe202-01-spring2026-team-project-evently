import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from os import getenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app_config import build_frontend_settings
from backend.db import get_mongo_client
from backend.routes.auth import router as auth_router
from backend.routes.contact import router as contact_router
from backend.routes.events import router as events_router
from backend.routes.users import UPLOAD_DIR
from backend.routes.users import router as users_router
from backend.seed import ensure_required_startup_users
from backend.services.notifications.arq import create_arq_client
from backend.services.notifications.email import create_email_notification_service

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db_client = get_mongo_client()
    app.state.db_client = db_client
    app.state.db = db_client["evently"]
    arq = None
    try:
        await ensure_required_startup_users(app.state.db)

        try:
            arq = await create_arq_client()
            app.state.arq = arq
        except Exception:
            _logger.exception(
                "Redis/Arq is not reachable; API will run without background "
                "reminders. Set REDIS_URL (e.g. in SSM for EC2) to enable them."
            )
            app.state.arq = None

        email_notification_service = create_email_notification_service(
            allow_missing=True
        )
        app.state.email_notification_service = email_notification_service

        if arq is not None:
            await arq.schedule_all_upcoming_event_reminders(app.state.db)

        yield
    finally:
        await db_client.close()
        if arq is not None:
            await arq.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Evently API", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness for load balancers; does not check MongoDB or Redis."""
        return {"status": "ok"}

    app.state.frontend_settings = build_frontend_settings(getenv("FRONTEND_URL"))
    frontend_origin = app.state.frontend_settings.primary_origin or ""
    session_https_only = frontend_origin.startswith("https://")

    # Catch unhandled errors in middleware that sits inside CORSMiddleware, so
    # even generic 500 responses still include the frontend's CORS headers.
    @app.middleware("http")
    async def _unhandled_exception_middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            response = await call_next(request)
        except Exception:
            _logger.exception(
                "Unhandled exception on %s %s", request.method, request.url
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

        return response

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
