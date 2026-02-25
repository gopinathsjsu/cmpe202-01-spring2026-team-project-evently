from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from backend.db import get_db
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


DbDep = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


@router.get("/", response_model=PaginatedEvents)
async def list_events(
    db: DbDep,
    q: Annotated[
        str | None,
        Query(description="Free-text search across title and about fields."),
    ] = None,
    category: Annotated[
        EventCategory | None,
        Query(description="Filter events by category."),
    ] = None,
    start_from: Annotated[
        datetime | None,
        Query(description="Return events starting at or after this datetime."),
    ] = None,
    start_to: Annotated[
        datetime | None,
        Query(description="Return events starting at or before this datetime."),
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
