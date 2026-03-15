import logging
from collections.abc import Mapping
from functools import lru_cache
from os import getenv
from typing import Protocol, TypeGuard, cast

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException
from starlette.config import Config
from starlette.datastructures import URL
from starlette.requests import Request
from starlette.responses import RedirectResponse

router = APIRouter()

CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"
OAUTH_NOT_CONFIGURED = "Google OAuth is not configured"


class GoogleOAuthClientProtocol(Protocol):
    async def authorize_access_token(
        self, request: Request, **kwargs: object
    ) -> Mapping[str, object]: ...

    async def authorize_redirect(
        self,
        request: Request,
        redirect_uri: str | URL | None = None,
        **kwargs: object,
    ) -> object: ...


class GoogleOAuthClientAdapter:
    def __init__(self, client: object) -> None:
        self._client = cast(GoogleOAuthClientProtocol, client)

    async def authorize_access_token(self, request: Request) -> Mapping[str, object]:
        return await self._client.authorize_access_token(request)

    async def authorize_redirect(
        self, request: Request, redirect_uri: str | URL
    ) -> object:
        return await self._client.authorize_redirect(request, redirect_uri)


def is_google_userinfo(value: object) -> TypeGuard[Mapping[str, object]]:
    return isinstance(value, Mapping) and all(isinstance(key, str) for key in value)


@lru_cache(maxsize=1)
def get_oauth() -> OAuth:
    client_id = getenv("OAUTH_CLIENT_ID")
    client_secret = getenv("OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set")

    oauth = OAuth(
        Config(
            environ={
                "GOOGLE_CLIENT_ID": client_id,
                "GOOGLE_CLIENT_SECRET": client_secret,
            }
        )
    )
    oauth.register(
        name="google",
        server_metadata_url=CONF_URL,
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth


def get_google_client() -> GoogleOAuthClientAdapter:
    try:
        google_client: object | None = get_oauth().create_client("google")  # type: ignore[no-untyped-call]
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=OAUTH_NOT_CONFIGURED) from e

    if google_client is None:
        raise HTTPException(status_code=500, detail="Failed to create OAuth client")

    return GoogleOAuthClientAdapter(google_client)


@router.get("/callback")
async def auth(request: Request) -> RedirectResponse:
    """Handle the OAuth callback from Google."""
    google_client = get_google_client()
    try:
        token = await google_client.authorize_access_token(request)
    except OAuthError as e:
        logging.getLogger(__name__).error("OAuth error: %s", e)
        raise HTTPException(
            status_code=400, detail="OAuth authentication failed"
        ) from e

    if (user := token.get("userinfo")) and is_google_userinfo(user):
        request.session["user"] = dict(user)

    return RedirectResponse(url="/")


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Initiate the OAuth login flow by redirecting to Google's authorization endpoint."""
    google_client = get_google_client()
    redir = await google_client.authorize_redirect(request, request.url_for("auth"))
    if not isinstance(redir, RedirectResponse):
        raise HTTPException(
            status_code=500, detail="Failed to create redirect response"
        )
    return redir


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Log the user out by clearing the session and redirecting to the homepage."""
    request.session.pop("user", None)
    return RedirectResponse(url="/")
