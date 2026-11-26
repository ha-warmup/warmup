"""Sensor platform for the Warmup integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WarmupConfigEntry
from .coordinator import WarmupCoordinator
from .entity import WarmupEntity
from .warmup4ie import Warmup4IEDevice


def _to_float(value: str | float | None) -> float | None:
    """Convert a value Warmup reports as a decimal string."""
    try:
        return float(value)
    except TypeError, ValueError:
        return None


@dataclass(frozen=True, kw_only=True)
class WarmupSensorEntityDescription(SensorEntityDescription):
    """Describes a Warmup thermostat sensor."""

    value_fn: Callable[[Warmup4IEDevice], float | None]
    # Returns True when the thermostat reports this sensor's probe as faulty
    # (typically because no probe is connected).
    fault_fn: Callable[[Warmup4IEDevice], bool] | None = None


SENSORS: tuple[WarmupSensorEntityDescription, ...] = (
    WarmupSensorEntityDescription(
        key="floor_temperature",
        translation_key="floor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.floor_temperature,
        fault_fn=lambda device: device.is_fault_floor_1,
    ),
    WarmupSensorEntityDescription(
        key="floor_temperature_2",
        translation_key="floor_temperature_2",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.floor_temperature_2,
        fault_fn=lambda device: device.is_fault_floor_2,
    ),
    WarmupSensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device: device.air_temperature,
        fault_fn=lambda device: device.is_fault_air,
    ),
    # Warmup's energy and cost are running totals for today, reset at midnight.
    WarmupSensorEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda device: _to_float(device.energy),
    ),
    WarmupSensorEntityDescription(
        key="cost_today",
        translation_key="cost_today",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        value_fn=lambda device: _to_float(device.cost),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WarmupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Warmup sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        WarmupSensor(coordinator, serial, description)
        for serial in coordinator.data
        for description in SENSORS
    )


class WarmupSensor(WarmupEntity, SensorEntity):
    """A reading from a Warmup thermostat."""

    entity_description: WarmupSensorEntityDescription

    def __init__(
        self,
        coordinator: WarmupCoordinator,
        serial: str,
        description: WarmupSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, serial)
        self.entity_description = description
        self._attr_unique_id = f"warmup_{serial}_{description.key}"
        if description.device_class is SensorDeviceClass.MONETARY:
            # Warmup doesn't say which currency its tariff is in.
            self._attr_native_unit_of_measurement = coordinator.hass.config.currency
        # A probe that isn't connected is reported as faulty; start its sensor
        # disabled rather than permanently unavailable.
        if description.fault_fn is not None and description.fault_fn(self._device):
            self._attr_entity_registry_enabled_default = False

    @property
    def available(self) -> bool:
        """Return whether the reading is valid."""
        fault_fn = self.entity_description.fault_fn
        return super().available and not (
            fault_fn is not None and fault_fn(self._device)
        )

    @property
    def native_value(self) -> float | None:
        """Return the reading."""
        return self.entity_description.value_fn(self._device)
