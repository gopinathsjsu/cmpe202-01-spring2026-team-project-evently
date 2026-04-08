from backend.cli import parse_args


def test_parse_args_accepts_database_url_override(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    parsed = parse_args(["--database-url", "mongodb://override", "--port", "9000"])

    assert parsed.database_url == "mongodb://override"
    assert parsed.port == 9000


def test_parse_args_prefers_explicit_database_url_over_env(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "mongodb://from-env")

    parsed = parse_args(["--database-url", "mongodb://from-cli"])

    assert parsed.database_url == "mongodb://from-cli"
