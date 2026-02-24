from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field


class GlobalRole(StrEnum):
    User = "user"
    Admin = "admin"


class UserProfile(BaseModel):
    bio: str | None = None
    location: str | None = None
    website: str | None = None

    twitter_handle: str | None = None
    instagram_handle: str | None = None
    facebook_handle: str | None = None
    linkedin_handle: str | None = None

    interests: list[str] = Field(default_factory=list)


class User(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str

    email: EmailStr
    phone_number: str | None = None

    roles: set[GlobalRole] = Field(default_factory=lambda: {GlobalRole.User})

    profile: UserProfile = Field(default_factory=UserProfile)


class EventFavorite(BaseModel):
    event_id: int
    user_id: int
