from typing import Any, TypedDict

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.mongo_client import AsyncMongoClient

from backend.db.client import get_mongo_client
from backend.services.notifications.arq import get_redis_settings


class Context(TypedDict):
    client: AsyncMongoClient[dict[str, Any]]
    db: AsyncDatabase[dict[str, Any]]


async def send_event_reminder(ctx: Context, event_id: str) -> None:
    # TODO: implement this
    print(f"sending event reminder for event id {event_id}")


class WorkerSettings:
    functions = [send_event_reminder]
    redis_settings = get_redis_settings()

    @staticmethod
    async def on_startup(ctx: Context) -> None:
        client = get_mongo_client()
        ctx["client"] = client
        ctx["db"] = client["evently"]

    @staticmethod
    async def on_shutdown(ctx: Context) -> None:
        await ctx["client"].close()


def run() -> None:
    import sys

    from arq.cli import cli

    sys.argv = ["arq", "backend.services.notifications.worker.WorkerSettings"]
    cli()
