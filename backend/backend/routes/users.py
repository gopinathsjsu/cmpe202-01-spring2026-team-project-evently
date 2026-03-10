from __future__ import annotations

import os
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr
from pymongo.asynchronous.database import AsyncDatabase

from backend.db import get_db
from backend.models.user import GlobalRole, User, UserProfile

router = APIRouter()

DbDep = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/gif"}
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5 MB

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


class PhotoResponse(BaseModel):
    profile_photo_url: str | None


class ActivityItem(BaseModel):
    event_id: int
    event_title: str
    event_image_url: str | None
    action: Literal["attended", "created", "registered"]
    date: datetime


class ActivityResponse(BaseModel):
    items: list[ActivityItem]


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

_USER_TOP_LEVEL_FIELDS = {"first_name", "last_name", "username", "email", "phone_number"}
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


async def _build_user_detail(db: AsyncDatabase[dict[str, Any]], user: User) -> UserDetail:
    events_created = await db["events"].count_documents({"organizer_user_id": user.id})
    events_attended = await db["attendance"].count_documents(
        {"user_id": user.id, "status": {"$eq": "checked_in"}}
    )
    return UserDetail.from_user(
        user,
        events_created_count=events_created,
        events_attended_count=events_attended,
    )


# ---------------------------------------------------------------------------
# GET /users/{user_id}
# ---------------------------------------------------------------------------


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(db: DbDep, user_id: int) -> UserDetail:
    """Retrieve full details for a single user."""
    user = await _get_user_or_404(db, user_id)
    return await _build_user_detail(db, user)


# ---------------------------------------------------------------------------
# PATCH /users/{user_id} -- Update Profile
# ---------------------------------------------------------------------------


@router.patch("/{user_id}", response_model=UserDetail)
async def update_user(db: DbDep, user_id: int, body: UserProfileUpdate) -> UserDetail:
    """Update a user's profile information."""
    await _get_user_or_404(db, user_id)

    updates: dict[str, Any] = {}
    provided = body.model_dump(exclude_none=True)

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
async def upload_photo(db: DbDep, user_id: int, file: UploadFile) -> PhotoResponse:
    """Upload or replace a user's profile photo."""
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
        if os.path.exists(old_path):
            os.remove(old_path)

    ext = (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
    filename = f"{user_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    photo_url = f"/uploads/{filename}"
    await db["users"].update_one(
        {"id": user_id}, {"$set": {"profile_photo_url": photo_url}}
    )

    return PhotoResponse(profile_photo_url=photo_url)


# ---------------------------------------------------------------------------
# DELETE /users/{user_id}/photo -- Remove Profile Photo
# ---------------------------------------------------------------------------


@router.delete("/{user_id}/photo", status_code=204)
async def delete_photo(db: DbDep, user_id: int) -> None:
    """Remove a user's profile photo."""
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
    limit: int = 10,
) -> ActivityResponse:
    """Return a user's recent activity (events created, attended, registered)."""
    await _get_user_or_404(db, user_id)

    items: list[ActivityItem] = []

    # Events created by the user
    created_cursor = db["events"].find({"organizer_user_id": user_id}).sort(
        "start_time", -1
    )
    async for raw_event in created_cursor:
        items.append(
            ActivityItem(
                event_id=raw_event["id"],
                event_title=raw_event["title"],
                event_image_url=raw_event.get("image_url"),
                action="created",
                date=raw_event["start_time"],
            )
        )

    # Events the user attended or registered for
    attendance_cursor = db["attendance"].find({"user_id": user_id}).sort(
        "checked_in_at", -1
    )
    async for raw_att in attendance_cursor:
        event_raw = await db["events"].find_one({"id": raw_att["event_id"]})
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
                action=action,
                date=date,
            )
        )

    items.sort(key=lambda a: a.date, reverse=True)
    items = items[:limit]

    return ActivityResponse(items=items)
