"""Clients for the data sources used by Sea Temperature.

Kept free of Home Assistant imports so it can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

import aiohttp

OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
CCO_WAVES_URL = "https://coastalmonitoring.org/observations/waves/latest.geojson"

_CURRENT_FIELDS = "sea_surface_temperature,wave_height,wave_period,wave_direction"
_TIMEOUT = aiohttp.ClientTimeout(total=20)


class SeaTemperatureError(Exception):
    """Base error."""


class CannotConnect(SeaTemperatureError):
    """The service could not be reached."""


class NoSeaData(SeaTemperatureError):
    """The service has no sea data for this point (e.g. it is inland)."""


class InvalidAuth(SeaTemperatureError):
    """The buoy service rejected the API key or domain."""


@dataclass
class SeaReading:
    """A single reading for a location."""

    source: str
    observed_at: datetime
    temperature: float
    wave_height: float | None
    wave_period: float | None
    wave_direction: float | None
    # Model grid point actually used (None if only a buoy was available).
    grid_latitude: float | None = None
    grid_longitude: float | None = None
    distance_km: float | None = None
    # Set when a measured buoy reading was used.
    station: str | None = None
    station_distance_km: float | None = None
    model_temperature: float | None = None


@dataclass
class Buoy:
    """A buoy's latest observation."""

    name: str
    latitude: float
    longitude: float
    observed_at: datetime
    temperature: float
    wave_height: float | None
    wave_period: float | None
    wave_direction: float | None


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


def _float(value: str | float | None) -> float | None:
    """Parse the buoy API's string numbers, treating blanks as missing."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def async_get_cco_buoys(
    session: aiohttp.ClientSession, api_key: str, domain: str, user_agent: str
) -> list[Buoy]:
    """Fetch the latest observation from every Regional Coastal Monitoring wave buoy.

    Only buoys that currently report a sea temperature are returned.
    """
    headers = {
        "X-API-Key": api_key,
        "Referer": f"https://{domain}/",
        "User-Agent": user_agent,
        "Accept": "application/json",
    }
    try:
        async with session.get(CCO_WAVES_URL, headers=headers, timeout=_TIMEOUT) as resp:
            if resp.status in (401, 403):
                raise InvalidAuth(f"HTTP {resp.status}")
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise CannotConnect(str(err)) from err

    buoys: list[Buoy] = []
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        temperature = _float(props.get("sst"))
        lat = _float(props.get("gps_latitude"))
        lon = _float(props.get("gps_longitude"))
        stamp = props.get("date")
        if temperature is None or lat is None or lon is None or not stamp:
            continue
        try:
            observed = datetime.strptime(stamp, "%Y%m%d#%H%M%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
        buoys.append(
            Buoy(
                name=props.get("sensor") or "Unknown buoy",
                latitude=lat,
                longitude=lon,
                observed_at=observed,
                temperature=temperature,
                wave_height=_float(props.get("hs")),
                wave_period=_float(props.get("tp")),
                wave_direction=_float(props.get("pdir")),
            )
        )
    return buoys


def nearest_buoy(
    buoys: list[Buoy],
    latitude: float,
    longitude: float,
    max_km: float,
    max_age: timedelta,
    now: datetime,
) -> tuple[Buoy, float] | None:
    """Closest recent buoy within max_km, with its distance, or None."""
    candidates = [
        (b, distance_km(latitude, longitude, b.latitude, b.longitude))
        for b in buoys
        if now - b.observed_at <= max_age
    ]
    candidates = [(b, d) for b, d in candidates if d <= max_km]
    if not candidates:
        return None
    buoy, dist = min(candidates, key=lambda c: c[1])
    return buoy, round(dist, 1)


def combine(
    model: SeaReading | None, nearest: tuple[Buoy, float] | None
) -> SeaReading | None:
    """Prefer the measured buoy temperature, filling the gaps from the model."""
    if nearest is None:
        return model
    buoy, dist = nearest

    def pick(measured: float | None, modelled: float | None) -> float | None:
        return measured if measured is not None else modelled

    return SeaReading(
        source=f"Buoy: {buoy.name} (measured)",
        observed_at=buoy.observed_at,
        temperature=buoy.temperature,
        wave_height=pick(buoy.wave_height, model.wave_height if model else None),
        wave_period=pick(buoy.wave_period, model.wave_period if model else None),
        wave_direction=pick(buoy.wave_direction, model.wave_direction if model else None),
        grid_latitude=model.grid_latitude if model else None,
        grid_longitude=model.grid_longitude if model else None,
        distance_km=model.distance_km if model else None,
        station=buoy.name,
        station_distance_km=dist,
        model_temperature=model.temperature if model else None,
    )
