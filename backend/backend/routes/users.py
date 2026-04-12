from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel, EmailStr
from pymongo.asynchronous.database import AsyncDatabase
from starlette.requests import Request

from backend.app_config import get_frontend_settings
from backend.db import get_db
from backend.models.attendance import AttendanceStatus
from backend.models.event import Event
from backend.models.user import GlobalRole, User, UserProfile
from backend.routes.auth import (
    AuthSessionUser,
    get_google_calendar_access_token,
    require_authenticated_user,
)
from backend.services.calendar_sync import (
    create_google_calendar_event,
    delete_google_calendar_event,
    google_calendar_event_payload,
)

router = APIRouter()

DbDep = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]
AuthUserDep = Annotated[AuthSessionUser, Depends(require_authenticated_user)]

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/gif"}
ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5 MB
USER_CALENDAR_COLLECTION = "user_calendar_entries"
USER_CALENDAR_SYNC_COLLECTION = "user_calendar_syncs"

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UserDetail(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    phone_number: str | None
    roles: set[GlobalRole]
    profile_photo_url: str | None = None
    profile: UserProfile
    events_created_count: int = 0
    events_attended_count: int = 0

    @classmethod
    def from_user(
        cls,
        user: User,
        *,
        events_created_count: int = 0,
        events_attended_count: int = 0,
    ) -> UserDetail:
        return cls(
            **user.model_dump(),
            events_created_count=events_created_count,
            events_attended_count=events_attended_count,
        )


class PublicUserDetail(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    profile_photo_url: str | None = None
    profile: UserProfile
    events_created_count: int = 0
    events_attended_count: int = 0

    @classmethod
    def from_user(
        cls,
        user: User,
        *,
        events_created_count: int = 0,
        events_attended_count: int = 0,
    ) -> PublicUserDetail:
        return cls(
            id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            profile_photo_url=user.profile_photo_url,
            profile=user.profile,
            events_created_count=events_created_count,
            events_attended_count=events_attended_count,
        )


class PhotoResponse(BaseModel):
    profile_photo_url: str | None


class ActivityItem(BaseModel):
    event_id: int
    event_title: str
    event_image_url: str | None
    event_end_time: datetime | None = None
    action: Literal["attended", "created", "registered"]
    date: datetime


class ActivityResponse(BaseModel):
    items: list[ActivityItem]


class MyEventItem(BaseModel):
    id: int
    title: str
    start_time: datetime
    end_time: datetime
    category: str
    is_online: bool
    image_url: str | None = None
    location_summary: str
    price: float
    status: str | None = None
    attending_count: int = 0


class MyEventsResponse(BaseModel):
    created: list[MyEventItem]
    registered: list[MyEventItem]


class CalendarItem(BaseModel):
    event_id: int
    event_title: str
    event_image_url: str | None
    start_time: datetime
    end_time: datetime | None = None
    added_at: datetime
    google_synced: bool = False
    google_calendar_event_url: str | None = None


class CalendarResponse(BaseModel):
    items: list[CalendarItem]
    google_sync_enabled: bool = False


class GoogleCalendarSyncResponse(BaseModel):
    google_sync_enabled: bool = True
    synced_count: int
    skipped_count: int
    status: Literal["enabled"] = "enabled"


class GoogleCalendarUnsyncResponse(BaseModel):
    google_sync_enabled: bool = False
    unsynced_count: int
    status: Literal["disabled"] = "disabled"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class UserProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    email: EmailStr | None = None
    phone_number: str | None = None

    bio: str | None = None
    location: str | None = None
    website: str | None = None

    twitter_handle: str | None = None
    instagram_handle: str | None = None
    facebook_handle: str | None = None
    linkedin_handle: str | None = None

    interests: list[str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_USER_TOP_LEVEL_FIELDS = {
    "first_name",
    "last_name",
    "username",
    "email",
    "phone_number",
}
_PROFILE_FIELDS = {
    "bio",
    "location",
    "website",
    "twitter_handle",
    "instagram_handle",
    "facebook_handle",
    "linkedin_handle",
    "interests",
}


async def _get_user_or_404(db: AsyncDatabase[dict[str, Any]], user_id: int) -> User:
    raw = await db["users"].find_one({"id": user_id})
    if raw is None:
        raise HTTPException(status_code=404, detail="User not found")
    return User(**raw)


async def _ensure_unique_user_fields(
    db: AsyncDatabase[dict[str, Any]], user_id: int, provided: dict[str, Any]
) -> dict[str, Any]:
    normalized = dict(provided)

    if "email" in normalized:
        normalized["email"] = str(normalized["email"]).strip().lower()
        existing_email = await db["users"].find_one(
            {"email": normalized["email"]}, {"id": 1}
        )
        if existing_email is not None and existing_email.get("id") != user_id:
            raise HTTPException(status_code=409, detail="Email is already in use")

    if "username" in normalized:
        username = str(normalized["username"]).strip()
        normalized["username"] = username
        existing_username = await db["users"].find_one(
            {"username": username}, {"id": 1}
        )
        if existing_username is not None and existing_username.get("id") != user_id:
            raise HTTPException(status_code=409, detail="Username is already in use")

    return normalized


async def _build_user_detail(
    db: AsyncDatabase[dict[str, Any]], user: User
) -> UserDetail:
    events_created = await db["events"].count_documents({"organizer_user_id": user.id})
    events_attended = await db["attendance"].count_documents(
        {"user_id": user.id, "status": {"$eq": "checked_in"}}
    )
    return UserDetail.from_user(
        user,
        events_created_count=events_created,
        events_attended_count=events_attended,
    )


async def _build_public_user_detail(
    db: AsyncDatabase[dict[str, Any]], user: User
) -> PublicUserDetail:
    events_created = await db["events"].count_documents({"organizer_user_id": user.id})
    events_attended = await db["attendance"].count_documents(
        {"user_id": user.id, "status": {"$eq": "checked_in"}}
    )
    return PublicUserDetail.from_user(
        user,
        events_created_count=events_created,
        events_attended_count=events_attended,
    )


def _ensure_same_user(current_user: AuthSessionUser, user_id: int) -> None:
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403, detail="You can only modify your own user."
        )


def _string_value(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _frontend_event_url(request: Request, event_id: int) -> str | None:
    frontend_settings = get_frontend_settings(request.app)
    if frontend_settings.primary_origin:
        return f"{frontend_settings.primary_origin}/events/{event_id}"
    if frontend_settings.allowed_origins:
        return f"{frontend_settings.allowed_origins[0]}/events/{event_id}"
    return None


async def _google_sync_enabled(db: AsyncDatabase[dict[str, Any]], user_id: int) -> bool:
    raw = await db[USER_CALENDAR_SYNC_COLLECTION].find_one({"user_id": user_id})
    return raw is not None and raw.get("google_sync_enabled") is True


async def _set_google_sync_enabled(
    db: AsyncDatabase[dict[str, Any]], user_id: int, enabled: bool
) -> None:
    await db[USER_CALENDAR_SYNC_COLLECTION].update_one(
        {"user_id": user_id},
        {
            "$set": {
                "google_sync_enabled": enabled,
                "updated_at": datetime.now(tz=UTC),
            }
        },
        upsert=True,
    )


async def _calendar_entries_for_user(
    db: AsyncDatabase[dict[str, Any]], user_id: int
) -> list[dict[str, Any]]:
    return await (
        db[USER_CALENDAR_COLLECTION]
        .find({"user_id": user_id})
        .sort("added_at", -1)
        .to_list(length=None)
    )


async def _events_by_id(
    db: AsyncDatabase[dict[str, Any]], event_ids: list[int]
) -> dict[int, Event]:
    events: dict[int, Event] = {}
    if not event_ids:
        return events

    async for raw_event in db["events"].find({"id": {"$in": event_ids}}):
        event = Event(**raw_event)
        events[event.id] = event
    return events


async def _backfill_registered_calendar_entries(
    db: AsyncDatabase[dict[str, Any]], user_id: int
) -> None:
    existing_entries = await _calendar_entries_for_user(db, user_id)
    existing_event_ids = {
        int(entry["event_id"])
        for entry in existing_entries
        if isinstance(entry.get("event_id"), int)
    }

    attendance_records = await (
        db["attendance"].find({"user_id": user_id}).sort("_id", -1).to_list(length=None)
    )
    latest_status_by_event: dict[int, str | None] = {}
    for record in attendance_records:
        event_id = record.get("event_id")
        if not isinstance(event_id, int) or event_id in latest_status_by_event:
            continue
        latest_status_by_event[event_id] = _string_value(record.get("status"))

    missing_event_ids = [
        event_id
        for event_id, status in latest_status_by_event.items()
        if status is not None
        and status != AttendanceStatus.Cancelled.value
        and event_id not in existing_event_ids
    ]
    if not missing_event_ids:
        return

    events = await _events_by_id(db, missing_event_ids)
    for event_id in missing_event_ids:
        if event_id not in events:
            continue
        await db[USER_CALENDAR_COLLECTION].insert_one(
            {
                "user_id": user_id,
                "event_id": event_id,
                "added_at": datetime.now(tz=UTC),
            }
        )


async def _build_calendar_response(
    db: AsyncDatabase[dict[str, Any]], user_id: int
) -> CalendarResponse:
    await _backfill_registered_calendar_entries(db, user_id)
    entries = await _calendar_entries_for_user(db, user_id)
    events = await _events_by_id(db, [int(entry["event_id"]) for entry in entries])

    items: list[CalendarItem] = []
    for entry in entries:
        event_id = int(entry["event_id"])
        event = events.get(event_id)
        if event is None:
            continue

        added_at = entry.get("added_at")
        if not isinstance(added_at, datetime):
            added_at = event.start_time

        google_calendar_event_url = _string_value(
            entry.get("google_calendar_event_url")
        )
        items.append(
            CalendarItem(
                event_id=event.id,
                event_title=event.title,
                event_image_url=event.image_url,
                start_time=event.start_time,
                end_time=event.end_time,
                added_at=added_at,
                google_synced=_string_value(entry.get("google_calendar_event_id"))
                is not None,
                google_calendar_event_url=google_calendar_event_url,
            )
        )

    items.sort(key=lambda item: item.start_time)
    return CalendarResponse(
        items=items,
        google_sync_enabled=await _google_sync_enabled(db, user_id),
    )


# ---------------------------------------------------------------------------
# GET /users/me -- Authenticated user's own full profile
# ---------------------------------------------------------------------------


@router.get("/me", response_model=UserDetail)
async def get_current_user_profile(db: DbDep, current_user: AuthUserDep) -> UserDetail:
    """Retrieve full details for the currently authenticated user."""
    user = await _get_user_or_404(db, current_user.id)
    return await _build_user_detail(db, user)


# ---------------------------------------------------------------------------
# GET /users/me/events -- Events created and registered by the current user
# ---------------------------------------------------------------------------


@router.get("/me/events", response_model=MyEventsResponse)
async def get_my_events(db: DbDep, current_user: AuthUserDep) -> MyEventsResponse:
    """Return events the authenticated user created and events they registered for."""
    user_id = current_user.id

    def _location_summary(raw: dict[str, Any]) -> str:
        loc = raw.get("location", {})
        if raw.get("is_online"):
            return "Online Event"
        venue = loc.get("venue_name")
        city = loc.get("city", "")
        state = loc.get("state", "")
        if venue:
            return f"{venue}, {city}"
        return f"{city}, {state}".strip(", ")

    async def _build_items(
        raw_events: list[dict[str, Any]],
    ) -> list[MyEventItem]:
        event_ids = [r["id"] for r in raw_events]
        counts: dict[int, int] = {}
        if event_ids:
            pipeline: list[dict[str, Any]] = [
                {
                    "$match": {
                        "event_id": {"$in": event_ids},
                        "status": {"$ne": "cancelled"},
                    }
                },
                {"$group": {"_id": "$event_id", "count": {"$sum": 1}}},
            ]
            async for doc in await db["attendance"].aggregate(pipeline):
                counts[doc["_id"]] = doc["count"]

        return [
            MyEventItem(
                id=r["id"],
                title=r["title"],
                start_time=r["start_time"],
                end_time=r["end_time"],
                category=r.get("category", "Other"),
                is_online=r.get("is_online", False),
                image_url=r.get("image_url"),
                location_summary=_location_summary(r),
                price=r.get("price", 0),
                status=r.get("status"),
                attending_count=counts.get(r["id"], 0),
            )
            for r in raw_events
        ]

    created_raw = await (
        db["events"]
        .find({"organizer_user_id": user_id})
        .sort("start_time", -1)
        .to_list(length=50)
    )

    attendance_records = await (
        db["attendance"].find({"user_id": user_id}).sort("_id", -1).to_list(length=None)
    )
    registered_event_ids: list[int] = []
    seen: set[int] = set()
    for rec in attendance_records:
        eid = rec.get("event_id")
        if not isinstance(eid, int) or eid in seen:
            continue
        seen.add(eid)
        if rec.get("status") != "cancelled":
            registered_event_ids.append(eid)

    registered_raw: list[dict[str, Any]] = []
    if registered_event_ids:
        id_order = {eid: idx for idx, eid in enumerate(registered_event_ids)}
        raw_list = await (
            db["events"]
            .find({"id": {"$in": registered_event_ids}})
            .to_list(length=None)
        )
        raw_list.sort(key=lambda r: id_order.get(r["id"], 0))
        registered_raw = raw_list

    return MyEventsResponse(
        created=await _build_items(created_raw),
        registered=await _build_items(registered_raw),
    )


# ---------------------------------------------------------------------------
# GET /users/{user_id}
# ---------------------------------------------------------------------------


@router.get("/{user_id}", response_model=PublicUserDetail)
async def get_user(db: DbDep, user_id: int) -> PublicUserDetail:
    """Retrieve public details for a single user."""
    user = await _get_user_or_404(db, user_id)
    return await _build_public_user_detail(db, user)


# ---------------------------------------------------------------------------
# GET /users/{user_id}/calendar -- Saved app calendar items
# ---------------------------------------------------------------------------


@router.get("/{user_id}/calendar", response_model=CalendarResponse)
async def get_user_calendar(
    db: DbDep, user_id: int, current_user: AuthUserDep
) -> CalendarResponse:
    _ensure_same_user(current_user, user_id)
    await _get_user_or_404(db, user_id)
    return await _build_calendar_response(db, user_id)


# ---------------------------------------------------------------------------
# POST /users/{user_id}/calendar/sync/google -- Enable + backfill Google sync
# ---------------------------------------------------------------------------


@router.post(
    "/{user_id}/calendar/sync/google",
    response_model=GoogleCalendarSyncResponse,
)
async def sync_user_calendar_to_google(
    db: DbDep,
    request: Request,
    user_id: int,
    current_user: AuthUserDep,
) -> GoogleCalendarSyncResponse:
    _ensure_same_user(current_user, user_id)
    await _get_user_or_404(db, user_id)

    access_token = await get_google_calendar_access_token(request)
    await _backfill_registered_calendar_entries(db, user_id)
    entries = await _calendar_entries_for_user(db, user_id)
    events = await _events_by_id(db, [int(entry["event_id"]) for entry in entries])

    synced_count = 0
    skipped_count = 0
    for entry in entries:
        if _string_value(entry.get("google_calendar_event_id")) is not None:
            skipped_count += 1
            continue

        event = events.get(int(entry["event_id"]))
        if event is None:
            skipped_count += 1
            continue

        google_event = await create_google_calendar_event(
            access_token,
            google_calendar_event_payload(
                event,
                event_url=_frontend_event_url(request, event.id),
            ),
        )
        google_event_id = _string_value(google_event.get("id"))
        if google_event_id is None:
            raise HTTPException(
                status_code=502,
                detail="Google Calendar returned an invalid response.",
            )

        await db[USER_CALENDAR_COLLECTION].update_one(
            {"_id": entry["_id"]},
            {
                "$set": {
                    "google_calendar_event_id": google_event_id,
                    "google_calendar_event_url": _string_value(
                        google_event.get("htmlLink")
                    ),
                }
            },
        )
        synced_count += 1

    await _set_google_sync_enabled(db, user_id, True)
    return GoogleCalendarSyncResponse(
        synced_count=synced_count,
        skipped_count=skipped_count,
    )


# ---------------------------------------------------------------------------
# DELETE /users/{user_id}/calendar/sync/google -- Disable + remove Google sync
# ---------------------------------------------------------------------------


@router.delete(
    "/{user_id}/calendar/sync/google",
    response_model=GoogleCalendarUnsyncResponse,
)
async def unsync_user_calendar_from_google(
    db: DbDep,
    request: Request,
    user_id: int,
    current_user: AuthUserDep,
) -> GoogleCalendarUnsyncResponse:
    _ensure_same_user(current_user, user_id)
    await _get_user_or_404(db, user_id)

    entries = await _calendar_entries_for_user(db, user_id)
    synced_entries = [
        entry
        for entry in entries
        if _string_value(entry.get("google_calendar_event_id")) is not None
    ]

    access_token: str | None = None
    unsynced_count = 0
    for entry in synced_entries:
        google_event_id = _string_value(entry.get("google_calendar_event_id"))
        if google_event_id is None:
            continue

        if access_token is None:
            access_token = await get_google_calendar_access_token(request)

        await delete_google_calendar_event(access_token, google_event_id)
        await db[USER_CALENDAR_COLLECTION].update_one(
            {"_id": entry["_id"]},
            {
                "$set": {
                    "google_calendar_event_id": None,
                    "google_calendar_event_url": None,
                }
            },
        )
        unsynced_count += 1

    await _set_google_sync_enabled(db, user_id, False)
    return GoogleCalendarUnsyncResponse(unsynced_count=unsynced_count)


# ---------------------------------------------------------------------------
# PATCH /users/{user_id} -- Update Profile
# ---------------------------------------------------------------------------


@router.patch("/{user_id}", response_model=UserDetail)
async def update_user(
    db: DbDep, user_id: int, body: UserProfileUpdate, current_user: AuthUserDep
) -> UserDetail:
    """Update a user's profile information."""
    _ensure_same_user(current_user, user_id)
    await _get_user_or_404(db, user_id)

    updates: dict[str, Any] = {}
    provided = await _ensure_unique_user_fields(
        db, user_id, body.model_dump(exclude_none=True)
    )

    for field, value in provided.items():
        if field in _USER_TOP_LEVEL_FIELDS:
            updates[field] = value
        elif field in _PROFILE_FIELDS:
            updates[f"profile.{field}"] = value

    if updates:
        await db["users"].update_one({"id": user_id}, {"$set": updates})

    user = await _get_user_or_404(db, user_id)
    return await _build_user_detail(db, user)


# ---------------------------------------------------------------------------
# POST /users/{user_id}/photo -- Upload Profile Photo
# ---------------------------------------------------------------------------


@router.post("/{user_id}/photo", response_model=PhotoResponse, status_code=200)
async def upload_photo(
    db: DbDep, user_id: int, file: UploadFile, current_user: AuthUserDep
) -> PhotoResponse:
    """Upload or replace a user's profile photo."""
    _ensure_same_user(current_user, user_id)
    user = await _get_user_or_404(db, user_id)

    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Allowed: JPG, PNG, GIF.",
        )

    contents = await file.read()
    if len(contents) > MAX_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max size is 5MB.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Remove old photo if one exists
    if user.profile_photo_url:
        old_filename = user.profile_photo_url.rsplit("/", 1)[-1]
        old_path = os.path.join(UPLOAD_DIR, old_filename)
    else:
        old_path = None

    ext = (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Invalid file extension. Allowed: jpg, jpeg, png, gif.",
        )
    filename = f"{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    photo_url = f"/uploads/{filename}"
    try:
        await db["users"].update_one(
            {"id": user_id}, {"$set": {"profile_photo_url": photo_url}}
        )
    except Exception:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise

    if old_path and os.path.exists(old_path):
        os.remove(old_path)

    return PhotoResponse(profile_photo_url=photo_url)


# ---------------------------------------------------------------------------
# DELETE /users/{user_id}/photo -- Remove Profile Photo
# ---------------------------------------------------------------------------


@router.delete("/{user_id}/photo", status_code=204)
async def delete_photo(db: DbDep, user_id: int, current_user: AuthUserDep) -> None:
    """Remove a user's profile photo."""
    _ensure_same_user(current_user, user_id)
    user = await _get_user_or_404(db, user_id)

    if user.profile_photo_url:
        filename = user.profile_photo_url.rsplit("/", 1)[-1]
        filepath = os.path.join(UPLOAD_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        await db["users"].update_one(
            {"id": user_id}, {"$set": {"profile_photo_url": None}}
        )


# ---------------------------------------------------------------------------
# GET /users/{user_id}/activity -- Recent Activity Feed
# ---------------------------------------------------------------------------


@router.get("/{user_id}/activity", response_model=ActivityResponse)
async def get_user_activity(
    db: DbDep,
    user_id: int,
    current_user: AuthUserDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> ActivityResponse:
    """Return a user's recent activity (events created, attended, registered)."""
    _ensure_same_user(current_user, user_id)
    await _get_user_or_404(db, user_id)

    items: list[ActivityItem] = []

    created_cursor = (
        db["events"]
        .find({"organizer_user_id": user_id})
        .sort("start_time", -1)
        .limit(limit)
    )
    async for raw_event in created_cursor:
        items.append(
            ActivityItem(
                event_id=raw_event["id"],
                event_title=raw_event["title"],
                event_image_url=raw_event.get("image_url"),
                event_end_time=raw_event.get("end_time"),
                action="created",
                date=raw_event["start_time"],
            )
        )

    attendance_cursor = (
        db["attendance"]
        .find({"user_id": user_id})
        .sort("checked_in_at", -1)
        .limit(limit)
    )
    attendance_records = await attendance_cursor.to_list(length=limit)
    latest_attendance_records: list[dict[str, Any]] = []
    seen_event_ids: set[int] = set()
    for raw_att in reversed(attendance_records):
        event_id = raw_att["event_id"]
        if event_id in seen_event_ids:
            continue
        seen_event_ids.add(event_id)
        latest_attendance_records.append(raw_att)
    latest_attendance_records.reverse()

    event_ids = list({r["event_id"] for r in latest_attendance_records})
    events_by_id: dict[int, dict[str, Any]] = {}
    if event_ids:
        async for ev in db["events"].find({"id": {"$in": event_ids}}):
            events_by_id[ev["id"]] = ev

    for raw_att in latest_attendance_records:
        if raw_att["status"] == "cancelled":
            continue

        event_raw = events_by_id.get(raw_att["event_id"])
        if event_raw is None:
            continue

        action: Literal["attended", "registered"] = (
            "attended" if raw_att["status"] == "checked_in" else "registered"
        )
        date = raw_att.get("checked_in_at") or event_raw["start_time"]

        items.append(
            ActivityItem(
                event_id=event_raw["id"],
                event_title=event_raw["title"],
                event_image_url=event_raw.get("image_url"),
                event_end_time=event_raw.get("end_time"),
                action=action,
                date=date,
            )
        )

    items.sort(key=lambda a: a.date, reverse=True)
    items = items[:limit]

    return ActivityResponse(items=items)
