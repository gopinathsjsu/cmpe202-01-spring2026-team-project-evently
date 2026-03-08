from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.events import router as events_router


def create_app() -> FastAPI:
    app = FastAPI(title="Evently API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(events_router, prefix="/events", tags=["events"])
    return app


app = create_app()
