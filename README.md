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

The only prerequisite is [Docker](https://docs.docker.com/get-docker/). From the project root:

```bash
docker compose up --build
```

This starts MongoDB, the FastAPI backend (with sample data), and the Next.js frontend in one command:

| Service  | URL                        |
|----------|----------------------------|
| Frontend | http://localhost:3000       |
| Backend  | http://localhost:8000       |
| MongoDB  | mongodb://localhost:27017   |

To stop everything: `docker compose down`

To stop and wipe the database: `docker compose down -v`

## Architecture

Below is the architecture diagram for the Evently system:
- ![Architecture Diagram](diagrams/architecture.png)

[![Assignment Link](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/xRTHk3Dv)

## Team Members

- Lucas Nguyen
- Wyatt Avilla
- Prajakta Jivanrao Ketkar
- Matthew Bernard
