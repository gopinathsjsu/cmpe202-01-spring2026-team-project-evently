# Backend

## Environment Setup

### Environment Variables

The backend requires the following environment variables to be set:

| Variable       | Description                 | Example                                    |
| -------------- | --------------------------- | ------------------------------------------ |
| `DB_USERNAME`  | MongoDB root username       | `admin`                                    |
| `DB_PASSWORD`  | MongoDB root password       | `password`                                 |
| `DATABASE_URL` | Full MongoDB connection URL | `mongodb://admin:password@localhost:27017` |

**Setup:**

1. Copy `.env.example` to `.env` with `cp .env.example .env`
2. Edit `.env` with your desired credentials
3. Source the environment file before running commands with `source .env`

### Required External Tools

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- [`just`](https://github.com/casey/just#packages)
- [Docker (with Compose v2: `docker compose`)](https://docs.docker.com/get-docker/)

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
