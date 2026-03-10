#!/bin/sh
set -e

echo "Seeding database..."
uv run python -m backend.seed

echo "Starting backend server..."
exec uv run backend --host 0.0.0.0
