"""Sensors for Sea Temperature."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SeaTemperatureConfigEntry, SeaTemperatureCoordinator
from .api import SeaReading
from .const import DOMAIN, WARN_GRID_DISTANCE_KM


@dataclass(frozen=True, kw_only=True)
class SeaSensorDescription(SensorEntityDescription):
    """Describes a sea sensor."""

    value_fn: Callable[[SeaReading], float | None]


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
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.wave_direction,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SeaTemperatureConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for a location."""
    coordinator = entry.runtime_data
    async_add_entities(SeaSensor(coordinator, entry, d) for d in SENSORS)


class SeaSensor(CoordinatorEntity[SeaTemperatureCoordinator], SensorEntity):
    """A sensor for one reading at one location."""

    _attr_has_entity_name = True
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
            manufacturer="Open-Meteo",
            model="Marine model",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        attrs: dict[str, Any] = {
            "source": data.source,
            "reading_time": data.observed_at.isoformat(),
            "grid_latitude": data.grid_latitude,
            "grid_longitude": data.grid_longitude,
            "distance_to_grid_point_km": data.distance_km,
        }
        if data.distance_km > WARN_GRID_DISTANCE_KM:
            attrs["accuracy_note"] = (
                "The nearest sea grid point is a long way from this location; "
                "treat the value as approximate."
            )
        return attrs
