# Backend

## Environment Setup

1. Make sure you have [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed
2. Run `uv sync --dev` from the `backend/` directory
3. Activate the virtual environment with `source ./.venv/bin/activate`

## Running the Backend

```sh
uv run backend
```

## CI

- run tests with `uv run pytest`
- run type-checking with `uv run mypy`
- run the linter with `uv run ruff check`
- run the formatter with `uv ruff format`
