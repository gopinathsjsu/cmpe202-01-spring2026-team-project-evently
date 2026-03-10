#!/bin/sh
set -e

echo "Seeding database (skips if already seeded)..."
uv run python -m backend.seed

echo "Starting backend server..."
exec uv run backend --host 0.0.0.0
