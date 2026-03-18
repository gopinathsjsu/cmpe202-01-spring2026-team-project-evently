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


def _sanitize_redirect_target(candidate: str | None, request: Request) -> str | None:
    if not candidate:
        return None

    parts = urlsplit(candidate)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None

    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in get_frontend_settings(request.app).allowed_origins:
        return None

    return urlunsplit(parts)


def _resolve_redirect_target(request: Request) -> str:
    if next_target := _sanitize_redirect_target(
        request.query_params.get("next"), request
    ):
        return next_target

    if referer := _sanitize_redirect_target(request.headers.get("referer"), request):
        return referer

    if frontend_origin := get_frontend_settings(request.app).primary_origin:
        return frontend_origin

    return "/"


def _string_value(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _derive_names(userinfo: Mapping[str, object], email: str) -> tuple[str, str]:
    first_name = _string_value(userinfo.get("given_name"))
    last_name = _string_value(userinfo.get("family_name"))
    if first_name:
        return first_name, last_name or ""

    full_name = _string_value(userinfo.get("name"))
    if full_name:
        parts = full_name.split(maxsplit=1)
        return parts[0], parts[1] if len(parts) > 1 else ""

    return email.split("@", maxsplit=1)[0], ""


def _base_username(userinfo: Mapping[str, object], email: str) -> str:
    candidate = (
        _string_value(userinfo.get("preferred_username"))
        or email.split("@", maxsplit=1)[0]
    )
    sanitized = USERNAME_SANITIZER.sub("", candidate.lower().replace("-", "_"))
    return sanitized or "evently_user"


async def _next_user_id(db: AsyncDatabase[dict[str, Any]]) -> int:
    last = await db["users"].find_one(sort=[("id", DESCENDING)])
    return int(last["id"]) + 1 if last else 1


async def _unique_username(
    db: AsyncDatabase[dict[str, Any]], base_username: str
) -> str:
    username = base_username
    suffix = 1
    while await db["users"].find_one({"username": username}, {"_id": 1}) is not None:
        suffix += 1
        username = f"{base_username}{suffix}"
    return username


async def _resolve_or_create_local_user(
    db: AsyncDatabase[dict[str, Any]], userinfo: Mapping[str, object]
) -> User | None:
    email = _string_value(userinfo.get("email"))
    if email is None:
        return None

    existing = await db["users"].find_one({"email": email})
    if existing is not None:
        return User(**existing)

    first_name, last_name = _derive_names(userinfo, email)
    username = await _unique_username(db, _base_username(userinfo, email))
    user = User(
        id=await _next_user_id(db),
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        profile_photo_url=_string_value(userinfo.get("picture")),
    )
    await db["users"].insert_one(user.model_dump(mode="json"))
    return user


async def _get_authenticated_user(
    db: AsyncDatabase[dict[str, Any]], request: Request
) -> AuthSessionUser | None:
    local_user_id = request.session.get(_EVENTLY_USER_SESSION_KEY)
    if isinstance(local_user_id, int):
        existing = await db["users"].find_one({"id": local_user_id})
        if existing is not None:
            user = User(**existing)
            oauth_user = request.session.get(_OAUTH_USER_SESSION_KEY)
            picture = None
            if is_google_userinfo(oauth_user):
                picture = _string_value(oauth_user.get("picture"))
            full_name = " ".join(
                part for part in [user.first_name, user.last_name] if part
            ).strip()
            return AuthSessionUser(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                name=full_name or user.username,
                picture=picture or user.profile_photo_url,
            )

    oauth_user = request.session.get(_OAUTH_USER_SESSION_KEY)
    if not is_google_userinfo(oauth_user):
        return None

    local_user = await _resolve_or_create_local_user(db, oauth_user)
    if local_user is None:
        return None

    request.session[_EVENTLY_USER_SESSION_KEY] = local_user.id
    full_name = " ".join(
        part for part in [local_user.first_name, local_user.last_name] if part
    ).strip()

    return AuthSessionUser(
        id=local_user.id,
        email=local_user.email,
        first_name=local_user.first_name,
        last_name=local_user.last_name,
        name=full_name or local_user.username,
        picture=_string_value(oauth_user.get("picture"))
        or local_user.profile_photo_url,
    )


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
async def auth(request: Request, db: DbDep) -> RedirectResponse:
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
        request.session[_OAUTH_USER_SESSION_KEY] = dict(user)
        if local_user := await _resolve_or_create_local_user(db, user):
            request.session[_EVENTLY_USER_SESSION_KEY] = local_user.id

    redirect_to = request.session.pop(_POST_AUTH_REDIRECT_KEY, "/")
    return RedirectResponse(url=redirect_to)


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Initiate the OAuth login flow by redirecting to Google's authorization endpoint."""
    google_client = get_google_client()
    request.session[_POST_AUTH_REDIRECT_KEY] = _resolve_redirect_target(request)
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
