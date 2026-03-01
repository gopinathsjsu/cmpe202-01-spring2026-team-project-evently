from datetime import datetime as DateTime
from enum import StrEnum

from pydantic import BaseModel, field_validator, model_validator


class EventScheduleEntry(BaseModel):
    start_time: DateTime
    description: str


class EventCategory(StrEnum):
    Music = "Music"
    Business = "Business"
    Arts = "Arts"
    Food = "Food"
    Sports = "Sports"
    Education = "Education"
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

    @field_validator("latitude")
    @classmethod
    def latitude_bounds(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def longitude_bounds(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v


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
    is_online: bool = False
    image_url: str | None = None

    schedule: list[EventScheduleEntry]
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
    def end_time_after_start_time(self) -> "Event":
        if self.end_time <= self.start_time:
            raise ValueError("End time must be after start time")
        return self
