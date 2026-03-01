from fastapi import FastAPI

from backend.routes.events import router as events_router


def create_app() -> FastAPI:
    app = FastAPI(title="Evently API")
    app.include_router(events_router, prefix="/events", tags=["events"])
    return app


app = create_app()
