# Backend

## Environment Setup

### Required External Tools

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- [`just`](https://github.com/casey/just#packages)
- [`docker-compose`](https://docs.docker.com/compose/install/)

### Installing Python Dependencies

1. Run `uv sync --dev` from the `backend/` directory
2. Activate the virtual environment with `source ./.venv/bin/activate`

## Running the Backend

> [!TIP]
> See the available `just` recipes by running `just`

1. Run `just db` to start the database
2. Run `uv run backend` to start the backend

Alternatively, you can run `just dev`

## CI

> [!TIP]
> See the available `uv run` subcommands by running `uv run`

- run tests with `uv run pytest`
- run type-checking with `uv run mypy`
- run the linter with `uv run ruff check`
- run the formatter with `uv ruff format`
