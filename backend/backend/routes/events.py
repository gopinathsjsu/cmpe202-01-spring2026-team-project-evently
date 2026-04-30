import logging
import os
import re
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, field_validator, model_validator
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError
from starlette.requests import Request

from backend.app_config import get_frontend_settings
from backend.db import get_db
from backend.models.attendance import AttendanceStatus
from backend.models.event import (
    Event,
    EventCategory,
    EventScheduleEntry,
    EventStatus,
    Location,
)
from backend.models.event_favorite import EventFavorite
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
from backend.services.notifications.arq import ArqClient, get_arq, utc_naive_datetime
from backend.services.notifications.email import (
    REMINDER_LEAD_TIME_MINUTES,
    EmailNotificationService,
    get_email_notif_service,
)

router = APIRouter()

DbDep = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]
AuthUserDep = Annotated[AuthSessionUser, Depends(require_authenticated_user)]
USER_CALENDAR_COLLECTION = "user_calendar_entries"
USER_CALENDAR_SYNC_COLLECTION = "user_calendar_syncs"
EVENT_USER_LOCK_COLLECTION = "event_user_locks"
EVENT_USER_LOCK_STALE_AFTER = timedelta(minutes=5)
CALENDAR_REMOVAL_STARTED_AT_FIELD = "removal_started_at"
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
ALLOWED_EVENT_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif"}
ALLOWED_EVENT_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
MAX_EVENT_IMAGE_SIZE = 5 * 1024 * 1024
ArqDep = Annotated[ArqClient, Depends(get_arq)]
EmailNotifDep = Annotated[EmailNotificationService, Depends(get_email_notif_service)]

# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class LocationSummary(BaseModel):
    venue_name: str | None = None
    city: str
    state: str

    @classmethod
    def from_location(cls, location: Location) -> "LocationSummary":
        return cls(
            venue_name=location.venue_name,
            city=location.city,
            state=location.state,
        )


class EventListItem(BaseModel):
    id: int
    title: str
    about: str
    organizer_user_id: int
    price: float
    total_capacity: int
    start_time: datetime
    end_time: datetime
    category: EventCategory
    is_online: bool
    image_url: str | None
    location: LocationSummary
    attending_count: int

    @classmethod
    def from_event(cls, event: Event, *, attending_count: int) -> "EventListItem":
        return cls(
            **event.model_dump(exclude={"schedule", "location"}),
            location=LocationSummary.from_location(event.location),
            attending_count=attending_count,
        )


class PaginatedEvents(BaseModel):
    items: list[EventListItem]
    total: int = Field(..., description="Total matching events")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")


class EventDetail(BaseModel):
    id: int
    title: str
    about: str
    organizer_user_id: int
    price: float
    total_capacity: int
    start_time: datetime
    end_time: datetime
    category: EventCategory
    is_online: bool
    image_url: str | None
    schedule: list[EventScheduleEntry]
    location: Location
    attending_count: int
    favorites_count: int

    @classmethod
    def from_event(
        cls, event: Event, *, attending_count: int, favorites_count: int
    ) -> "EventDetail":
        return cls(
            **event.model_dump(),
            attending_count=attending_count,
            favorites_count=favorites_count,
        )


class EventManageDetail(EventDetail):
    status: EventStatus

    @classmethod
    def from_event(
        cls, event: Event, *, attending_count: int, favorites_count: int
    ) -> "EventManageDetail":
        return cls(
            **event.model_dump(),
            attending_count=attending_count,
            favorites_count=favorites_count,
        )


class FavoriteAddResponse(BaseModel):
    event_id: int
    user_id: int
    status: Literal["favorited"] = "favorited"


class FavoriteRemoveResponse(BaseModel):
    event_id: int
    user_id: int
    status: Literal["unfavorited"] = "unfavorited"


class AttendanceStatusResponse(BaseModel):
    event_id: int
    user_id: int
    status: Literal["going", "checked_in", "cancelled"] | None


class AttendanceRegisterResponse(BaseModel):
    event_id: int
    user_id: int
    status: Literal["going"] = "going"
    in_calendar: bool = True
    google_synced: bool = False


class AttendanceCancelResponse(BaseModel):
    event_id: int
    user_id: int
    status: Literal["cancelled"] = "cancelled"
    in_calendar: bool = False
    google_synced: bool = False


class AppCalendarStatusResponse(BaseModel):
    event_id: int
    in_calendar: bool
    google_sync_enabled: bool = False


class AppCalendarMutationResponse(BaseModel):
    event_id: int
    status: Literal["added", "removed"]
    google_synced: bool = False


class PendingEventListItem(BaseModel):
    id: int
    title: str
    about: str
    organizer_user_id: int
    price: float
    total_capacity: int
    start_time: datetime
    end_time: datetime
    category: EventCategory
    status: Literal["pending"]
    is_online: bool
    image_url: str | None
    location: LocationSummary

    @classmethod
    def from_event(cls, event: Event) -> "PendingEventListItem":
        return cls(
            id=event.id,
            title=event.title,
            about=event.about,
            organizer_user_id=event.organizer_user_id,
            price=event.price,
            total_capacity=event.total_capacity,
            start_time=event.start_time,
            end_time=event.end_time,
            category=event.category,
            status="pending",
            is_online=event.is_online,
            image_url=event.image_url,
            location=LocationSummary.from_location(event.location),
        )


class EventAttendeeItem(BaseModel):
    user_id: int
    first_name: str
    last_name: str
    email: str
    profile_photo_url: str | None
    status: Literal["going", "checked_in"]
    checked_in_at: datetime | None


class EventAttendeesResponse(BaseModel):
    event_id: int
    event_title: str
    total_capacity: int
    going_count: int
    checked_in_count: int
    attendees: list[EventAttendeeItem]


class CheckInResponse(BaseModel):
    event_id: int
    user_id: int
    status: Literal["checked_in"] = "checked_in"
    checked_in_at: datetime


class UndoCheckInResponse(BaseModel):
    event_id: int
    user_id: int
    status: Literal["going"] = "going"


class RemoveAttendeeResponse(BaseModel):
    event_id: int
    user_id: int
    status: Literal["cancelled"] = "cancelled"
    in_calendar: bool = False
    google_synced: bool = False


class EventImageResponse(BaseModel):
    event_id: int
    image_url: str


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class EventCreate(BaseModel):
    title: str
    about: str
    price: float = 0.0
    total_capacity: int
    start_time: datetime
    end_time: datetime
    category: EventCategory
    is_online: bool = False
    image_url: str | None = None
    schedule: list[EventScheduleEntry] = Field(default_factory=list)
    location: Location

    @field_validator("price")
    @classmethod
    def price_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Price must be non-negative")
        return v

    @field_validator("total_capacity")
    @classmethod
    def capacity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Total capacity must be positive")
        return v

    @model_validator(mode="after")
    def end_time_after_start_time(self) -> "EventCreate":
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self


class EventUpdate(BaseModel):
    title: str | None = None
    about: str | None = None
    price: float | None = None
    total_capacity: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    category: EventCategory | None = None
    is_online: bool | None = None
    schedule: list[EventScheduleEntry] | None = None
    location: Location | None = None

    @field_validator("price")
    @classmethod
    def price_non_negative(cls, v: float | None) -> float | None:
        if v is not None and v < 0:
            raise ValueError("Price must be non-negative")
        return v

    @field_validator("total_capacity")
    @classmethod
    def capacity_positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("Total capacity must be positive")
        return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _next_event_id(db: AsyncDatabase[dict[str, Any]]) -> int:
    if await db["events"].count_documents({}, limit=1) == 0:
        await db["counters"].delete_one({"_id": "events"})
    elif await db["counters"].find_one({"_id": "events"}) is None:
        latest = await db["events"].find_one({}, sort=[("id", DESCENDING)])
        next_seq = int(latest["id"]) if latest is not None else 0
        await db["counters"].update_one(
            {"_id": "events"},
            {"$set": {"seq": next_seq}},
            upsert=True,
        )

    counter = await db["counters"].find_one_and_update(
        {"_id": "events"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    if counter is None:
        raise HTTPException(status_code=500, detail="Failed to allocate event ID")
    return int(counter["seq"])


def _event_upload_path(filename: str) -> str:
    return os.path.join(UPLOAD_DIR, filename)


def _removable_event_image_path(event_id: int, image_url: str | None) -> str | None:
    if not image_url or not image_url.startswith("/uploads/"):
        return None

    filename = image_url.rsplit("/", 1)[-1]
    if not filename.startswith(f"event_{event_id}_"):
        return None

    return _event_upload_path(filename)


async def _read_valid_event_image(file: UploadFile) -> tuple[bytes, str]:
    if file.content_type not in ALLOWED_EVENT_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Allowed: JPG, PNG, GIF.",
        )

    ext = (file.filename or "event-image.jpg").rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EVENT_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Invalid file extension. Allowed: jpg, jpeg, png, gif.",
        )

    contents = await file.read()
    if len(contents) > MAX_EVENT_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max size is 5MB.")

    return contents, ext


async def _event_counts(
    db: AsyncDatabase[dict[str, Any]], event_id: int
) -> tuple[int, int]:
    attending = await db["attendance"].count_documents(
        {"event_id": event_id, "status": {"$ne": "cancelled"}}
    )
    favorites = await db["event_favorites"].count_documents({"event_id": event_id})
    return attending, favorites


def _event_with_updates(event: Event, updates: dict[str, Any]) -> Event:
    data = event.model_dump()
    data.update(updates)
    return Event(**data)


async def _attending_counts(
    db: AsyncDatabase[dict[str, Any]], event_ids: list[int]
) -> dict[int, int]:
    """Return {event_id: count} for active attendees."""
    if not event_ids:
        return {}
    pipeline: list[dict[str, Any]] = [
        {"$match": {"event_id": {"$in": event_ids}, "status": {"$ne": "cancelled"}}},
        {"$group": {"_id": "$event_id", "count": {"$sum": 1}}},
    ]
    counts: dict[int, int] = {}
    cursor = await db["attendance"].aggregate(pipeline)
    async for doc in cursor:
        counts[doc["_id"]] = doc["count"]
    return counts


async def _ensure_registered_count(
    db: AsyncDatabase[dict[str, Any]], event_id: int
) -> None:
    raw_event = await db["events"].find_one(
        {"id": event_id}, {"_id": 1, "registered_count": 1}
    )
    if raw_event is None or "registered_count" in raw_event:
        return

    active_count = await db["attendance"].count_documents(
        {"event_id": event_id, "status": {"$ne": AttendanceStatus.Cancelled.value}}
    )
    await db["events"].update_one(
        {"_id": raw_event["_id"], "registered_count": {"$exists": False}},
        {"$set": {"registered_count": active_count}},
    )


async def _reserve_event_slot(db: AsyncDatabase[dict[str, Any]], event_id: int) -> bool:
    reserved = await db["events"].find_one_and_update(
        {
            "id": event_id,
            "$expr": {"$lt": ["$registered_count", "$total_capacity"]},
        },
        {"$inc": {"registered_count": 1}},
        return_document=ReturnDocument.AFTER,
    )
    return reserved is not None


async def _release_event_slot(db: AsyncDatabase[dict[str, Any]], event_id: int) -> None:
    await db["events"].update_one(
        {"id": event_id, "registered_count": {"$gt": 0}},
        {"$inc": {"registered_count": -1}},
    )


def _event_user_lock_id(*, event_id: int, user_id: int) -> str:
    return f"{event_id}:{user_id}"


async def _acquire_event_user_lock(
    db: AsyncDatabase[dict[str, Any]], *, event_id: int, user_id: int
) -> str:
    lock_id = _event_user_lock_id(event_id=event_id, user_id=user_id)
    now = datetime.now(tz=UTC)
    await db[EVENT_USER_LOCK_COLLECTION].delete_one(
        {"_id": lock_id, "acquired_at": {"$lt": now - EVENT_USER_LOCK_STALE_AFTER}}
    )
    try:
        await db[EVENT_USER_LOCK_COLLECTION].insert_one(
            {
                "_id": lock_id,
                "event_id": event_id,
                "user_id": user_id,
                "acquired_at": now,
            }
        )
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=409,
            detail="This event registration is already being updated. Please try again.",
        ) from exc
    return lock_id


async def _release_event_user_lock(
    db: AsyncDatabase[dict[str, Any]], lock_id: str
) -> None:
    await db[EVENT_USER_LOCK_COLLECTION].delete_one({"_id": lock_id})


def _resolve_date_preset(preset: str) -> tuple[datetime, datetime]:
    now = datetime.now(tz=UTC)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if preset == "today":
        return start_of_day, start_of_day + timedelta(days=1)
    if preset == "this_week":
        monday = start_of_day - timedelta(days=start_of_day.weekday())
        return monday, monday + timedelta(days=7)
    # this_month
    first = start_of_day.replace(day=1)
    if first.month == 12:
        end = first.replace(year=first.year + 1, month=1)
    else:
        end = first.replace(month=first.month + 1)
    return first, end


def _require_admin(current_user: AuthSessionUser) -> None:
    if "admin" not in current_user.roles:
        raise HTTPException(status_code=403, detail="Administrator access required")


def _require_organizer_or_admin(current_user: AuthSessionUser, event: Event) -> None:
    if "admin" not in current_user.roles and current_user.id != event.organizer_user_id:
        raise HTTPException(
            status_code=403, detail="Organizer or administrator access required"
        )


def _public_event_visibility_filter(event_id: int) -> dict[str, Any]:
    return {
        "id": event_id,
        "$or": [
            {"status": EventStatus.Approved.value},
            {"status": {"$exists": False}},
        ],
    }


def _frontend_event_url(request: Request, event_id: int) -> str | None:
    frontend_settings = get_frontend_settings(request.app)
    if frontend_settings.primary_origin:
        return f"{frontend_settings.primary_origin}/events/{event_id}"
    if frontend_settings.allowed_origins:
        return f"{frontend_settings.allowed_origins[0]}/events/{event_id}"
    return None


def _string_value(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


async def _google_sync_enabled(db: AsyncDatabase[dict[str, Any]], user_id: int) -> bool:
    raw = await db[USER_CALENDAR_SYNC_COLLECTION].find_one({"user_id": user_id})
    return raw is not None and raw.get("google_sync_enabled") is True


async def _calendar_entry_for_user(
    db: AsyncDatabase[dict[str, Any]], *, user_id: int, event_id: int
) -> dict[str, Any] | None:
    return await db[USER_CALENDAR_COLLECTION].find_one(
        {"user_id": user_id, "event_id": event_id}
    )


async def _attendance_status_for_user(
    db: AsyncDatabase[dict[str, Any]], *, user_id: int, event_id: int
) -> str | None:
    attendance = await db["attendance"].find_one(
        {"event_id": event_id, "user_id": user_id},
        sort=[("_id", DESCENDING)],
    )
    if attendance is None:
        return None
    return _string_value(attendance.get("status"))


async def _create_google_calendar_sync_fields(
    request: Request, event: Event
) -> tuple[str, dict[str, object]]:
    access_token = await get_google_calendar_access_token(request)
    try:
        google_event = await create_google_calendar_event(
            access_token,
            google_calendar_event_payload(
                event,
                event_url=_frontend_event_url(request, event.id),
            ),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logging.getLogger(__name__).exception(
            "Unexpected Google Calendar sync failure for event %s", event.id
        )
        raise HTTPException(
            status_code=502,
            detail="Could not sync this event to Google Calendar. Please try again.",
        ) from exc
    google_event_id = _string_value(google_event.get("id"))
    if google_event_id is None:
        raise HTTPException(
            status_code=502,
            detail="Google Calendar returned an invalid response.",
        )

    return access_token, {
        "google_calendar_event_id": google_event_id,
        "google_calendar_event_url": _string_value(google_event.get("htmlLink")),
    }


async def _delete_google_calendar_sync_if_present(
    request: Request, existing_entry: dict[str, Any]
) -> bool:
    google_event_id = _string_value(existing_entry.get("google_calendar_event_id"))
    if google_event_id is None:
        return False

    access_token = await get_google_calendar_access_token(request)
    await delete_google_calendar_event(access_token, google_event_id)
    return True


async def _ensure_event_in_app_calendar(
    db: AsyncDatabase[dict[str, Any]],
    request: Request,
    *,
    user_id: int,
    event: Event,
) -> bool:
    existing = await _calendar_entry_for_user(db, user_id=user_id, event_id=event.id)
    google_synced = False

    if existing is None:
        document: dict[str, object] = {
            "user_id": user_id,
            "event_id": event.id,
            "added_at": datetime.now(tz=UTC),
        }
        if await _google_sync_enabled(db, user_id):
            access_token, sync_fields = await _create_google_calendar_sync_fields(
                request, event
            )
            document.update(sync_fields)
            google_synced = True
            try:
                await db[USER_CALENDAR_COLLECTION].insert_one(document)
            except DuplicateKeyError:
                try:
                    await delete_google_calendar_event(
                        access_token, str(sync_fields["google_calendar_event_id"])
                    )
                except Exception:
                    logging.getLogger(__name__).exception(
                        "Failed to roll back duplicate Google Calendar event"
                    )
                concurrent = await _calendar_entry_for_user(
                    db, user_id=user_id, event_id=event.id
                )
                return (
                    concurrent is not None
                    and _string_value(concurrent.get("google_calendar_event_id"))
                    is not None
                )
            except Exception:
                try:
                    await delete_google_calendar_event(
                        access_token, str(sync_fields["google_calendar_event_id"])
                    )
                except Exception:
                    logging.getLogger(__name__).exception(
                        "Failed to roll back Google Calendar event after local insert failure"
                    )
                raise
            return google_synced

        try:
            await db[USER_CALENDAR_COLLECTION].insert_one(document)
        except DuplicateKeyError:
            concurrent = await _calendar_entry_for_user(
                db, user_id=user_id, event_id=event.id
            )
            return (
                concurrent is not None
                and _string_value(concurrent.get("google_calendar_event_id"))
                is not None
            )
        return google_synced

    if _string_value(
        existing.get("google_calendar_event_id")
    ) is None and await _google_sync_enabled(db, user_id):
        access_token, sync_fields = await _create_google_calendar_sync_fields(
            request, event
        )
        try:
            result = await db[USER_CALENDAR_COLLECTION].update_one(
                {
                    "_id": existing["_id"],
                    "$or": [
                        {"google_calendar_event_id": {"$exists": False}},
                        {"google_calendar_event_id": None},
                    ],
                },
                {"$set": sync_fields},
            )
            if result.matched_count != 1:
                await delete_google_calendar_event(
                    access_token, str(sync_fields["google_calendar_event_id"])
                )
                concurrent = await _calendar_entry_for_user(
                    db, user_id=user_id, event_id=event.id
                )
                return (
                    concurrent is not None
                    and _string_value(concurrent.get("google_calendar_event_id"))
                    is not None
                )
        except Exception:
            try:
                await delete_google_calendar_event(
                    access_token, str(sync_fields["google_calendar_event_id"])
                )
            except Exception:
                logging.getLogger(__name__).exception(
                    "Failed to roll back Google Calendar event after local update failure"
                )
            raise
        return True

    return _string_value(existing.get("google_calendar_event_id")) is not None


async def _remove_event_from_app_calendar_if_present(
    db: AsyncDatabase[dict[str, Any]],
    request: Request,
    *,
    user_id: int,
    event_id: int,
) -> tuple[bool, bool]:
    existing = await _calendar_entry_for_user(db, user_id=user_id, event_id=event_id)
    if existing is None:
        return False, False

    claim = await db[USER_CALENDAR_COLLECTION].update_one(
        {
            "_id": existing["_id"],
            CALENDAR_REMOVAL_STARTED_AT_FIELD: {"$exists": False},
        },
        {"$set": {CALENDAR_REMOVAL_STARTED_AT_FIELD: datetime.now(tz=UTC)}},
    )
    if claim.matched_count != 1:
        return False, False

    try:
        google_synced = await _delete_google_calendar_sync_if_present(request, existing)
        await db[USER_CALENDAR_COLLECTION].delete_one({"_id": existing["_id"]})
    except Exception:
        await db[USER_CALENDAR_COLLECTION].update_one(
            {"_id": existing["_id"]},
            {"$unset": {CALENDAR_REMOVAL_STARTED_AT_FIELD: ""}},
        )
        raise

    return True, google_synced


# ---------------------------------------------------------------------------
# GET /events/  — List with filters, search, sort, pagination
# ---------------------------------------------------------------------------


@router.get("/", response_model=PaginatedEvents)
async def list_events(
    db: DbDep,
    q: Annotated[
        str | None,
        Query(description="Free-text search across title and about."),
    ] = None,
    category: Annotated[
        EventCategory | None,
        Query(description="Filter by category."),
    ] = None,
    city: Annotated[
        str | None,
        Query(description="Filter by city name (case-insensitive)."),
    ] = None,
    is_online: Annotated[
        bool | None,
        Query(description="Filter by online (true) or in-person (false)."),
    ] = None,
    price_type: Annotated[
        Literal["free", "paid"] | None,
        Query(description="Filter by free (price=0) or paid (price>0)."),
    ] = None,
    date_preset: Annotated[
        Literal["today", "this_week", "this_month"] | None,
        Query(description="Quick date range filter."),
    ] = None,
    start_from: Annotated[
        datetime | None,
        Query(description="Events starting at or after this datetime."),
    ] = None,
    start_to: Annotated[
        datetime | None,
        Query(description="Events starting at or before this datetime."),
    ] = None,
    sort_by: Annotated[
        Literal["start_time", "price", "title"],
        Query(description="Field to sort by."),
    ] = "start_time",
    sort_order: Annotated[
        Literal["asc", "desc"],
        Query(description="Sort direction."),
    ] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 12,
) -> PaginatedEvents:
    """List events with filtering, search, sorting, and pagination."""
    collection = db["events"]
    conditions: list[dict[str, object]] = [
        {
            "$or": [
                {"status": EventStatus.Approved.value},
                {"status": {"$exists": False}},
            ]
        }
    ]

    if q:
        escaped_q = re.escape(q)
        conditions.append(
            {
                "$or": [
                    {"title": {"$regex": escaped_q, "$options": "i"}},
                    {"about": {"$regex": escaped_q, "$options": "i"}},
                ]
            }
        )

    if category is not None:
        conditions.append({"category": category.value})

    if city is not None:
        escaped_city = re.escape(city)
        conditions.append(
            {"location.city": {"$regex": f"^{escaped_city}$", "$options": "i"}}
        )

    if is_online is not None:
        conditions.append({"is_online": is_online})

    if price_type == "free":
        conditions.append({"price": 0.0})
    elif price_type == "paid":
        conditions.append({"price": {"$gt": 0}})

    if date_preset:
        preset_from, preset_to = _resolve_date_preset(date_preset)
        conditions.append({"start_time": {"$gte": preset_from, "$lt": preset_to}})
    elif start_from or start_to:
        time_filter: dict[str, datetime] = {}
        if start_from is not None:
            time_filter["$gte"] = start_from
        if start_to is not None:
            time_filter["$lte"] = start_to
        conditions.append({"start_time": time_filter})

    filters: dict[str, object] = (
        conditions[0] if len(conditions) == 1 else {"$and": conditions}
    )

    sort_direction = ASCENDING if sort_order == "asc" else DESCENDING
    sort_key = {"start_time": "start_time", "price": "price", "title": "title"}[sort_by]
    skip = (page - 1) * page_size

    total = await collection.count_documents(filters)
    cursor = (
        collection.find(filters)
        .sort(sort_key, sort_direction)
        .skip(skip)
        .limit(page_size)
    )
    raw_events = await cursor.to_list(length=page_size)

    event_ids = [r["id"] for r in raw_events]
    counts = await _attending_counts(db, event_ids)

    items: list[EventListItem] = []
    for raw in raw_events:
        event = Event(**raw)
        items.append(
            EventListItem.from_event(event, attending_count=counts.get(event.id, 0))
        )

    return PaginatedEvents(items=items, total=total, page=page, page_size=page_size)


@router.get("/pending", response_model=list[PendingEventListItem])
async def list_pending_events(
    db: DbDep, current_user: AuthUserDep
) -> list[PendingEventListItem]:
    _require_admin(current_user)
    raw_events = await (
        db["events"]
        .find({"status": EventStatus.Pending.value})
        .sort("start_time", ASCENDING)
        .to_list(length=None)
    )
    return [PendingEventListItem.from_event(Event(**raw)) for raw in raw_events]


# ---------------------------------------------------------------------------
# GET /events/{event_id}  — Single event detail
# ---------------------------------------------------------------------------


@router.get("/{event_id}", response_model=EventDetail)
async def get_event(db: DbDep, event_id: int) -> EventDetail:
    """Retrieve full details for a single event."""
    raw = await db["events"].find_one(_public_event_visibility_filter(event_id))
    if raw is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = Event(**raw)
    attending, favorites = await _event_counts(db, event_id)

    return EventDetail.from_event(
        event, attending_count=attending, favorites_count=favorites
    )


@router.get("/{event_id}/manage", response_model=EventManageDetail)
async def get_event_for_management(
    db: DbDep, event_id: int, current_user: AuthUserDep
) -> EventManageDetail:
    """Retrieve full event details for organizer/admin editing."""
    raw = await db["events"].find_one({"id": event_id})
    if raw is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = Event(**raw)
    _require_organizer_or_admin(current_user, event)
    attending, favorites = await _event_counts(db, event_id)
    return EventManageDetail.from_event(
        event, attending_count=attending, favorites_count=favorites
    )


@router.patch("/{event_id}", response_model=EventManageDetail)
async def update_event(
    db: DbDep, event_id: int, body: EventUpdate, current_user: AuthUserDep
) -> EventManageDetail:
    """Update an event. Restricted to the organizer or an admin."""
    raw = await db["events"].find_one({"id": event_id})
    if raw is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = Event(**raw)
    _require_organizer_or_admin(current_user, event)

    updates = body.model_dump(exclude_unset=True)
    if isinstance(updates.get("start_time"), datetime):
        updates["start_time"] = utc_naive_datetime(updates["start_time"])
    if isinstance(updates.get("end_time"), datetime):
        updates["end_time"] = utc_naive_datetime(updates["end_time"])

    if body.start_time is None and body.end_time is None:
        pass
    elif updates.get("end_time", event.end_time) <= updates.get(
        "start_time", event.start_time
    ):
        raise HTTPException(status_code=422, detail="End time must be after start time")

    if updates:
        updated_event = _event_with_updates(event, updates)
        await db["events"].update_one({"id": event_id}, {"$set": updates})
    else:
        updated_event = event

    attending, favorites = await _event_counts(db, event_id)
    return EventManageDetail.from_event(
        updated_event, attending_count=attending, favorites_count=favorites
    )


# ---------------------------------------------------------------------------
# GET /events/{event_id}/attendance  — Current user's attendance status
# ---------------------------------------------------------------------------


@router.get("/{event_id}/attendance", response_model=AttendanceStatusResponse)
async def get_my_attendance(
    db: DbDep, event_id: int, current_user: AuthUserDep
) -> AttendanceStatusResponse:
    """Return the authenticated user's attendance status for a given event."""
    event = await db["events"].find_one(
        _public_event_visibility_filter(event_id), {"_id": 1}
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    attendance = await db["attendance"].find_one(
        {"event_id": event_id, "user_id": current_user.id},
        sort=[("_id", DESCENDING)],
    )

    return AttendanceStatusResponse(
        event_id=event_id,
        user_id=current_user.id,
        status=attendance["status"] if attendance is not None else None,
    )


# ---------------------------------------------------------------------------
# GET /events/{event_id}/calendar  — Current user's app-calendar status
# ---------------------------------------------------------------------------


@router.get("/{event_id}/calendar", response_model=AppCalendarStatusResponse)
async def get_my_calendar_status(
    db: DbDep, event_id: int, current_user: AuthUserDep
) -> AppCalendarStatusResponse:
    raw_event = await db["events"].find_one(_public_event_visibility_filter(event_id))
    if raw_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    existing = await _calendar_entry_for_user(
        db, user_id=current_user.id, event_id=event_id
    )
    if existing is None:
        attendance_status = await _attendance_status_for_user(
            db, user_id=current_user.id, event_id=event_id
        )
        if (
            attendance_status is not None
            and attendance_status != AttendanceStatus.Cancelled.value
        ):
            with suppress(DuplicateKeyError):
                await db[USER_CALENDAR_COLLECTION].insert_one(
                    {
                        "user_id": current_user.id,
                        "event_id": event_id,
                        "added_at": datetime.now(tz=UTC),
                    }
                )
            existing = {"user_id": current_user.id, "event_id": event_id}

    return AppCalendarStatusResponse(
        event_id=event_id,
        in_calendar=existing is not None,
        google_sync_enabled=await _google_sync_enabled(db, current_user.id),
    )


# ---------------------------------------------------------------------------
# POST /events/{event_id}/calendar  — Add event to user's app calendar
# ---------------------------------------------------------------------------


@router.post("/{event_id}/calendar", response_model=AppCalendarMutationResponse)
async def add_event_to_app_calendar(
    db: DbDep,
    request: Request,
    event_id: int,
    current_user: AuthUserDep,
) -> AppCalendarMutationResponse:
    raw_event = await db["events"].find_one(_public_event_visibility_filter(event_id))
    if raw_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    lock_id = await _acquire_event_user_lock(
        db, event_id=event_id, user_id=current_user.id
    )
    try:
        google_synced = await _ensure_event_in_app_calendar(
            db,
            request,
            user_id=current_user.id,
            event=Event(**raw_event),
        )
    finally:
        await _release_event_user_lock(db, lock_id)

    return AppCalendarMutationResponse(
        event_id=event_id,
        status="added",
        google_synced=google_synced,
    )


# ---------------------------------------------------------------------------
# DELETE /events/{event_id}/calendar  — Remove event from user's app calendar
# ---------------------------------------------------------------------------


@router.delete("/{event_id}/calendar", response_model=AppCalendarMutationResponse)
async def remove_event_from_app_calendar(
    db: DbDep,
    request: Request,
    event_id: int,
    current_user: AuthUserDep,
) -> AppCalendarMutationResponse:
    raw_event = await db["events"].find_one(_public_event_visibility_filter(event_id))
    if raw_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    lock_id = await _acquire_event_user_lock(
        db, event_id=event_id, user_id=current_user.id
    )
    try:
        removed, google_synced = await _remove_event_from_app_calendar_if_present(
            db,
            request,
            user_id=current_user.id,
            event_id=event_id,
        )
    finally:
        await _release_event_user_lock(db, lock_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Calendar entry not found")

    return AppCalendarMutationResponse(
        event_id=event_id,
        status="removed",
        google_synced=google_synced,
    )


# ---------------------------------------------------------------------------
# POST /events/{event_id}/attendance  — Register current user for an event
# ---------------------------------------------------------------------------


@router.post("/{event_id}/attendance", response_model=AttendanceRegisterResponse)
async def register_attendance(
    db: DbDep,
    request: Request,
    event_id: int,
    current_user: AuthUserDep,
    email_notif: EmailNotifDep,
) -> AttendanceRegisterResponse:
    """Register the authenticated user for a given event."""
    raw_event = await db["events"].find_one(_public_event_visibility_filter(event_id))
    if raw_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = Event(**raw_event)
    if event.organizer_user_id == current_user.id:
        raise HTTPException(
            status_code=400, detail="Organizers cannot register for their own events"
        )

    lock_id = await _acquire_event_user_lock(
        db, event_id=event_id, user_id=current_user.id
    )
    try:
        existing = await db["attendance"].find_one(
            {"event_id": event_id, "user_id": current_user.id},
            sort=[("_id", DESCENDING)],
        )
        if (
            existing is not None
            and existing["status"] != AttendanceStatus.Cancelled.value
        ):
            google_synced = await _ensure_event_in_app_calendar(
                db,
                request,
                user_id=current_user.id,
                event=event,
            )
            return AttendanceRegisterResponse(
                event_id=event_id,
                user_id=current_user.id,
                google_synced=google_synced,
            )

        await _ensure_registered_count(db, event_id)
        if not await _reserve_event_slot(db, event_id):
            raise HTTPException(status_code=400, detail="This event is sold out")

        inserted_attendance_id: object | None = None
        calendar_preexisting = (
            await _calendar_entry_for_user(
                db, user_id=current_user.id, event_id=event_id
            )
            is not None
        )
        try:
            if existing is None:
                insert_result = await db["attendance"].insert_one(
                    {
                        "event_id": event_id,
                        "user_id": current_user.id,
                        "status": AttendanceStatus.Going.value,
                        "checked_in_at": None,
                    }
                )
                inserted_attendance_id = insert_result.inserted_id
            else:
                result = await db["attendance"].update_one(
                    {
                        "_id": existing["_id"],
                        "status": AttendanceStatus.Cancelled.value,
                    },
                    {
                        "$set": {
                            "status": AttendanceStatus.Going.value,
                            "checked_in_at": None,
                        }
                    },
                )
                if result.matched_count != 1:
                    raise HTTPException(
                        status_code=409, detail="Registration state changed"
                    )

            google_synced = await _ensure_event_in_app_calendar(
                db,
                request,
                user_id=current_user.id,
                event=event,
            )
            await email_notif.send_registration_confirmation(current_user.email, event)
        except Exception:
            if inserted_attendance_id is not None:
                await db["attendance"].delete_one({"_id": inserted_attendance_id})
            elif existing is not None:
                await db["attendance"].update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {
                            "status": existing["status"],
                            "checked_in_at": existing.get("checked_in_at"),
                        }
                    },
                )
            await _release_event_slot(db, event_id)
            if not calendar_preexisting:
                try:
                    await _remove_event_from_app_calendar_if_present(
                        db,
                        request,
                        user_id=current_user.id,
                        event_id=event_id,
                    )
                except Exception:
                    logging.getLogger(__name__).exception(
                        "Failed to roll back calendar entry after registration failure"
                    )
            raise

        return AttendanceRegisterResponse(
            event_id=event_id,
            user_id=current_user.id,
            google_synced=google_synced,
        )
    finally:
        await _release_event_user_lock(db, lock_id)


# ---------------------------------------------------------------------------
# DELETE /events/{event_id}/attendance  — Cancel current user's registration
# ---------------------------------------------------------------------------


@router.delete("/{event_id}/attendance", response_model=AttendanceCancelResponse)
async def cancel_attendance(
    db: DbDep, request: Request, event_id: int, current_user: AuthUserDep
) -> AttendanceCancelResponse:
    """Cancel the authenticated user's registration for a given event."""
    event = await db["events"].find_one(
        _public_event_visibility_filter(event_id), {"_id": 1}
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    lock_id = await _acquire_event_user_lock(
        db, event_id=event_id, user_id=current_user.id
    )
    try:
        existing = await db["attendance"].find_one(
            {"event_id": event_id, "user_id": current_user.id},
            sort=[("_id", DESCENDING)],
        )
        if existing is None or existing["status"] == AttendanceStatus.Cancelled.value:
            raise HTTPException(status_code=404, detail="Registration not found")

        result = await db["attendance"].update_one(
            {"_id": existing["_id"], "status": existing["status"]},
            {
                "$set": {
                    "status": AttendanceStatus.Cancelled.value,
                    "checked_in_at": None,
                }
            },
        )
        if result.matched_count != 1:
            raise HTTPException(status_code=409, detail="Registration state changed")

        await _ensure_registered_count(db, event_id)
        await _release_event_slot(db, event_id)

        try:
            _, google_synced = await _remove_event_from_app_calendar_if_present(
                db,
                request,
                user_id=current_user.id,
                event_id=event_id,
            )
        except Exception:
            await db["attendance"].update_one(
                {"_id": existing["_id"], "status": AttendanceStatus.Cancelled.value},
                {
                    "$set": {
                        "status": existing["status"],
                        "checked_in_at": existing.get("checked_in_at"),
                    }
                },
            )
            await db["events"].update_one(
                {"id": event_id}, {"$inc": {"registered_count": 1}}
            )
            raise
    finally:
        await _release_event_user_lock(db, lock_id)

    return AttendanceCancelResponse(
        event_id=event_id,
        user_id=current_user.id,
        google_synced=google_synced,
    )


# ---------------------------------------------------------------------------
# GET /events/{event_id}/attendees  — List all attendees (organizer/admin)
# ---------------------------------------------------------------------------


@router.get("/{event_id}/attendees", response_model=EventAttendeesResponse)
async def get_event_attendees(
    db: DbDep, event_id: int, current_user: AuthUserDep
) -> EventAttendeesResponse:
    """Return all attendees for an event. Restricted to the organizer or an admin."""
    raw_event = await db["events"].find_one({"id": event_id})
    if raw_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = Event(**raw_event)
    _require_organizer_or_admin(current_user, event)

    attendance_records = await (
        db["attendance"]
        .find({"event_id": event_id})
        .sort("_id", ASCENDING)
        .to_list(length=None)
    )

    # Deduplicate before filtering so a later cancellation hides older active rows.
    latest_by_user: dict[int, dict[str, Any]] = {}
    for record in attendance_records:
        latest_by_user[record["user_id"]] = record
    latest_by_user = {
        user_id: record
        for user_id, record in latest_by_user.items()
        if record["status"] != AttendanceStatus.Cancelled.value
    }

    user_ids = list(latest_by_user.keys())
    users_by_id: dict[int, dict[str, Any]] = {}
    if user_ids:
        async for raw_user in db["users"].find({"id": {"$in": user_ids}}):
            users_by_id[raw_user["id"]] = raw_user

    attendees: list[EventAttendeeItem] = []
    for uid, record in latest_by_user.items():
        user_raw = users_by_id.get(uid)
        if user_raw is None:
            continue
        raw_checked_in_at = record.get("checked_in_at")
        attendees.append(
            EventAttendeeItem(
                user_id=uid,
                first_name=user_raw.get("first_name", ""),
                last_name=user_raw.get("last_name", ""),
                email=user_raw.get("email", ""),
                profile_photo_url=user_raw.get("profile_photo_url"),
                status=record["status"],
                checked_in_at=raw_checked_in_at
                if isinstance(raw_checked_in_at, datetime)
                else None,
            )
        )

    attendees.sort(key=lambda a: (a.last_name.lower(), a.first_name.lower()))

    going_count = sum(1 for a in attendees if a.status == AttendanceStatus.Going.value)
    checked_in_count = sum(
        1 for a in attendees if a.status == AttendanceStatus.CheckedIn.value
    )

    return EventAttendeesResponse(
        event_id=event_id,
        event_title=event.title,
        total_capacity=event.total_capacity,
        going_count=going_count,
        checked_in_count=checked_in_count,
        attendees=attendees,
    )


# ---------------------------------------------------------------------------
# POST /events/{event_id}/attendees/{user_id}/check-in  — Check in attendee
# ---------------------------------------------------------------------------


@router.post("/{event_id}/attendees/{user_id}/check-in", response_model=CheckInResponse)
async def check_in_attendee(
    db: DbDep, event_id: int, user_id: int, current_user: AuthUserDep
) -> CheckInResponse:
    """Check in an attendee for an event. Restricted to the organizer or an admin."""
    raw_event = await db["events"].find_one({"id": event_id})
    if raw_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = Event(**raw_event)
    _require_organizer_or_admin(current_user, event)

    lock_id = await _acquire_event_user_lock(db, event_id=event_id, user_id=user_id)
    try:
        existing = await db["attendance"].find_one(
            {
                "event_id": event_id,
                "user_id": user_id,
                "status": {"$ne": AttendanceStatus.Cancelled.value},
            },
            sort=[("_id", DESCENDING)],
        )
        if existing is None:
            raise HTTPException(status_code=404, detail="Attendee not found")

        if existing["status"] == AttendanceStatus.CheckedIn.value:
            raise HTTPException(
                status_code=409, detail="Attendee is already checked in"
            )

        checked_in_at = datetime.now(tz=UTC)
        result = await db["attendance"].update_one(
            {"_id": existing["_id"], "status": AttendanceStatus.Going.value},
            {
                "$set": {
                    "status": AttendanceStatus.CheckedIn.value,
                    "checked_in_at": checked_in_at,
                }
            },
        )
        if result.matched_count != 1:
            raise HTTPException(status_code=409, detail="Registration state changed")
    finally:
        await _release_event_user_lock(db, lock_id)

    return CheckInResponse(
        event_id=event_id, user_id=user_id, checked_in_at=checked_in_at
    )


# ---------------------------------------------------------------------------
# DELETE /events/{event_id}/attendees/{user_id}/check-in  — Undo check-in
# ---------------------------------------------------------------------------


@router.delete(
    "/{event_id}/attendees/{user_id}/check-in", response_model=UndoCheckInResponse
)
async def undo_check_in_attendee(
    db: DbDep, event_id: int, user_id: int, current_user: AuthUserDep
) -> UndoCheckInResponse:
    """Undo a check-in for an attendee. Restricted to the organizer or an admin."""
    raw_event = await db["events"].find_one({"id": event_id})
    if raw_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = Event(**raw_event)
    _require_organizer_or_admin(current_user, event)

    lock_id = await _acquire_event_user_lock(db, event_id=event_id, user_id=user_id)
    try:
        existing = await db["attendance"].find_one(
            {"event_id": event_id, "user_id": user_id},
            sort=[("_id", DESCENDING)],
        )
        if existing is None or existing["status"] == AttendanceStatus.Cancelled.value:
            raise HTTPException(status_code=404, detail="Attendee not found")

        if existing["status"] == AttendanceStatus.Going.value:
            raise HTTPException(status_code=409, detail="Attendee is not checked in")

        result = await db["attendance"].update_one(
            {"_id": existing["_id"], "status": AttendanceStatus.CheckedIn.value},
            {"$set": {"status": AttendanceStatus.Going.value, "checked_in_at": None}},
        )
        if result.matched_count != 1:
            raise HTTPException(status_code=409, detail="Registration state changed")
    finally:
        await _release_event_user_lock(db, lock_id)

    return UndoCheckInResponse(event_id=event_id, user_id=user_id)


# ---------------------------------------------------------------------------
# DELETE /events/{event_id}/attendees/{user_id}  — Remove attendee
# ---------------------------------------------------------------------------


@router.delete("/{event_id}/attendees/{user_id}", response_model=RemoveAttendeeResponse)
async def remove_attendee(
    db: DbDep,
    request: Request,
    event_id: int,
    user_id: int,
    current_user: AuthUserDep,
) -> RemoveAttendeeResponse:
    """Remove an attendee from an event. Restricted to the organizer or an admin."""
    raw_event = await db["events"].find_one({"id": event_id})
    if raw_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = Event(**raw_event)
    _require_organizer_or_admin(current_user, event)

    lock_id = await _acquire_event_user_lock(db, event_id=event_id, user_id=user_id)
    try:
        existing = await db["attendance"].find_one(
            {"event_id": event_id, "user_id": user_id},
            sort=[("_id", DESCENDING)],
        )
        if existing is None or existing["status"] == AttendanceStatus.Cancelled.value:
            raise HTTPException(status_code=404, detail="Attendee not found")

        result = await db["attendance"].update_one(
            {"_id": existing["_id"], "status": existing["status"]},
            {
                "$set": {
                    "status": AttendanceStatus.Cancelled.value,
                    "checked_in_at": None,
                }
            },
        )
        if result.matched_count != 1:
            raise HTTPException(status_code=409, detail="Registration state changed")

        await _ensure_registered_count(db, event_id)
        await _release_event_slot(db, event_id)

        try:
            _, google_synced = await _remove_event_from_app_calendar_if_present(
                db,
                request,
                user_id=user_id,
                event_id=event_id,
            )
        except Exception:
            await db["attendance"].update_one(
                {"_id": existing["_id"], "status": AttendanceStatus.Cancelled.value},
                {
                    "$set": {
                        "status": existing["status"],
                        "checked_in_at": existing.get("checked_in_at"),
                    }
                },
            )
            await db["events"].update_one(
                {"id": event_id}, {"$inc": {"registered_count": 1}}
            )
            raise
    finally:
        await _release_event_user_lock(db, lock_id)

    return RemoveAttendeeResponse(
        event_id=event_id, user_id=user_id, google_synced=google_synced
    )


# ---------------------------------------------------------------------------
# POST /events/  — Create a new event
# ---------------------------------------------------------------------------


@router.post("/", response_model=EventDetail, status_code=201)
async def create_event(
    db: DbDep,
    body: EventCreate,
    current_user: AuthUserDep,
    arq: ArqDep,
    email_notif: EmailNotifDep,
) -> EventDetail:
    """Create a new event and return its full detail."""
    new_id = await _next_event_id(db)

    event = Event(
        id=new_id,
        title=body.title,
        about=body.about,
        organizer_user_id=current_user.id,
        price=body.price,
        total_capacity=body.total_capacity,
        start_time=body.start_time,
        end_time=body.end_time,
        category=body.category,
        status=EventStatus.Pending,
        is_online=body.is_online,
        image_url=body.image_url,
        schedule=body.schedule,
        location=body.location,
    )

    await db["events"].insert_one({**event.model_dump(), "registered_count": 0})

    reminder_time = utc_naive_datetime(event.start_time) - timedelta(
        minutes=REMINDER_LEAD_TIME_MINUTES
    )
    if reminder_time > datetime.now(UTC).replace(tzinfo=None):
        await arq.schedule_event_reminder(event.id, reminder_time)
    await email_notif.send_event_creation_confirmation(current_user.email, event)

    return EventDetail.from_event(event, attending_count=0, favorites_count=0)


@router.post("/{event_id}/image", response_model=EventImageResponse)
async def upload_event_image(
    db: DbDep, event_id: int, file: UploadFile, current_user: AuthUserDep
) -> EventImageResponse:
    """Upload or replace an event image. Restricted to the organizer or an admin."""
    raw_event = await db["events"].find_one({"id": event_id})
    if raw_event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = Event(**raw_event)
    _require_organizer_or_admin(current_user, event)
    contents, ext = await _read_valid_event_image(file)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = f"event_{event_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = _event_upload_path(filename)
    old_path = _removable_event_image_path(event_id, event.image_url)

    with open(filepath, "wb") as f:
        f.write(contents)

    image_url = f"/uploads/{filename}"
    try:
        await db["events"].update_one(
            {"id": event_id}, {"$set": {"image_url": image_url}}
        )
    except Exception:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise

    if old_path and os.path.exists(old_path):
        os.remove(old_path)

    return EventImageResponse(event_id=event_id, image_url=image_url)


@router.post("/{event_id}/approve", response_model=PendingEventListItem)
async def approve_event(
    db: DbDep, event_id: int, current_user: AuthUserDep
) -> PendingEventListItem:
    _require_admin(current_user)
    raw = await db["events"].find_one_and_update(
        {"id": event_id, "status": EventStatus.Pending.value},
        {"$set": {"status": EventStatus.Approved.value}},
        return_document=ReturnDocument.AFTER,
    )
    if raw is None:
        raise HTTPException(status_code=404, detail="Pending event not found")
    return PendingEventListItem.from_event(
        Event(**raw).model_copy(update={"status": EventStatus.Pending})
    )


@router.post("/{event_id}/reject", response_model=PendingEventListItem)
async def reject_event(
    db: DbDep, event_id: int, current_user: AuthUserDep
) -> PendingEventListItem:
    _require_admin(current_user)
    raw = await db["events"].find_one_and_update(
        {"id": event_id, "status": EventStatus.Pending.value},
        {"$set": {"status": EventStatus.Rejected.value}},
        return_document=ReturnDocument.AFTER,
    )
    if raw is None:
        raise HTTPException(status_code=404, detail="Pending event not found")
    return PendingEventListItem.from_event(
        Event(**raw).model_copy(update={"status": EventStatus.Pending})
    )


# ---------------------------------------------------------------------------
# POST /events/{event_id}/favorites  — Favorite an event
# ---------------------------------------------------------------------------


@router.post(
    "/{event_id}/favorites", response_model=FavoriteAddResponse, status_code=201
)
async def add_favorite(
    db: DbDep, event_id: int, current_user: AuthUserDep
) -> FavoriteAddResponse:
    """Add an event to a user's favorites (idempotent)."""
    event = await db["events"].find_one(_public_event_visibility_filter(event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    favorite = EventFavorite(event_id=event_id, user_id=current_user.id)

    existing = await db["event_favorites"].find_one(
        {"event_id": favorite.event_id, "user_id": favorite.user_id}
    )
    if existing is None:
        await db["event_favorites"].insert_one(favorite.model_dump())

    return FavoriteAddResponse(event_id=event_id, user_id=current_user.id)


# ---------------------------------------------------------------------------
# DELETE /events/{event_id}/favorites  — Unfavorite an event
# ---------------------------------------------------------------------------


@router.delete(
    "/{event_id}/favorites", response_model=FavoriteRemoveResponse, status_code=200
)
async def remove_favorite(
    db: DbDep, event_id: int, current_user: AuthUserDep
) -> FavoriteRemoveResponse:
    """Remove an event from a user's favorites."""
    event = await db["events"].find_one(_public_event_visibility_filter(event_id))
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    favorite = EventFavorite(event_id=event_id, user_id=current_user.id)
    await db["event_favorites"].delete_one(
        {"event_id": favorite.event_id, "user_id": favorite.user_id}
    )
    return FavoriteRemoveResponse(event_id=event_id, user_id=current_user.id)
