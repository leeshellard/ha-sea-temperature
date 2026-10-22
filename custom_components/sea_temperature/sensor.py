"""Sensors for Sea Temperature."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength, UnitOfTemperature, UnitOfTime, DEGREE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SeaTemperatureConfigEntry, SeaTemperatureCoordinator
from .api import SeaReading
from .const import DOMAIN, WARN_GRID_DISTANCE_KM


@dataclass(frozen=True, kw_only=True)
class SeaSensorDescription(SensorEntityDescription):
    """Describes a sea sensor."""

    value_fn: Callable[[SeaReading], float | str | datetime | None]


# Upper temperature bound (°C) for each band, tuned for UK/N. European waters.
SWIM_BANDS: tuple[tuple[float, str], ...] = (
    (10.0, "very_cold"),
    (14.0, "cold"),
    (17.0, "fresh"),
    (20.0, "comfortable"),
)
SWIM_OPTIONS = [band for _, band in SWIM_BANDS] + ["warm"]
ROUGH_WATER_WAVE_HEIGHT_M = 1.5


# Douglas sea scale: upper significant wave height (m) for each state.
SEA_STATE_BANDS: tuple[tuple[float, str], ...] = (
    (0.1, "calm"),
    (0.5, "smooth"),
    (1.25, "slight"),
    (2.5, "moderate"),
    (4.0, "rough"),
    (6.0, "very_rough"),
    (9.0, "high"),
    (14.0, "very_high"),
)
SEA_STATE_OPTIONS = [state for _, state in SEA_STATE_BANDS] + ["phenomenal"]
TIDE_KEYS = {"tide_state", "next_high_tide", "next_low_tide"}


def _sea_state(reading: SeaReading) -> str | None:
    if reading.wave_height is None:
        return None
    for upper, state in SEA_STATE_BANDS:
        if reading.wave_height < upper:
            return state
    return "phenomenal"


def _swim_comfort(reading: SeaReading) -> str:
    for upper, band in SWIM_BANDS:
        if reading.temperature < upper:
            return band
    return "warm"


SENSORS: tuple[SeaSensorDescription, ...] = (
    SeaSensorDescription(
        key="sea_temperature",
        translation_key="sea_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda r: r.temperature,
    ),
    SeaSensorDescription(
        key="swim_comfort",
        translation_key="swim_comfort",
        device_class=SensorDeviceClass.ENUM,
        options=SWIM_OPTIONS,
        value_fn=_swim_comfort,
    ),
    SeaSensorDescription(
        key="temperature_change",
        translation_key="temperature_change",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda r: r.temperature_change_24h,
    ),
    SeaSensorDescription(
        key="sea_state",
        translation_key="sea_state",
        device_class=SensorDeviceClass.ENUM,
        options=SEA_STATE_OPTIONS,
        value_fn=_sea_state,
    ),
    SeaSensorDescription(
        key="tide_state",
        translation_key="tide_state",
        device_class=SensorDeviceClass.ENUM,
        options=["rising", "falling"],
        value_fn=lambda r: r.tide.state if r.tide else None,
    ),
    SeaSensorDescription(
        key="next_high_tide",
        translation_key="next_high_tide",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda r: r.tide.next_high if r.tide else None,
    ),
    SeaSensorDescription(
        key="next_low_tide",
        translation_key="next_low_tide",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda r: r.tide.next_low if r.tide else None,
    ),
    SeaSensorDescription(
        key="wave_height",
        translation_key="wave_height",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda r: r.wave_height,
    ),
    SeaSensorDescription(
        key="wave_period",
        translation_key="wave_period",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.wave_period,
    ),
    SeaSensorDescription(
        key="wave_direction",
        translation_key="wave_direction",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.wave_direction,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SeaTemperatureConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for a location."""
    coordinator = entry.runtime_data
    async_add_entities(SeaSensor(coordinator, entry, d) for d in SENSORS)


class SeaSensor(CoordinatorEntity[SeaTemperatureCoordinator], SensorEntity):
    """A sensor for one reading at one location."""

    _attr_has_entity_name = True
    _attr_attribution = (
        "Model data from Open-Meteo.com. Buoy data, when enabled, is from the Regional "
        "Coastal Monitoring Programme under the Open Government Licence (real-time, "
        "not quality-controlled)."
    )
    entity_description: SeaSensorDescription

    def __init__(
        self,
        coordinator: SeaTemperatureCoordinator,
        entry: SeaTemperatureConfigEntry,
        description: SeaSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Open-Meteo / Regional Coastal Monitoring",
            model="Marine model and buoys",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        key = self.entity_description.key
        if key in TIDE_KEYS:
            attrs = {"source": data.tide.source if data.tide else None}
            if data.tide is not None:
                attrs["next_high_height_m"] = data.tide.next_high_height
                attrs["next_low_height_m"] = data.tide.next_low_height
            return attrs
        attrs: dict[str, Any] = {
            "source": data.source,
            "reading_time": data.observed_at.isoformat(),
        }
        if data.station is not None:
            attrs["buoy"] = data.station
            attrs["buoy_distance_km"] = data.station_distance_km
            attrs["model_temperature"] = data.model_temperature
        if data.distance_km is not None:
            attrs["grid_latitude"] = data.grid_latitude
            attrs["grid_longitude"] = data.grid_longitude
            attrs["distance_to_grid_point_km"] = data.distance_km
        if key == "temperature_change":
            attrs["note"] = "Change in the Open-Meteo modelled sea temperature over the last 24 hours."
        if key == "swim_comfort":
            attrs["temperature"] = data.temperature
            attrs["rough_water"] = (
                data.wave_height is not None
                and data.wave_height >= ROUGH_WATER_WAVE_HEIGHT_M
            )
            attrs["note"] = (
                "Based on sea temperature only. Not safety advice: check "
                "local conditions, tides and flags before entering the water."
            )
        if (
            data.station is None
            and data.distance_km is not None
            and data.distance_km > WARN_GRID_DISTANCE_KM
        ):
            attrs["accuracy_note"] = (
                "The nearest sea grid point is a long way from this location; "
                "treat the value as approximate."
            )
        return attrs
