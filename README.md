# Evently

Evently is a platform that allows users to create, discover, manage events.
This system supports role-based access control, event moderation, ticketing, calendar integration, notifications, and UI for web.
User Roles:
1. **Attendee**
    - Register / Login
    - Browse & search events
    - View event details
    - RSVP / Book tickets
    - Receive confirmations
    - Add event to calendar

2. **Organizer**
    - Create events
    - Upload event details
    - Manage attendees

3. **Admin**
    - Review events
    - Approve / Reject events

## Quick Start

Prerequisites: [Docker](https://docs.docker.com/get-docker/) and (optionally) [`just`](https://github.com/casey/just#packages) for convenience commands.

**1. Create a `.env` file** from the template:

```bash
cp .env.example .env   # then edit credentials if desired
```

**2. Start the full stack:**

```bash
just up          # or: docker compose up --build
```

This starts MongoDB, the FastAPI backend (with sample data), and the Next.js frontend:

| Service  | URL                        |
|----------|----------------------------|
| Frontend | http://localhost:3000       |
| Backend  | http://localhost:8000       |
| MongoDB  | mongodb://localhost:27017   |

**3. Stop / reset:**

```bash
just down        # stop all services
just reset       # stop and wipe the database volume
```

## Local Development

For development with hot reloading, run services outside Docker. Additional prerequisites: [`uv`](https://docs.astral.sh/uv/), [`pnpm`](https://pnpm.io/installation), and [`just`](https://github.com/casey/just#packages).

```bash
# Terminal 1 — start MongoDB + seed + backend (from project root)
just backend

# Terminal 2 — start the frontend (from project root)
just frontend
```

Run `just` with no arguments to see all available commands.

## Architecture

Below is the architecture diagram for the Evently system:
- ![Architecture Diagram](diagrams/architecture.png)

[![Assignment Link](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/xRTHk3Dv)

## Team Members

- Lucas Nguyen
- Wyatt Avilla
- Prajakta Jivanrao Ketkar
- Matthew Bernard
