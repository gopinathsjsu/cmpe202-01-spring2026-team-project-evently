from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from backend.models.user import GlobalRole, User, UserProfile


async def test_create_and_retrieve_user(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    collection = db["users"]

    result = await collection.insert_one(user_data)
    assert result.inserted_id is not None

    found = await collection.find_one({"_id": result.inserted_id})
    assert found is not None

    user = User(**found)

    assert user.id == user_data["id"]
    assert user.username == user_data["username"]
    assert user.first_name == user_data["first_name"]
    assert user.last_name == user_data["last_name"]
    assert user.email == user_data["email"]
    assert user.phone_number == user_data["phone_number"]
    assert GlobalRole.User in user.roles
    assert user.profile.bio == user_data["profile"]["bio"]
    assert user.profile.location == user_data["profile"]["location"]
    assert user.profile.interests == user_data["profile"]["interests"]

    delete_result = await collection.delete_one({"_id": result.inserted_id})
    assert delete_result.deleted_count == 1

    gone = await collection.find_one({"_id": result.inserted_id})
    assert gone is None


async def test_user_profile_as_subdocument(
    db: AsyncDatabase[dict[str, Any]], user_data: dict[str, Any]
) -> None:
    collection = db["users"]

    result = await collection.insert_one(user_data)
    found = await collection.find_one({"_id": result.inserted_id})

    assert found is not None
    profile_data = found["profile"]
    profile = UserProfile(**profile_data)

    assert profile.bio == "Test bio"
    assert profile.twitter_handle == "testuser"
    assert profile.instagram_handle == "testuser"
    assert profile.interests == ["music", "tech"]

    await collection.delete_one({"_id": result.inserted_id})
