set dotenv-load

# List available recipes
default:
    @just --list

# ── Full-stack (Docker Compose) ──────────────────────────────────────

# Start the full stack (MongoDB + Redis + backend + notification worker + frontend)
up *args: _stop-dev-db
    docker compose up --build {{args}}

# Start the full stack in the background
up-d: _stop-dev-db
    docker compose up --build -d

# Stop the full stack
down *args:
    docker compose down {{args}}
    @docker compose -f backend/docker-compose.yml down 2>/dev/null || true

# Stop the full stack and wipe the database volume
reset:
    docker compose down -v
    @docker compose -f backend/docker-compose.yml down -v 2>/dev/null || true

# View service logs (optionally pass a service name: just logs backend)
logs *args:
    docker compose logs -f {{args}}

# ── Individual services for local development ────────────────────────

# Start only MongoDB and Redis (prerequisites for local backend development)
db: _stop-dev-db
    docker compose up -d mongodb redis

# Stop MongoDB and Redis
db-stop:
    docker compose stop mongodb redis
    @docker compose -f backend/docker-compose.yml down 2>/dev/null || true

# Start backend in local dev mode (MongoDB + Redis + seed + server + notification worker)
backend:
    cd backend && just dev

# Start notification worker in local dev mode
worker:
    cd backend && just worker

# Start frontend in local dev mode (requires backend running)
frontend:
    cd frontend && pnpm dev

# ── Helpers ────────────────────────────────────────────────────────────

[private]
_stop-dev-db:
    @docker compose -f backend/docker-compose.yml down 2>/dev/null || true
