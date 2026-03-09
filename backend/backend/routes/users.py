from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.asynchronous.database import AsyncDatabase

from backend.db import get_db
from backend.models.user import GlobalRole, User, UserProfile

router = APIRouter()

DbDep = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]


class UserDetail(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    email: str
    phone_number: str | None
    roles: set[GlobalRole]
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


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(db: DbDep, user_id: int) -> UserDetail:
    """Retrieve full details for a single user."""
    raw = await db["users"].find_one({"id": user_id})
    if raw is None:
        raise HTTPException(status_code=404, detail="User not found")

    user = User(**raw)

    events_created = await db["events"].count_documents({"organizer_user_id": user_id})
    events_attended = await db["attendance"].count_documents(
        {"user_id": user_id, "status": {"$ne": "cancelled"}}
    )

    return UserDetail.from_user(
        user,
        events_created_count=events_created,
        events_attended_count=events_attended,
    )
