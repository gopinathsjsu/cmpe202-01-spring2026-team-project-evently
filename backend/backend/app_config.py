from dataclasses import dataclass
from os import getenv
from urllib.parse import urlsplit

from fastapi import FastAPI

DEFAULT_FRONTEND_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


@dataclass(frozen=True)
class FrontendSettings:
    allowed_origins: tuple[str, ...]
    primary_origin: str | None = None


def _normalized_origin(url: str | None) -> str | None:
    if not url:
        return None

    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        return None

    return f"{parts.scheme}://{parts.netloc}"


def build_frontend_settings(frontend_url: str | None) -> FrontendSettings:
    primary_origin = _normalized_origin(frontend_url)
    allowed_origins = list(DEFAULT_FRONTEND_ORIGINS)
    if primary_origin and primary_origin not in allowed_origins:
        allowed_origins.append(primary_origin)

    return FrontendSettings(
        allowed_origins=tuple(allowed_origins),
        primary_origin=primary_origin,
    )


def get_frontend_settings(app: FastAPI) -> FrontendSettings:
    settings = getattr(app.state, "frontend_settings", None)
    if isinstance(settings, FrontendSettings):
        return settings
    return build_frontend_settings(getenv("FRONTEND_URL"))
