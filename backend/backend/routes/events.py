from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query  # type: ignore[import-untyped]
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from backend.models.event import Event, EventCategory

router = APIRouter()


class EventListItem(BaseModel):
    """Simplified view of an event for listings."""

    id: int
    title: str
    about: str
    organizer_user_id: int
    price: float
    total_capacity: int
    start_time: datetime
    end_time: datetime
    category: EventCategory


class PaginatedEvents(BaseModel):
    items: list[EventListItem]
    total: int = Field(..., description="Total number of events matching the filters")
    page: int
    page_size: int


async def _get_db() -> AsyncDatabase[dict[str, Any]]:  # pragma: no cover
    """Placeholder replaced at app startup via dependency_overrides."""
    from backend.api import get_db  # type: ignore[misc]

    async for db in get_db():
        return db
    raise RuntimeError("get_db yielded nothing")


@router.get("/", response_model=PaginatedEvents)  # type: ignore[misc]
async def list_events(
    db: AsyncDatabase[dict[str, Any]] = Depends(_get_db),
    q: str | None = Query(
        default=None,
        description="Free-text search across title and about fields.",
    ),
    category: EventCategory | None = Query(
        default=None,
        description="Filter events by category.",
    ),
    start_from: datetime | None = Query(
        default=None,
        description="Return events starting at or after this datetime.",
    ),
    start_to: datetime | None = Query(
        default=None,
        description="Return events starting at or before this datetime.",
    ),
    sort_by: Literal["start_time", "price", "title"] = Query(
        default="start_time",
        description="Field to sort by.",
    ),
    sort_order: Literal["asc", "desc"] = Query(
        default="asc",
        description="Sort direction.",
    ),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 12,
) -> PaginatedEvents:
    """List events with optional filtering, search, sorting, and pagination."""
    collection = db["events"]

    filters: dict[str, object] = {}

    if q:
        filters["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"about": {"$regex": q, "$options": "i"}},
        ]

    if category is not None:
        filters["category"] = category.value

    if start_from or start_to:
        time_filter: dict[str, datetime] = {}
        if start_from is not None:
            time_filter["$gte"] = start_from
        if start_to is not None:
            time_filter["$lte"] = start_to
        filters["start_time"] = time_filter

    sort_direction = ASCENDING if sort_order == "asc" else DESCENDING
    sort_field = {
        "start_time": "start_time",
        "price": "price",
        "title": "title",
    }[sort_by]

    skip = (page - 1) * page_size

    total = await collection.count_documents(filters)

    cursor = (
        collection.find(filters)
        .sort(sort_field, sort_direction)
        .skip(skip)
        .limit(page_size)
    )

    raw_events = await cursor.to_list(length=page_size)

    items: list[EventListItem] = []
    for raw in raw_events:
        event = Event(**raw)
        items.append(
            EventListItem(
                id=event.id,
                title=event.title,
                about=event.about,
                organizer_user_id=event.organizer_user_id,
                price=event.price,
                total_capacity=event.total_capacity,
                start_time=event.start_time,
                end_time=event.end_time,
                category=event.category,
            )
        )

    return PaginatedEvents(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
