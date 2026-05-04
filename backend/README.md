# Backend

## Environment Setup

### Environment Variables

The backend requires the following environment variables to be set:

| Variable                | Description                           | Example                                    |
| ----------------------- | ------------------------------------- | ------------------------------------------ |
| `DB_USERNAME`           | MongoDB root username                 | `admin`                                    |
| `DB_PASSWORD`           | MongoDB root password                 | `password`                                 |
| `DATABASE_URL`          | Full MongoDB connection URL           | `mongodb://admin:password@localhost:27017` |
| `REDIS_URL`             | Full Redis connection URL             | `redis://localhost:6379/0`                 |
| `RESEND_API_KEY`        | Resend API Key                        | `1234SEND`                                 |
| `NOMINATIM_USER_AGENT`  | Identifies Evently geocoding requests | `Evently/1.0 (team@example.com)`           |

**Setup:**

1. Copy `.env.example` to `.env` with `cp .env.example .env`
2. Edit `.env` with your desired credentials

> Both `just` and Docker Compose read `.env` directly. No manual `source .env` step is needed.

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

1. Run `just db` to start MongoDB and Redis
2. Run `uv run backend` to start the backend
3. Run `uv run notif-worker` in another terminal to start the notification worker

Alternatively, you can run `just dev` to start MongoDB, Redis, the backend, and the notification worker together.

## Seed Data

The seed command loads sample users, events, attendance, favorites, and compact SVG event banners from `backend/uploads/seed-events`.
Run `just seed` to drop and reseed local data.

If you edit the seeded event image set, regenerate the assets from the project root with:

```bash
just seed-images
```

## CI

> [!TIP]
> See the available `uv run` subcommands by running `uv run`

- run tests with `uv run pytest`
- run type-checking with `uv run mypy`
- run the linter with `uv run ruff check`
- run the formatter with `uv run ruff format`
