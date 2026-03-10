set dotenv-load

# List available recipes
default:
    @just --list

# ── Full-stack (Docker Compose) ──────────────────────────────────────

# Start the full stack (MongoDB + backend + frontend)
up *args:
    docker compose up --build {{args}}

# Start the full stack in the background
up-d:
    docker compose up --build -d

# Stop the full stack
down *args:
    docker compose down {{args}}

# Stop the full stack and wipe the database volume
reset:
    docker compose down -v

# View service logs (optionally pass a service name: just logs backend)
logs *args:
    docker compose logs -f {{args}}

# ── Individual services for local development ────────────────────────

# Start only MongoDB (prerequisite for local backend development)
db:
    docker compose up -d mongodb

# Stop MongoDB
db-stop:
    docker compose stop mongodb

# Start backend in local dev mode (MongoDB + seed + server with hot reload)
backend:
    cd backend && just dev

# Start frontend in local dev mode (requires backend running)
frontend:
    cd frontend && pnpm dev
