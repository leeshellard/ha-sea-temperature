"""The Sea Temperature integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, NoSeaData, SeaReading, async_get_open_meteo
from .const import DOMAIN, UPDATE_INTERVAL, USER_AGENT

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
        try:
            return await async_get_open_meteo(
                session, self._latitude, self._longitude, USER_AGENT
            )
        except (CannotConnect, NoSeaData) as err:
            raise UpdateFailed(str(err)) from err


async def async_setup_entry(hass: HomeAssistant, entry: SeaTemperatureConfigEntry) -> bool:
    """Set up a location from a config entry."""
    coordinator = SeaTemperatureCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SeaTemperatureConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
