from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException

from backend.models.event import Event

GOOGLE_CALENDAR_EVENTS_URL = (
    "https://www.googleapis.com/calendar/v3/calendars/primary/events"
)


def google_calendar_location(event: Event) -> str:
    if event.is_online:
        return "Online"

    parts = [
        event.location.venue_name,
        event.location.address,
        (
            f"{event.location.city}, {event.location.state} {event.location.zip_code}"
        ).strip(),
    ]
    return ", ".join(part for part in parts if part)


def google_calendar_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def google_calendar_description(event: Event, event_url: str | None) -> str:
    parts = [event.about.strip()]
    if event_url:
        parts.append(f"View this event on Evently: {event_url}")
    return "\n\n".join(part for part in parts if part)


def google_calendar_event_payload(
    event: Event, *, event_url: str | None
) -> dict[str, object]:
    return {
        "summary": event.title,
        "description": google_calendar_description(event, event_url),
        "location": google_calendar_location(event),
        "start": {"dateTime": google_calendar_datetime(event.start_time)},
        "end": {"dateTime": google_calendar_datetime(event.end_time)},
    }


async def create_google_calendar_event(
    access_token: str, payload: dict[str, object]
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                GOOGLE_CALENDAR_EVENTS_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not reach Google Calendar.",
        ) from exc

    if response.status_code in {401, 403}:
        raise HTTPException(
            status_code=403,
            detail="Google Calendar rejected the request. Please sign in again.",
        )

    if not response.is_success:
        raise HTTPException(
            status_code=502,
            detail="Google Calendar could not create the event.",
        )

    try:
        body = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Google Calendar returned an invalid response.",
        ) from exc

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=502,
            detail="Google Calendar returned an invalid response.",
        )

    return body


async def delete_google_calendar_event(access_token: str, google_event_id: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{GOOGLE_CALENDAR_EVENTS_URL}/{google_event_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not reach Google Calendar.",
        ) from exc

    if response.status_code == 404:
        return

    if response.status_code in {401, 403}:
        raise HTTPException(
            status_code=403,
            detail="Google Calendar rejected the request. Please sign in again.",
        )

    if not response.is_success:
        raise HTTPException(
            status_code=502,
            detail="Google Calendar could not remove the event.",
        )
