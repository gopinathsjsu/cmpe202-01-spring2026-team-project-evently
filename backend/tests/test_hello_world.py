from typing import Any

from pymongo.asynchronous.database import AsyncDatabase


async def test_hello_world(db: AsyncDatabase[dict[str, Any]]) -> None:
    """Insert a 'Hello World' document, verify it exists, then remove it."""
    collection = db["greetings"]

    result = await collection.insert_one({"message": "Hello World"})
    assert result.inserted_id is not None

    found = await collection.find_one({"_id": result.inserted_id})
    assert found is not None
    assert found["message"] == "Hello World"

    delete_result = await collection.delete_one({"_id": result.inserted_id})
    assert delete_result.deleted_count == 1

    gone = await collection.find_one({"_id": result.inserted_id})
    assert gone is None
