"""Config flow: find a beach by name, or drop a pin on the map."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    LocationSelector,
    LocationSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .api import CannotConnect, NoSeaData, Place, async_get_open_meteo, async_search_places
from .const import CONF_LOCATION_NAME, DOMAIN, MAX_GRID_DISTANCE_KM, USER_AGENT

CONF_QUERY = "query"
CONF_PLACE = "place"
CONF_LOCATION = "location"


class SeaTemperatureConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle adding a sea location."""

    VERSION = 1

    def __init__(self) -> None:
        self._places: list[Place] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose how to pick the location."""
        return self.async_show_menu(step_id="user", menu_options=["search", "map"])

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Search for a beach or place by name."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._places = await async_search_places(
                    async_get_clientsession(self.hass), user_input[CONF_QUERY], USER_AGENT
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                if self._places:
                    return await self.async_step_pick()
                errors["base"] = "no_results"

        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema({vol.Required(CONF_QUERY): TextSelector()}),
            errors=errors,
        )

    async def async_step_pick(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick one of the search results."""
        errors: dict[str, str] = {}
        if user_input is not None:
            place = self._places[int(user_input[CONF_PLACE])]
            name = place.name.split(",")[0].strip()
            errors = await self._validate(place.latitude, place.longitude)
            if not errors:
                return await self._create(name, place.latitude, place.longitude)

        options = [
            {"value": str(i), "label": _label(place)} for i, place in enumerate(self._places)
        ]
        return self.async_show_form(
            step_id="pick",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PLACE): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_map(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Drop a pin on a map."""
        errors: dict[str, str] = {}
        if user_input is not None:
            lat = user_input[CONF_LOCATION][CONF_LATITUDE]
            lon = user_input[CONF_LOCATION][CONF_LONGITUDE]
            errors = await self._validate(lat, lon)
            if not errors:
                return await self._create(user_input[CONF_LOCATION_NAME], lat, lon)

        default = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }
        return self.async_show_form(
            step_id="map",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION_NAME): TextSelector(),
                    vol.Required(CONF_LOCATION, default=default): LocationSelector(
                        LocationSelectorConfig(radius=False)
                    ),
                }
            ),
            errors=errors,
        )

    async def _validate(self, lat: float, lon: float) -> dict[str, str]:
        """Check the point gets a usable reading."""
        try:
            reading = await async_get_open_meteo(
                async_get_clientsession(self.hass), lat, lon, USER_AGENT
            )
        except CannotConnect:
            return {"base": "cannot_connect"}
        except NoSeaData:
            return {"base": "no_sea_data"}
        if reading.distance_km > MAX_GRID_DISTANCE_KM:
            return {"base": "too_far_from_sea"}
        return {}

    async def _create(self, name: str, lat: float, lon: float) -> ConfigFlowResult:
        await self.async_set_unique_id(f"{lat:.3f}_{lon:.3f}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=name, data={CONF_LATITUDE: lat, CONF_LONGITUDE: lon}
        )


def _label(place: Place) -> str:
    """Readable one-line label for a search result."""
    parts = [p.strip() for p in place.name.split(",")]
    label = ", ".join(parts[:1] + parts[-3:]) if len(parts) > 4 else place.name
    return f"{'🏖 ' if place.kind == 'beach' else ''}{label}"
