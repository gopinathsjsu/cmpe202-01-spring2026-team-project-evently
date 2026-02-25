from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(slots=True)
class CommandLineArguments:
    database_url: str
    log_level: str
    host: str
    port: int


def parse_args(argv: Sequence[str] | None = None) -> CommandLineArguments:
    parser = argparse.ArgumentParser(
        description="Evently Backend Command Line Interface",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        required=(env_db_url := os.getenv("DATABASE_URL")) is None or env_db_url == "",
        help="URL for the database. Takes priority over the `DATABASE_URL` environment variable. Required if DATABASE_URL is not set.",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=("critical", "error", "warning", "info", "debug"),
        help="Logging verbosity. Defaults to info.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the server to. Defaults to 127.0.0.1.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to. Defaults to 8000.",
    )

    args = parser.parse_args(argv)

    return CommandLineArguments(
        database_url=args.database_url,
        log_level=args.log_level.upper(),
        host=args.host,
        port=args.port,
    )
