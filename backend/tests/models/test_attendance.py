from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from backend.models.attendance import AttendanceStatus, EventAttendance


async def test_create_and_retrieve_attendance(
    db: AsyncDatabase[dict[str, Any]], attendance_data: dict[str, Any]
) -> None:
    collection = db["attendance"]

    result = await collection.insert_one(attendance_data)
    assert result.inserted_id is not None

    found = await collection.find_one({"_id": result.inserted_id})
    assert found is not None

    attendance = EventAttendance(**found)

    assert attendance.event_id == attendance_data["event_id"]
    assert attendance.user_id == attendance_data["user_id"]
    assert attendance.status == AttendanceStatus.Going
    assert attendance.checked_in_at is None

    delete_result = await collection.delete_one({"_id": result.inserted_id})
    assert delete_result.deleted_count == 1

    gone = await collection.find_one({"_id": result.inserted_id})
    assert gone is None


async def test_attendance_with_checkin(
    db: AsyncDatabase[dict[str, Any]], attendance_data: dict[str, Any]
) -> None:
    from datetime import datetime

    attendance_data["status"] = "checked_in"
    attendance_data["checked_in_at"] = datetime(2026, 6, 15, 19, 30, 0)

    collection = db["attendance"]

    result = await collection.insert_one(attendance_data)
    found = await collection.find_one({"_id": result.inserted_id})

    assert found is not None
    attendance = EventAttendance(**found)

    assert attendance.status == AttendanceStatus.CheckedIn
    assert attendance.checked_in_at is not None

    await collection.delete_one({"_id": result.inserted_id})
