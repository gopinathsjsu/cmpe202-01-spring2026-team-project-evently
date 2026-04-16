import asyncio
import logging
from typing import Any, TypedDict

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.mongo_client import AsyncMongoClient

from backend.db.client import get_mongo_client
from backend.models.event import Event
from backend.services.notifications.arq import get_redis_settings
from backend.services.notifications.email import (
    EmailNotificationService,
    create_email_notification_service,
)


class Context(TypedDict):
    client: AsyncMongoClient[dict[str, Any]]
    db: AsyncDatabase[dict[str, Any]]
    email: EmailNotificationService


async def send_event_reminder(ctx: Context, event_id: int) -> None:
    user_ids = await ctx["db"]["attendance"].distinct("user_id", {"event_id": event_id})
    users = await ctx["db"]["users"].find({"id": {"$in": user_ids}}).to_list(None)
    event_dict = await ctx["db"]["events"].find_one({"id": event_id})
    event = Event.model_validate(event_dict) if event_dict else None
    if event is None:
        logging.getLogger(__name__).error(
            "Event with id %s not found for reminder job", event_id
        )
        return

    await asyncio.gather(
        *[ctx["email"].send_event_reminder(user["email"], event) for user in users]
    )


class WorkerSettings:
    functions = [send_event_reminder]
    redis_settings = get_redis_settings()

    @staticmethod
    async def on_startup(ctx: Context) -> None:
        client = get_mongo_client()
        ctx["client"] = client
        ctx["db"] = client["evently"]
        ctx["email"] = create_email_notification_service()

    @staticmethod
    async def on_shutdown(ctx: Context) -> None:
        await ctx["client"].close()


def run() -> None:
    import sys

    from arq.cli import cli

    sys.argv = ["arq", "backend.services.notifications.worker.WorkerSettings"]
    cli()
