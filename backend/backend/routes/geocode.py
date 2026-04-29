import os
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.routes.auth import AuthSessionUser, require_authenticated_user

router = APIRouter()

AuthUserDep = Annotated[AuthSessionUser, Depends(require_authenticated_user)]

NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_USER_AGENT = (
    "Evently/1.0 "
    "(https://github.com/gopinathsjsu/cmpe202-01-spring2026-team-project-evently)"
)


class GeocodeResult(BaseModel):
    latitude: float
    longitude: float
    display_name: str | None = None


def _clean_required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=422, detail=f"{field_name} is required")
    return cleaned


async def _search_nominatim(params: dict[str, str]) -> list[dict[str, Any]]:
    user_agent = os.getenv("NOMINATIM_USER_AGENT", DEFAULT_USER_AGENT).strip()
    headers = {
        "Accept": "application/json",
        "User-Agent": user_agent or DEFAULT_USER_AGENT,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            response = await client.get(NOMINATIM_SEARCH_URL, params=params)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 429:
            detail = "Geocoding service rate limit reached. Please try again shortly."
            raise HTTPException(status_code=503, detail=detail) from exc
        raise HTTPException(status_code=502, detail="Geocoding service failed") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Geocoding service failed") from exc

    data = response.json()
    if not isinstance(data, list):
        raise HTTPException(status_code=502, detail="Invalid geocoding response")

    return [item for item in data if isinstance(item, dict)]


def _result_from_place(place: dict[str, Any]) -> GeocodeResult | None:
    latitude_raw = place.get("lat")
    longitude_raw = place.get("lon")
    if not isinstance(latitude_raw, str) or not isinstance(longitude_raw, str):
        return None

    try:
        latitude = float(latitude_raw)
        longitude = float(longitude_raw)
    except ValueError:
        return None

    display_name = place.get("display_name")
    return GeocodeResult(
        latitude=latitude,
        longitude=longitude,
        display_name=display_name if isinstance(display_name, str) else None,
    )


@router.get("/", response_model=GeocodeResult)
async def geocode_address(
    _current_user: AuthUserDep,
    street: Annotated[str, Query(min_length=1)],
    city: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
    postalcode: Annotated[str, Query(min_length=1)],
) -> GeocodeResult:
    """Resolve a user-entered event address to coordinates."""
    params = {
        "street": _clean_required(street, "Street address"),
        "city": _clean_required(city, "City"),
        "state": _clean_required(state, "State"),
        "postalcode": _clean_required(postalcode, "ZIP code"),
        "country": "United States",
        "countrycodes": "us",
        "format": "jsonv2",
        "addressdetails": "1",
        "limit": "1",
    }

    for place in await _search_nominatim(params):
        if result := _result_from_place(place):
            return result

    raise HTTPException(
        status_code=404,
        detail="Address not found. Please check the location details.",
    )
