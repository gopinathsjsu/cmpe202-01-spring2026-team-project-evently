from datetime import datetime as DateTime
from enum import StrEnum

from pydantic import BaseModel


class AttendanceStatus(StrEnum):
    Going = "going"
    Cancelled = "cancelled"
    CheckedIn = "checked_in"


class EventAttendance(BaseModel):
    event_id: int
    user_id: int
    status: AttendanceStatus = AttendanceStatus.Going
    checked_in_at: DateTime | None = None
