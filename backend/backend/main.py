import asyncio
import logging
from collections.abc import Sequence
from typing import Any

from pymongo.asynchronous.database import AsyncDatabase
from pymongo.asynchronous.mongo_client import AsyncMongoClient

from .cli import parse_args


async def main(argv: Sequence[str] | None = None) -> None:
    cli_args = parse_args(argv)

    logging.basicConfig(
        format="[%(levelname)s][%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=cli_args.log_level,
    )

    logging.getLogger(__name__).info("Evently backend starting...")

    db_client: AsyncMongoClient[
        dict[str, Any]
    ]  # placeholder type hint until we settle on data models
    async with AsyncMongoClient(cli_args.database_url) as db_client:
        logging.getLogger(__name__).debug("Pinging MongoDB...")
        await db_client.admin.command("ping")

        db: AsyncDatabase[dict[str, Any]] = db_client["evently"]
        logging.getLogger(__name__).debug("Database obtained...")

        logging.getLogger(__name__).debug(
            "Current collection names: %s", await db.list_collection_names()
        )

    logging.getLogger(__name__).info("Exiting...")


def cli(argv: Sequence[str] | None = None) -> None:
    asyncio.run(main(argv))


if __name__ == "__main__":
    # change to trigger ci
    cli()
