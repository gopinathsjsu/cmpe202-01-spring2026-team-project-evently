import logging
import re
import uuid
from collections.abc import Mapping
from functools import lru_cache
from os import getenv
from time import time
from typing import Annotated, Any, Protocol, TypeGuard, cast
from urllib.parse import urlsplit, urlunsplit

import httpx
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from starlette.config import Config
from starlette.datastructures import URL
from starlette.requests import Request
from starlette.responses import RedirectResponse

from backend.app_config import get_frontend_settings
from backend.db import get_db
from backend.models.user import GlobalRole, User, UserProfile

CONF_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
GOOGLE_OAUTH_SCOPE = f"openid email profile {GOOGLE_CALENDAR_SCOPE}"
GOOGLE_TOKEN_REFRESH_URL = "https://oauth2.googleapis.com/token"

OAUTH_NOT_CONFIGURED = "Google OAuth is not configured"
OAUTH_INVALID_IDENTITY = "Google account is missing required verified identity claims"
USERNAME_SANITIZER = re.compile(r"[^a-z0-9_]+")

_OAUTH_USER_SESSION_KEY = "user"
_OAUTH_TOKEN_SESSION_ID_KEY = "oauth_token_session_id"
_EVENTLY_USER_SESSION_KEY = "evently_user_id"
_POST_AUTH_REDIRECT_KEY = "post_auth_redirect"
_PENDING_SIGNUP_SESSION_KEY = "pending_signup"
_OAUTH_TOKEN_COLLECTION = "oauth_tokens"

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


class PendingSignupUser(BaseModel):
    email: str
    first_name: str
    last_name: str
    suggested_username: str
    picture: str | None = None


class PendingSignupResponse(BaseModel):
    pending: PendingSignupUser | None


class CompleteSignupRequest(BaseModel):
    username: str
    first_name: str | None = None
    last_name: str | None = None
    phone_number: str | None = None
    bio: str | None = None
    location: str | None = None
    website: str | None = None
    twitter_handle: str | None = None
    instagram_handle: str | None = None
    facebook_handle: str | None = None
    linkedin_handle: str | None = None
    interests: list[str] = Field(default_factory=list)


class CompleteSignupResponse(BaseModel):
    user: AuthSessionUser
    redirect_to: str


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
        self,
        request: Request,
        redirect_uri: str | URL,
        **kwargs: object,
    ) -> object:
        return await self._client.authorize_redirect(request, redirect_uri, **kwargs)


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


def _complete_signup_redirect_target(request: Request) -> str:
    frontend_origin = get_frontend_settings(request.app).primary_origin
    if frontend_origin:
        return str(URL(frontend_origin).replace(path="/complete-signup", query=""))
    return "/complete-signup"


def _string_value(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _session_token_store_id(request: Request) -> str:
    existing = request.session.get(_OAUTH_TOKEN_SESSION_ID_KEY)
    if isinstance(existing, str) and existing.strip():
        return existing
    session_id = uuid.uuid4().hex
    request.session[_OAUTH_TOKEN_SESSION_ID_KEY] = session_id
    return session_id


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


def _serialized_oauth_token(
    token: Mapping[str, object], *, previous: Mapping[str, object] | None = None
) -> dict[str, object] | None:
    access_token = _string_value(token.get("access_token"))
    if access_token is None:
        return None

    serialized: dict[str, object] = {"access_token": access_token}

    if previous is None:
        previous = {}

    if token_type := (
        _string_value(token.get("token_type"))
        or _string_value(previous.get("token_type"))
    ):
        serialized["token_type"] = token_type

    if scope := _string_value(token.get("scope")) or _string_value(
        previous.get("scope")
    ):
        serialized["scope"] = scope

    if refresh_token := _string_value(token.get("refresh_token")) or _string_value(
        previous.get("refresh_token")
    ):
        serialized["refresh_token"] = refresh_token

    expires_at = token.get("expires_at")
    if isinstance(expires_at, int | float):
        serialized["expires_at"] = int(expires_at)
    else:
        expires_in = token.get("expires_in")
        if isinstance(expires_in, int | float):
            serialized["expires_at"] = int(time()) + int(expires_in)
        elif isinstance(previous_expires_at := previous.get("expires_at"), int | float):
            serialized["expires_at"] = int(previous_expires_at)

    return serialized


def _stored_oauth_token(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    access_token = value.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        return None
    return value


def _oauth_token_has_scope(token: Mapping[str, object], required_scope: str) -> bool:
    scope = _string_value(token.get("scope"))
    if scope is None:
        return True
    return required_scope in scope.split()


def _oauth_token_needs_refresh(token: Mapping[str, object]) -> bool:
    expires_at = token.get("expires_at")
    if not isinstance(expires_at, int | float):
        return False
    return time() >= float(expires_at) - 60


async def _refresh_oauth_token(token: Mapping[str, object]) -> dict[str, object]:
    refresh_token = _string_value(token.get("refresh_token"))
    if refresh_token is None:
        raise HTTPException(
            status_code=403,
            detail="Google Calendar access has expired. Please sign in again.",
        )

    client_id = getenv("OAUTH_CLIENT_ID")
    client_secret = getenv("OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail=OAUTH_NOT_CONFIGURED)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_REFRESH_URL,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )
    except httpx.HTTPError as exc:
        logging.getLogger(__name__).error("Google token refresh failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not refresh Google Calendar access.",
        ) from exc

    if response.status_code in {400, 401}:
        raise HTTPException(
            status_code=403,
            detail="Google Calendar access has expired. Please sign in again.",
        )

    if not response.is_success:
        raise HTTPException(
            status_code=502,
            detail="Could not refresh Google Calendar access.",
        )

    payload = response.json()
    if not isinstance(payload, Mapping):
        raise HTTPException(
            status_code=502,
            detail="Could not refresh Google Calendar access.",
        )

    refreshed = _serialized_oauth_token(payload, previous=token)
    if refreshed is None:
        raise HTTPException(
            status_code=502,
            detail="Could not refresh Google Calendar access.",
        )

    return refreshed


async def _store_oauth_token(
    db: AsyncDatabase[dict[str, Any]],
    request: Request,
    token: Mapping[str, object],
    *,
    previous: Mapping[str, object] | None = None,
) -> None:
    serialized = _serialized_oauth_token(token, previous=previous)
    if serialized is None:
        await _clear_oauth_token(db, request)
        return

    session_id = _session_token_store_id(request)
    await db[_OAUTH_TOKEN_COLLECTION].update_one(
        {"_id": session_id},
        {"$set": {"token": dict(serialized)}},
        upsert=True,
    )


async def _load_oauth_token(
    db: AsyncDatabase[dict[str, Any]], request: Request
) -> Mapping[str, object] | None:
    session_id = request.session.get(_OAUTH_TOKEN_SESSION_ID_KEY)
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    stored = await db[_OAUTH_TOKEN_COLLECTION].find_one({"_id": session_id})
    if not isinstance(stored, Mapping):
        return None
    return _stored_oauth_token(stored.get("token"))


async def _clear_oauth_token(
    db: AsyncDatabase[dict[str, Any]], request: Request
) -> None:
    session_id = request.session.pop(_OAUTH_TOKEN_SESSION_ID_KEY, None)
    if isinstance(session_id, str) and session_id.strip():
        await db[_OAUTH_TOKEN_COLLECTION].delete_one({"_id": session_id})


async def get_google_calendar_access_token(request: Request) -> str:
    db = cast(AsyncDatabase[dict[str, Any]], request.app.state.db)
    stored_token = await _load_oauth_token(db, request)
    if stored_token is None:
        raise HTTPException(
            status_code=403,
            detail="Google Calendar access is not available for this session. Please sign in again.",
        )

    if not _oauth_token_has_scope(stored_token, GOOGLE_CALENDAR_SCOPE):
        raise HTTPException(
            status_code=403,
            detail="Google Calendar permission has not been granted. Please sign in again.",
        )

    if _oauth_token_needs_refresh(stored_token):
        refreshed = await _refresh_oauth_token(stored_token)
        await _store_oauth_token(db, request, refreshed, previous=stored_token)
        stored_token = refreshed

    access_token = _string_value(stored_token.get("access_token"))
    if access_token is None:
        raise HTTPException(
            status_code=403,
            detail="Google Calendar access is not available for this session. Please sign in again.",
        )

    return access_token


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


def _normalize_requested_username(value: str) -> str:
    normalized = USERNAME_SANITIZER.sub("", value.strip().lower().replace("-", "_"))
    if not normalized:
        raise HTTPException(
            status_code=400, detail="Username must contain letters or numbers"
        )
    return normalized


def _build_auth_session_user(
    user: User, *, picture: str | None = None
) -> AuthSessionUser:
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


def _pending_signup_user(userinfo: Mapping[str, object]) -> PendingSignupUser | None:
    email = _verified_oauth_email(userinfo)
    subject = _oauth_subject(userinfo)
    if email is None or subject is None:
        return None

    first_name, last_name = _derive_names(userinfo, email)
    return PendingSignupUser(
        email=email,
        first_name=first_name,
        last_name=last_name,
        suggested_username=_base_username(userinfo, email),
        picture=_string_value(userinfo.get("picture")),
    )


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


async def _resolve_existing_local_user(
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

    return None


async def _create_local_user_from_oauth(
    db: AsyncDatabase[dict[str, Any]],
    userinfo: Mapping[str, object],
    payload: CompleteSignupRequest,
) -> User:
    subject = _oauth_subject(userinfo)
    normalized_email = _verified_oauth_email(userinfo)
    if subject is None or normalized_email is None:
        raise HTTPException(status_code=400, detail=OAUTH_INVALID_IDENTITY)

    existing = await _resolve_existing_local_user(db, userinfo)
    if existing is not None:
        return existing

    username = _normalize_requested_username(payload.username)
    if await db["users"].find_one({"username": username}, {"_id": 1}) is not None:
        raise HTTPException(status_code=409, detail="Username is already in use")
    if await db["users"].find_one({"email": normalized_email}, {"_id": 1}) is not None:
        raise HTTPException(status_code=409, detail="Email is already in use")

    default_first_name, default_last_name = _derive_names(userinfo, normalized_email)
    user = User(
        id=await _next_user_id(db),
        username=username,
        first_name=(payload.first_name or default_first_name).strip(),
        last_name=(
            payload.last_name if payload.last_name is not None else default_last_name
        ).strip(),
        email=normalized_email,
        google_sub=subject,
        roles=_roles_for_email(normalized_email),
        profile_photo_url=_string_value(userinfo.get("picture")),
        phone_number=_string_value(payload.phone_number),
        profile=UserProfile(
            bio=_string_value(payload.bio),
            location=_string_value(payload.location),
            website=_string_value(payload.website),
            twitter_handle=_string_value(payload.twitter_handle),
            instagram_handle=_string_value(payload.instagram_handle),
            facebook_handle=_string_value(payload.facebook_handle),
            linkedin_handle=_string_value(payload.linkedin_handle),
            interests=[item.strip() for item in payload.interests if item.strip()],
        ),
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
                return _build_auth_session_user(user, picture=picture)

            oauth_subject, oauth_email = oauth_identity
            if user.google_sub == oauth_subject:
                picture = None
                if is_google_userinfo(oauth_user):
                    picture = _string_value(oauth_user.get("picture"))
                request.session.pop(_PENDING_SIGNUP_SESSION_KEY, None)
                return _build_auth_session_user(user, picture=picture)

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
                request.session.pop(_PENDING_SIGNUP_SESSION_KEY, None)
                return _build_auth_session_user(user, picture=picture)

        request.session.pop(_EVENTLY_USER_SESSION_KEY, None)

    if not is_google_userinfo(oauth_user):
        return None

    if request.session.get(_PENDING_SIGNUP_SESSION_KEY):
        local_user = await _resolve_existing_local_user(db, oauth_user)
        if local_user is None:
            return None
        request.session[_EVENTLY_USER_SESSION_KEY] = local_user.id
        request.session.pop(_PENDING_SIGNUP_SESSION_KEY, None)
        return _build_auth_session_user(
            local_user,
            picture=_string_value(oauth_user.get("picture")),
        )

    local_user = await _resolve_existing_local_user(db, oauth_user)
    if local_user is None:
        request.session.pop(_OAUTH_USER_SESSION_KEY, None)
        return None

    request.session[_EVENTLY_USER_SESSION_KEY] = local_user.id
    request.session.pop(_PENDING_SIGNUP_SESSION_KEY, None)
    return _build_auth_session_user(
        local_user,
        picture=_string_value(oauth_user.get("picture")),
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
        client_kwargs={"scope": GOOGLE_OAUTH_SCOPE},
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

    request.session[_OAUTH_USER_SESSION_KEY] = dict(user)
    await _store_oauth_token(db, request, token)

    local_user = await _resolve_existing_local_user(db, user)
    if local_user is None:
        request.session.pop(_EVENTLY_USER_SESSION_KEY, None)
        request.session[_PENDING_SIGNUP_SESSION_KEY] = True
        return RedirectResponse(url=_complete_signup_redirect_target(request))

    request.session.pop(_PENDING_SIGNUP_SESSION_KEY, None)
    request.session[_EVENTLY_USER_SESSION_KEY] = local_user.id
    redirect_to = request.session.pop(_POST_AUTH_REDIRECT_KEY, "/")
    return RedirectResponse(url=redirect_to)


@router.get("/signin")
@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Initiate the OAuth login flow by redirecting to Google's authorization endpoint."""
    google_client = get_google_client()
    db = cast(AsyncDatabase[dict[str, Any]], request.app.state.db)
    request.session.pop(_OAUTH_USER_SESSION_KEY, None)
    await _clear_oauth_token(db, request)
    request.session.pop(_EVENTLY_USER_SESSION_KEY, None)
    request.session.pop(_PENDING_SIGNUP_SESSION_KEY, None)
    request.session[_POST_AUTH_REDIRECT_KEY] = _resolve_redirect_target(request)
    redir = await google_client.authorize_redirect(
        request,
        str(request.url_for("auth")),
        access_type="offline",
        include_granted_scopes="true",
    )
    if not isinstance(redir, RedirectResponse):
        raise HTTPException(
            status_code=500, detail="Failed to create redirect response"
        )
    return redir


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Log the user out by clearing the session and redirecting to the homepage."""
    db = cast(AsyncDatabase[dict[str, Any]], request.app.state.db)
    request.session.pop(_OAUTH_USER_SESSION_KEY, None)
    await _clear_oauth_token(db, request)
    request.session.pop(_EVENTLY_USER_SESSION_KEY, None)
    request.session.pop(_PENDING_SIGNUP_SESSION_KEY, None)
    request.session.pop(_POST_AUTH_REDIRECT_KEY, None)
    return RedirectResponse(url=_resolve_redirect_target(request))


@router.get("/session", response_model=AuthSessionResponse)
async def read_auth_session(db: DbDep, request: Request) -> AuthSessionResponse:
    """Return the current authentication session, including user information if authenticated."""
    return AuthSessionResponse(user=await _get_authenticated_user(db, request))


@router.get("/pending-signup", response_model=PendingSignupResponse)
async def read_pending_signup(request: Request) -> PendingSignupResponse:
    oauth_user = request.session.get(_OAUTH_USER_SESSION_KEY)
    if not request.session.get(_PENDING_SIGNUP_SESSION_KEY) or not is_google_userinfo(
        oauth_user
    ):
        return PendingSignupResponse(pending=None)
    return PendingSignupResponse(pending=_pending_signup_user(oauth_user))


@router.post("/complete-signup", response_model=CompleteSignupResponse)
async def complete_signup(
    request: Request, db: DbDep, body: CompleteSignupRequest
) -> CompleteSignupResponse:
    oauth_user = request.session.get(_OAUTH_USER_SESSION_KEY)
    if not request.session.get(_PENDING_SIGNUP_SESSION_KEY) or not is_google_userinfo(
        oauth_user
    ):
        raise HTTPException(status_code=401, detail="No signup session found")

    local_user = await _create_local_user_from_oauth(db, oauth_user, body)
    request.session[_EVENTLY_USER_SESSION_KEY] = local_user.id
    request.session.pop(_PENDING_SIGNUP_SESSION_KEY, None)

    redirect_to = request.session.pop(_POST_AUTH_REDIRECT_KEY, "/")
    return CompleteSignupResponse(
        user=_build_auth_session_user(
            local_user, picture=_string_value(oauth_user.get("picture"))
        ),
        redirect_to=redirect_to,
    )
