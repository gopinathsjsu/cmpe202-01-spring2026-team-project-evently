from datetime import datetime as DateTime
from enum import StrEnum

from pydantic import BaseModel, model_validator


class AttendanceStatus(StrEnum):
    Going = "going"
    Cancelled = "cancelled"
    CheckedIn = "checked_in"


class EventAttendance(BaseModel):
    event_id: int
    user_id: int
    status: AttendanceStatus = AttendanceStatus.Going
    checked_in_at: DateTime | None = None

    @model_validator(mode="after")
    def checked_in_at_required_for_checked_in(self) -> "EventAttendance":
        if self.status == AttendanceStatus.CheckedIn and self.checked_in_at is None:
            raise ValueError("checked_in_at is required when status is checked_in")
        return self
