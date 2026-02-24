from datetime import datetime as DateTime
from enum import StrEnum

from pydantic import BaseModel


class EventScheduleEntry(BaseModel):
    start_time: DateTime
    description: str


class EventCategory(StrEnum):
    Music = "Music"
    Sports = "Sports"
    Theater = "Theater"
    Comedy = "Comedy"
    Festival = "Festival"
    Conference = "Conference"
    Workshop = "Workshop"
    Other = "Other"


class Location(BaseModel):
    longitude: float
    latitude: float

    venue_name: str | None = None

    address: str
    city: str
    state: str
    zip_code: str


class Event(BaseModel):
    id: int
    title: str
    about: str
    organizer_user_id: int
    price: float
    total_capacity: int

    start_time: DateTime
    end_time: DateTime

    category: EventCategory
    schedule: list[EventScheduleEntry]
    location: Location
