"""Clients for the data sources used by Sea Temperature.

Kept free of Home Assistant imports so it can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

import aiohttp

OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

_CURRENT_FIELDS = "sea_surface_temperature,wave_height,wave_period,wave_direction"
_TIMEOUT = aiohttp.ClientTimeout(total=20)


class SeaTemperatureError(Exception):
    """Base error."""


class CannotConnect(SeaTemperatureError):
    """The service could not be reached."""


class NoSeaData(SeaTemperatureError):
    """The service has no sea data for this point (e.g. it is inland)."""


@dataclass
class SeaReading:
    """A single reading for a location."""

    source: str
    observed_at: datetime
    temperature: float
    wave_height: float | None
    wave_period: float | None
    wave_direction: float | None
    grid_latitude: float
    grid_longitude: float
    distance_km: float


@dataclass
class Place:
    """A search result."""

    name: str
    latitude: float
    longitude: float
    kind: str


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    p1, p2 = radians(lat1), radians(lat2)
    dlat, dlon = p2 - p1, radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(a))


async def async_get_open_meteo(
    session: aiohttp.ClientSession, latitude: float, longitude: float, user_agent: str
) -> SeaReading:
    """Fetch the current modelled sea conditions from Open-Meteo."""
    params = {
        "latitude": f"{latitude:.4f}",
        "longitude": f"{longitude:.4f}",
        "current": _CURRENT_FIELDS,
        "timezone": "GMT",
        "cell_selection": "sea",
    }
    try:
        async with session.get(
            OPEN_METEO_MARINE_URL,
            params=params,
            headers={"User-Agent": user_agent},
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise CannotConnect(str(err)) from err

    current = data.get("current") or {}
    temperature = current.get("sea_surface_temperature")
    if temperature is None:
        raise NoSeaData("Open-Meteo has no sea temperature for this point")

    grid_lat = float(data["latitude"])
    grid_lon = float(data["longitude"])
    observed = datetime.fromisoformat(current["time"]).replace(tzinfo=timezone.utc)

    return SeaReading(
        source="Open-Meteo Marine (model)",
        observed_at=observed,
        temperature=float(temperature),
        wave_height=current.get("wave_height"),
        wave_period=current.get("wave_period"),
        wave_direction=current.get("wave_direction"),
        grid_latitude=grid_lat,
        grid_longitude=grid_lon,
        distance_km=round(distance_km(latitude, longitude, grid_lat, grid_lon), 1),
    )


async def async_search_places(
    session: aiohttp.ClientSession, query: str, user_agent: str
) -> list[Place]:
    """Search OpenStreetMap for places, preferring beaches."""
    params = {"q": query, "format": "jsonv2", "limit": "15"}
    try:
        async with session.get(
            NOMINATIM_URL,
            params=params,
            headers={"User-Agent": user_agent},
            timeout=_TIMEOUT,
        ) as resp:
            resp.raise_for_status()
            rows = await resp.json()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise CannotConnect(str(err)) from err

    places = [
        Place(
            name=row["display_name"],
            latitude=float(row["lat"]),
            longitude=float(row["lon"]),
            kind=row.get("type", ""),
        )
        for row in rows
    ]
    # Beaches first, keeping Nominatim's relevance order within each group.
    places.sort(key=lambda p: p.kind != "beach")
    return places
