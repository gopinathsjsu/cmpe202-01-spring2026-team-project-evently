import logging
import re
from collections.abc import Mapping
from functools import lru_cache
from os import getenv
from typing import Annotated, Any, Protocol, TypeGuard, cast
from urllib.parse import urlsplit, urlunsplit

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from starlette.config import Config
from starlette.datastructures import URL
from starlette.requests import Request
from starlette.responses import RedirectResponse

from backend.app_config import get_frontend_settings
from backend.db import get_db
from backend.models.user import GlobalRole, User

CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"

OAUTH_NOT_CONFIGURED = "Google OAuth is not configured"
OAUTH_INVALID_IDENTITY = "Google account is missing required verified identity claims"
USERNAME_SANITIZER = re.compile(r"[^a-z0-9_]+")

_OAUTH_USER_SESSION_KEY = "user"
_EVENTLY_USER_SESSION_KEY = "evently_user_id"
_POST_AUTH_REDIRECT_KEY = "post_auth_redirect"

DbDep = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]

router = APIRouter()


class AuthSessionUser(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    name: str
    roles: list[str]
    picture: str | None = None


class AuthSessionResponse(BaseModel):
    user: AuthSessionUser | None


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


def _bool_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _normalized_email(value: str) -> str:
    return value.strip().strip("\"'").lower()


def _oauth_subject(userinfo: Mapping[str, object]) -> str | None:
    return _string_value(userinfo.get("sub"))


def _verified_oauth_email(userinfo: Mapping[str, object]) -> str | None:
    email = _oauth_email(userinfo)
    if email is None:
        return None
    if _bool_value(userinfo.get("email_verified")) is not True:
        return None
    return email


def _configured_admin_emails() -> set[str]:
    raw_value = getenv("ADMIN_EMAILS", "")
    if not raw_value:
        return set()

    return {
        normalized
        for part in re.split(r"[\s,;]+", raw_value)
        if (normalized := _normalized_email(part))
    }


def _roles_for_email(email: str) -> set[GlobalRole]:
    roles = {GlobalRole.User}
    if _normalized_email(email) in _configured_admin_emails():
        roles.add(GlobalRole.Admin)
    return roles


def _serialized_roles(roles: set[GlobalRole]) -> list[str]:
    return [role.value for role in sorted(roles, key=lambda role: role.value)]


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


def _oauth_profile_updates(
    userinfo: Mapping[str, object], user: User
) -> dict[str, object]:
    first_name, last_name = _derive_names(userinfo, user.email)
    profile_photo_url = _string_value(userinfo.get("picture"))
    normalized_email = _verified_oauth_email(userinfo)

    updates: dict[str, object] = {}
    if first_name and first_name != user.first_name:
        updates["first_name"] = first_name
    if last_name != user.last_name:
        updates["last_name"] = last_name
    if normalized_email and normalized_email != _normalized_email(str(user.email)):
        updates["email"] = normalized_email
    if profile_photo_url and profile_photo_url != user.profile_photo_url:
        updates["profile_photo_url"] = profile_photo_url

    return updates


def _oauth_email(userinfo: Mapping[str, object]) -> str | None:
    email = _string_value(userinfo.get("email"))
    if email is None:
        return None
    return _normalized_email(email)


async def _next_user_id(db: AsyncDatabase[dict[str, Any]]) -> int:
    if await db["users"].count_documents({}, limit=1) == 0:
        await db["counters"].delete_one({"_id": "users"})

    counter = await db["counters"].find_one_and_update(
        {"_id": "users"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if counter is None:
        raise HTTPException(status_code=500, detail="Failed to allocate user ID")
    return int(counter["seq"])


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
    subject = _oauth_subject(userinfo)
    normalized_email = _verified_oauth_email(userinfo)
    if subject is None or normalized_email is None:
        return None

    existing = await db["users"].find_one({"google_sub": subject})
    if existing is not None:
        user = await _sync_user_roles(db, User(**existing))
        updates = _oauth_profile_updates(userinfo, user)
        if updates:
            if updated_email := updates.get("email"):
                email_owner = await db["users"].find_one({"email": updated_email})
                if email_owner is not None and email_owner.get("id") != user.id:
                    raise HTTPException(
                        status_code=409, detail="Google account email is already in use"
                    )
            await db["users"].update_one({"id": user.id}, {"$set": updates})
            user = user.model_copy(update=updates)
        return user

    existing = await db["users"].find_one({"email": normalized_email})
    if existing is not None:
        if (
            existing_google_sub := _string_value(existing.get("google_sub"))
        ) is not None and existing_google_sub != subject:
            raise HTTPException(
                status_code=409, detail="Google account is already linked elsewhere"
            )

        user = await _sync_user_roles(db, User(**existing))
        updates = _oauth_profile_updates(userinfo, user)
        if user.google_sub != subject:
            updates["google_sub"] = subject
        if updates:
            await db["users"].update_one({"id": user.id}, {"$set": updates})
            user = user.model_copy(update=updates)
        return user

    first_name, last_name = _derive_names(userinfo, normalized_email)
    username = await _unique_username(db, _base_username(userinfo, normalized_email))
    user = User(
        id=await _next_user_id(db),
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=normalized_email,
        google_sub=subject,
        roles=_roles_for_email(normalized_email),
        profile_photo_url=_string_value(userinfo.get("picture")),
    )
    await db["users"].insert_one(
        {
            **user.model_dump(mode="json"),
            "roles": _serialized_roles(user.roles),
        }
    )
    return user


async def _sync_user_roles(db: AsyncDatabase[dict[str, Any]], user: User) -> User:
    expected_roles = _roles_for_email(user.email)
    if user.roles == expected_roles:
        return user

    await db["users"].update_one(
        {"id": user.id},
        {"$set": {"roles": _serialized_roles(expected_roles)}},
    )
    return user.model_copy(update={"roles": expected_roles})


async def _get_authenticated_user(
    db: AsyncDatabase[dict[str, Any]], request: Request
) -> AuthSessionUser | None:
    oauth_user = request.session.get(_OAUTH_USER_SESSION_KEY)
    oauth_identity: tuple[str, str] | None = None
    if (
        is_google_userinfo(oauth_user)
        and (oauth_subject := _oauth_subject(oauth_user))
        and (oauth_email := _verified_oauth_email(oauth_user))
    ):
        oauth_identity = (oauth_subject, oauth_email)

    local_user_id = request.session.get(_EVENTLY_USER_SESSION_KEY)
    if isinstance(local_user_id, int):
        existing = await db["users"].find_one({"id": local_user_id})
        if existing is not None:
            user = await _sync_user_roles(db, User(**existing))
            if oauth_identity is None:
                if is_google_userinfo(oauth_user):
                    request.session.pop(_OAUTH_USER_SESSION_KEY, None)
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
                    roles=_serialized_roles(user.roles),
                    picture=picture or user.profile_photo_url,
                )

            oauth_subject, oauth_email = oauth_identity
            if user.google_sub == oauth_subject:
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
                    roles=_serialized_roles(user.roles),
                    picture=picture or user.profile_photo_url,
                )

            if user.google_sub is None and oauth_email == _normalized_email(
                str(user.email)
            ):
                await db["users"].update_one(
                    {"id": user.id}, {"$set": {"google_sub": oauth_subject}}
                )
                user = user.model_copy(update={"google_sub": oauth_subject})
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
                    roles=_serialized_roles(user.roles),
                    picture=picture or user.profile_photo_url,
                )

        request.session.pop(_EVENTLY_USER_SESSION_KEY, None)

    if not is_google_userinfo(oauth_user):
        return None

    local_user = await _resolve_or_create_local_user(db, oauth_user)
    if local_user is None:
        request.session.pop(_OAUTH_USER_SESSION_KEY, None)
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
        roles=_serialized_roles(local_user.roles),
        picture=_string_value(oauth_user.get("picture"))
        or local_user.profile_photo_url,
    )


async def require_authenticated_user(db: DbDep, request: Request) -> AuthSessionUser:
    if (user := await _get_authenticated_user(db, request)) is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


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

    if not ((user := token.get("userinfo")) and is_google_userinfo(user)):
        raise HTTPException(status_code=400, detail="OAuth authentication failed")

    if _oauth_subject(user) is None or _verified_oauth_email(user) is None:
        raise HTTPException(status_code=400, detail=OAUTH_INVALID_IDENTITY)

    local_user = await _resolve_or_create_local_user(db, user)
    if local_user is None:
        raise HTTPException(status_code=400, detail=OAUTH_INVALID_IDENTITY)

    request.session[_OAUTH_USER_SESSION_KEY] = dict(user)
    request.session[_EVENTLY_USER_SESSION_KEY] = local_user.id

    redirect_to = request.session.pop(_POST_AUTH_REDIRECT_KEY, "/")
    return RedirectResponse(url=redirect_to)


@router.get("/signin")
@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Initiate the OAuth login flow by redirecting to Google's authorization endpoint."""
    google_client = get_google_client()
    request.session.pop(_OAUTH_USER_SESSION_KEY, None)
    request.session.pop(_EVENTLY_USER_SESSION_KEY, None)
    request.session[_POST_AUTH_REDIRECT_KEY] = _resolve_redirect_target(request)
    redir = await google_client.authorize_redirect(
        request, str(request.url_for("auth"))
    )
    if not isinstance(redir, RedirectResponse):
        raise HTTPException(
            status_code=500, detail="Failed to create redirect response"
        )
    return redir


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Log the user out by clearing the session and redirecting to the homepage."""
    request.session.pop(_OAUTH_USER_SESSION_KEY, None)
    request.session.pop(_EVENTLY_USER_SESSION_KEY, None)
    request.session.pop(_POST_AUTH_REDIRECT_KEY, None)
    return RedirectResponse(url=_resolve_redirect_target(request))


@router.get("/session", response_model=AuthSessionResponse)
async def read_auth_session(db: DbDep, request: Request) -> AuthSessionResponse:
    """Return the current authentication session, including user information if authenticated."""
    return AuthSessionResponse(user=await _get_authenticated_user(db, request))
