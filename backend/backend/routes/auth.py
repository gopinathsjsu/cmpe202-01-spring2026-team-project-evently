import logging
from os import getenv

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException
from starlette.config import Config
from starlette.requests import Request
from starlette.responses import RedirectResponse

router = APIRouter()

client_id = getenv("OAUTH_CLIENT_ID")
client_secret = getenv("OAUTH_CLIENT_SECRET")
if not client_id or not client_secret:
    raise ValueError("OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set")

oauth = OAuth(
    Config(
        environ={
            "GOOGLE_CLIENT_ID": client_id,
            "GOOGLE_CLIENT_SECRET": client_secret,
        }
    )
)

CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"

oauth.register(
    name="google",
    server_metadata_url=CONF_URL,
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/callback")
async def auth(request: Request) -> RedirectResponse:
    """Handle the OAuth callback from Google."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError as e:
        logging.getLogger(__name__).error("OAuth error: %s", e)
        raise HTTPException(
            status_code=400, detail="OAuth authentication failed"
        ) from e

    if user := token.get("userinfo"):
        request.session["user"] = dict(user)

    return RedirectResponse(url="/")


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Initiate the OAuth login flow by redirecting to Google's authorization endpoint."""
    redir = await oauth.google.authorize_redirect(request, request.url_for("auth"))
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
