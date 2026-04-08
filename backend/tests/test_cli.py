import os

from backend.cli import parse_args
from backend.main import cli


def test_parse_args_accepts_database_url_override(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    parsed = parse_args(["--database-url", "mongodb://override", "--port", "9000"])

    assert parsed.database_url == "mongodb://override"
    assert parsed.port == 9000


def test_parse_args_prefers_explicit_database_url_over_env(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "mongodb://from-env")

    parsed = parse_args(["--database-url", "mongodb://from-cli"])

    assert parsed.database_url == "mongodb://from-cli"


def test_cli_sets_database_url_before_starting_server(monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def fake_run(app: str, *, host: str, port: int, log_level: str, reload: bool) -> None:
        recorded["app"] = app
        recorded["host"] = host
        recorded["port"] = port
        recorded["log_level"] = log_level
        recorded["reload"] = reload
        recorded["database_url"] = os.environ.get("DATABASE_URL")

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("backend.main.uvicorn.run", fake_run)

    cli(["--database-url", "mongodb://cli-db", "--port", "9001"])

    assert recorded == {
        "app": "backend.api:app",
        "host": "127.0.0.1",
        "port": 9001,
        "log_level": "info",
        "reload": False,
        "database_url": "mongodb://cli-db",
    }
