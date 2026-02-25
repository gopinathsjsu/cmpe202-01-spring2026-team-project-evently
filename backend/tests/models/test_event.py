from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from backend.models.event import Event, EventCategory, EventScheduleEntry, Location


async def test_create_and_retrieve_event(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]

    result = await collection.insert_one(event_data)
    assert result.inserted_id is not None

    found = await collection.find_one({"_id": result.inserted_id})
    assert found is not None

    event = Event(**found)

    assert event.id == event_data["id"]
    assert event.title == event_data["title"]
    assert event.about == event_data["about"]
    assert event.organizer_user_id == event_data["organizer_user_id"]
    assert event.price == event_data["price"]
    assert event.total_capacity == event_data["total_capacity"]
    assert event.category == EventCategory.Music
    assert len(event.schedule) == 2

    delete_result = await collection.delete_one({"_id": result.inserted_id})
    assert delete_result.deleted_count == 1

    gone = await collection.find_one({"_id": result.inserted_id})
    assert gone is None


async def test_location_as_subdocument(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]

    result = await collection.insert_one(event_data)
    found = await collection.find_one({"_id": result.inserted_id})

    assert found is not None
    location_data = found["location"]
    location = Location(**location_data)

    assert location.longitude == -122.4194
    assert location.latitude == 37.7749
    assert location.venue_name == "The Fillmore"
    assert location.address == "1805 Geary Blvd"
    assert location.city == "San Francisco"
    assert location.state == "CA"
    assert location.zip_code == "94115"

    await collection.delete_one({"_id": result.inserted_id})


async def test_event_schedule_as_list(
    db: AsyncDatabase[dict[str, Any]], event_data: dict[str, Any]
) -> None:
    collection = db["events"]

    result = await collection.insert_one(event_data)
    found = await collection.find_one({"_id": result.inserted_id})

    assert found is not None
    schedule = [EventScheduleEntry(**entry) for entry in found["schedule"]]

    assert len(schedule) == 2
    assert schedule[0].description == "Doors open"
    assert schedule[1].description == "Main act"

    await collection.delete_one({"_id": result.inserted_id})
