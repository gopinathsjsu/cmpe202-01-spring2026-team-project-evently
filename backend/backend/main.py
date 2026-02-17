import asyncio
import logging
from collections.abc import Sequence

from .clap import parse_args


async def main(argv: Sequence[str] | None = None) -> None:
    cli_args = parse_args(argv)

    logging.basicConfig(
        format="[%(levelname)s][%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=cli_args.log_level,
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
