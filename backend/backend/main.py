import logging
from collections.abc import Sequence

import uvicorn

from .cli import parse_args


def cli(argv: Sequence[str] | None = None) -> None:
    cli_args = parse_args(argv)

    logging.basicConfig(
        format="[%(levelname)s][%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=cli_args.log_level,
    )

    logging.getLogger(__name__).info(
        "Starting Evently API on %s:%d", cli_args.host, cli_args.port
    )

    uvicorn.run(
        "backend.api:app",
        host=cli_args.host,
        port=cli_args.port,
        log_level=cli_args.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    cli()
