"""The Sea Temperature integration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CannotConnect,
    InvalidAuth,
    NoSeaData,
    SeaReading,
    async_get_cco_buoys,
    async_get_open_meteo,
    combine,
    nearest_buoy,
)
from .const import (
    BUOY_MAX_AGE,
    CONF_BUOY_MAX_KM,
    CONF_CCO_DOMAIN,
    CONF_CCO_KEY,
    DEFAULT_BUOY_MAX_KM,
    DOMAIN,
    UPDATE_INTERVAL,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type SeaTemperatureConfigEntry = ConfigEntry[SeaTemperatureCoordinator]


class SeaTemperatureCoordinator(DataUpdateCoordinator[SeaReading]):
    """Fetches readings for one location."""

    config_entry: SeaTemperatureConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SeaTemperatureConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )
        self._latitude = entry.data[CONF_LATITUDE]
        self._longitude = entry.data[CONF_LONGITUDE]

    async def _async_update_data(self) -> SeaReading:
        session = async_get_clientsession(self.hass)

        model: SeaReading | None = None
        model_error: Exception | None = None
        try:
            model = await async_get_open_meteo(
                session, self._latitude, self._longitude, USER_AGENT
            )
        except (CannotConnect, NoSeaData) as err:
            model_error = err

        nearest = None
        options = self.config_entry.options
        if key := options.get(CONF_CCO_KEY):
            try:
                buoys = await async_get_cco_buoys(
                    session, key, options.get(CONF_CCO_DOMAIN, ""), USER_AGENT
                )
                nearest = nearest_buoy(
                    buoys,
                    self._latitude,
                    self._longitude,
                    options.get(CONF_BUOY_MAX_KM, DEFAULT_BUOY_MAX_KM),
                    BUOY_MAX_AGE,
                    datetime.now(timezone.utc),
                )
            except InvalidAuth:
                _LOGGER.warning(
                    "The buoy API key or domain was rejected; using the model only. "
                    "Check them in the integration options"
                )
            except CannotConnect as err:
                _LOGGER.debug("Buoy data unavailable, using the model: %s", err)

        reading = combine(model, nearest)
        if reading is None:
            raise UpdateFailed(str(model_error))
        return reading


async def async_setup_entry(hass: HomeAssistant, entry: SeaTemperatureConfigEntry) -> bool:
    """Set up a location from a config entry."""
    coordinator = SeaTemperatureCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: SeaTemperatureConfigEntry) -> None:
    """Reload so new buoy options take effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SeaTemperatureConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
