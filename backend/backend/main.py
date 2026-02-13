import asyncio
import logging
from collections.abc import Sequence


async def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(
        format="[%(levelname)s][%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )

    logging.getLogger(__name__).info("Hello from backend!")
    logging.getLogger(__name__).info(
        "Received %s CLI arguments",
        (len(argv) - 1) if argv else 0,
    )


def cli(argv: Sequence[str] | None = None) -> None:
    asyncio.run(main(argv))


if __name__ == "__main__":
    cli()
