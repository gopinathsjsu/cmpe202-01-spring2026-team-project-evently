from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from backend.db import get_db
from backend.models.event import Event, EventCategory, EventScheduleEntry, Location
from backend.models.event_favorite import EventFavorite

router = APIRouter()

DbDep = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]

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


class FavoriteAddResponse(BaseModel):
    event_id: int
    user_id: int
    status: Literal["favorited"] = "favorited"


class FavoriteRemoveResponse(BaseModel):
    event_id: int
    user_id: int
    status: Literal["unfavorited"] = "unfavorited"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class EventCreate(BaseModel):
    title: str
    about: str
    organizer_user_id: int
    price: float = 0.0
    total_capacity: int
    start_time: datetime
    end_time: datetime
    category: EventCategory
    is_online: bool = False
    image_url: str | None = None
    schedule: list[EventScheduleEntry] = Field(default_factory=list)
    location: Location


class FavoriteRequest(BaseModel):
    user_id: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _next_event_id(db: AsyncDatabase[dict[str, Any]]) -> int:
    last = await db["events"].find_one(sort=[("id", DESCENDING)])
    return (last["id"] + 1) if last else 1


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
    filters: dict[str, object] = {}

    if q:
        filters["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"about": {"$regex": q, "$options": "i"}},
        ]

    if category is not None:
        filters["category"] = category.value

    if city is not None:
        filters["location.city"] = {"$regex": f"^{city}$", "$options": "i"}

    if is_online is not None:
        filters["is_online"] = is_online

    if price_type == "free":
        filters["price"] = 0.0
    elif price_type == "paid":
        filters["price"] = {"$gt": 0}

    if date_preset:
        preset_from, preset_to = _resolve_date_preset(date_preset)
        filters["start_time"] = {"$gte": preset_from, "$lte": preset_to}
    elif start_from or start_to:
        time_filter: dict[str, datetime] = {}
        if start_from is not None:
            time_filter["$gte"] = start_from
        if start_to is not None:
            time_filter["$lte"] = start_to
        filters["start_time"] = time_filter

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


# ---------------------------------------------------------------------------
# GET /events/{event_id}  — Single event detail
# ---------------------------------------------------------------------------


@router.get("/{event_id}", response_model=EventDetail)
async def get_event(db: DbDep, event_id: int) -> EventDetail:
    """Retrieve full details for a single event."""
    raw = await db["events"].find_one({"id": event_id})
    if raw is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = Event(**raw)
    attending = await db["attendance"].count_documents(
        {"event_id": event_id, "status": {"$ne": "cancelled"}}
    )
    favorites = await db["event_favorites"].count_documents({"event_id": event_id})

    return EventDetail.from_event(
        event, attending_count=attending, favorites_count=favorites
    )


# ---------------------------------------------------------------------------
# POST /events/  — Create a new event
# ---------------------------------------------------------------------------


@router.post("/", response_model=EventDetail, status_code=201)
async def create_event(db: DbDep, body: EventCreate) -> EventDetail:
    """Create a new event and return its full detail."""
    new_id = await _next_event_id(db)

    event = Event(
        id=new_id,
        title=body.title,
        about=body.about,
        organizer_user_id=body.organizer_user_id,
        price=body.price,
        total_capacity=body.total_capacity,
        start_time=body.start_time,
        end_time=body.end_time,
        category=body.category,
        is_online=body.is_online,
        image_url=body.image_url,
        schedule=body.schedule,
        location=body.location,
    )

    await db["events"].insert_one(event.model_dump())

    return EventDetail.from_event(event, attending_count=0, favorites_count=0)


# ---------------------------------------------------------------------------
# POST /events/{event_id}/favorites  — Favorite an event
# ---------------------------------------------------------------------------


@router.post(
    "/{event_id}/favorites", response_model=FavoriteAddResponse, status_code=201
)
async def add_favorite(
    db: DbDep, event_id: int, body: FavoriteRequest
) -> FavoriteAddResponse:
    """Add an event to a user's favorites (idempotent)."""
    event = await db["events"].find_one({"id": event_id})
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    favorite = EventFavorite(event_id=event_id, user_id=body.user_id)

    existing = await db["event_favorites"].find_one(
        {"event_id": favorite.event_id, "user_id": favorite.user_id}
    )
    if existing is None:
        await db["event_favorites"].insert_one(favorite.model_dump())

    return FavoriteAddResponse(event_id=event_id, user_id=body.user_id)


# ---------------------------------------------------------------------------
# DELETE /events/{event_id}/favorites  — Unfavorite an event
# ---------------------------------------------------------------------------


@router.delete(
    "/{event_id}/favorites", response_model=FavoriteRemoveResponse, status_code=200
)
async def remove_favorite(
    db: DbDep, event_id: int, body: FavoriteRequest
) -> FavoriteRemoveResponse:
    """Remove an event from a user's favorites."""
    event = await db["events"].find_one({"id": event_id})
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    favorite = EventFavorite(event_id=event_id, user_id=body.user_id)
    await db["event_favorites"].delete_one(
        {"event_id": favorite.event_id, "user_id": favorite.user_id}
    )
    return FavoriteRemoveResponse(event_id=event_id, user_id=body.user_id)
