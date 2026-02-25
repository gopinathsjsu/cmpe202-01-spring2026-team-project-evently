from typing import Any

from pymongo.asynchronous.database import AsyncDatabase

from backend.models.ticket import Ticket


async def test_create_and_retrieve_ticket(
    db: AsyncDatabase[dict[str, Any]], ticket_data: dict[str, Any]
) -> None:
    collection = db["tickets"]

    result = await collection.insert_one(ticket_data)
    assert result.inserted_id is not None

    found = await collection.find_one({"_id": result.inserted_id})
    assert found is not None

    ticket = Ticket(**found)

    assert ticket.id == ticket_data["id"]
    assert ticket.event_id == ticket_data["event_id"]
    assert ticket.attendee_id == ticket_data["attendee_id"]
    assert ticket.price == ticket_data["price"]
    assert ticket.purchase_time == ticket_data["purchase_time"]

    delete_result = await collection.delete_one({"_id": result.inserted_id})
    assert delete_result.deleted_count == 1

    gone = await collection.find_one({"_id": result.inserted_id})
    assert gone is None
