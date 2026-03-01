from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from backend.models.event_favorite import EventFavorite


async def test_create_and_retrieve_event_favorite(
    db: AsyncDatabase[dict[str, Any]], event_favorite_data: dict[str, Any]
) -> None:
    collection = db["event_favorites"]

    result = await collection.insert_one(event_favorite_data)
    assert result.inserted_id is not None

    found = await collection.find_one({"_id": result.inserted_id})
    assert found is not None

    favorite = EventFavorite(**found)

    assert favorite.event_id == event_favorite_data["event_id"]
    assert favorite.user_id == event_favorite_data["user_id"]

    delete_result = await collection.delete_one({"_id": result.inserted_id})
    assert delete_result.deleted_count == 1

    gone = await collection.find_one({"_id": result.inserted_id})
    assert gone is None
