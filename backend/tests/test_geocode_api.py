import os
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("SESSION_SECRET_KEY", "test-secret")

from backend.api import create_app
from backend.routes import geocode as geocode_routes
from backend.routes.auth import AuthSessionUser, require_authenticated_user


def _auth_user() -> AuthSessionUser:
    return AuthSessionUser(
        id=7,
        email="organizer@example.com",
        first_name="Event",
        last_name="Organizer",
        name="Event Organizer",
        roles=["user"],
    )


def _make_client() -> AsyncClient:
    app = create_app()
    app.dependency_overrides[require_authenticated_user] = _auth_user
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_geocode_address_returns_first_nominatim_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_params: dict[str, str] = {}

    async def fake_search_nominatim(params: dict[str, str]) -> list[dict[str, Any]]:
        captured_params.update(params)
        return [
            {
                "lat": "37.3351874",
                "lon": "-121.8810715",
                "display_name": "1 Washington Sq, San Jose, CA 95192",
            }
        ]

    monkeypatch.setattr(geocode_routes, "_search_nominatim", fake_search_nominatim)

    async with _make_client() as client:
        resp = await client.get(
            "/geocode/",
            params={
                "street": " 1 Washington Sq ",
                "city": " San Jose ",
                "state": " CA ",
                "postalcode": " 95192 ",
            },
        )

    assert resp.status_code == 200
    assert resp.json() == {
        "latitude": 37.3351874,
        "longitude": -121.8810715,
        "display_name": "1 Washington Sq, San Jose, CA 95192",
    }
    assert captured_params == {
        "street": "1 Washington Sq",
        "city": "San Jose",
        "state": "CA",
        "postalcode": "95192",
        "country": "United States",
        "countrycodes": "us",
        "format": "jsonv2",
        "addressdetails": "1",
        "limit": "1",
    }


@pytest.mark.asyncio
async def test_geocode_address_returns_404_when_address_cannot_be_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_search_nominatim(_params: dict[str, str]) -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(geocode_routes, "_search_nominatim", fake_search_nominatim)

    async with _make_client() as client:
        resp = await client.get(
            "/geocode/",
            params={
                "street": "Missing Place",
                "city": "San Jose",
                "state": "CA",
                "postalcode": "95192",
            },
        )

    assert resp.status_code == 404
    assert (
        resp.json()["detail"] == "Address not found. Please check the location details."
    )
