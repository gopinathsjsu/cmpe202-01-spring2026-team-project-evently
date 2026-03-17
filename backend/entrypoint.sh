#!/bin/sh
set -e

# build the mongodb container url
if [ -n "${DB_USERNAME:-}" ] && [ -n "${DB_PASSWORD:-}" ]; then
    export DATABASE_URL="mongodb://${DB_USERNAME}:${DB_PASSWORD}@${MONGODB_HOST:-mongodb}:${MONGODB_PORT:-27017}"
fi

echo "Seeding database (skips if already seeded)..."
uv run python -m backend.seed

echo "Starting backend server..."
exec uv run backend --host 0.0.0.0
