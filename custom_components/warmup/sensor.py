"""Sensor platform for the Warmup integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import time
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import WarmupConfigEntry
from .const import DOMAIN
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
        entity_registry_enabled_default=False,
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
    locations = {
        device.get_location_id(): device.get_location_name()
        for device in coordinator.data.values()
    }
    async_add_entities(
        WarmupTariffSensor(coordinator, location_id, name)
        for location_id, name in locations.items()
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


def _parse_time(value: str | None) -> time | None:
    """Parse a Warmup HH:MM time."""
    try:
        hours, minutes = (value or "").split(":")
        return time(int(hours), int(minutes))
    except ValueError:
        return None


def current_rate(tariff: dict[str, Any] | None, now: time) -> float | None:
    """Return the tariff's rate per kWh at this time of day.

    The cheaper ("low") rate applies from its start time until its end time,
    which may be on the next day; the standard rate applies at other times.
    """
    if not tariff:
        return None
    standard = _to_float(tariff.get("cost"))
    low = _to_float(tariff.get("low"))
    start = _parse_time(tariff.get("start"))
    end = _parse_time(tariff.get("end"))
    if low is None or start is None or end is None or start == end:
        return standard
    if start < end:
        in_low_window = start <= now < end
    else:
        in_low_window = now >= start or now < end
    return low if in_low_window else standard


class WarmupTariffSensor(CoordinatorEntity[WarmupCoordinator], SensorEntity):
    """The electricity rate that applies now at a Warmup location."""

    _attr_has_entity_name = True
    _attr_translation_key = "tariff"
    _attr_suggested_display_precision = 2
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: WarmupCoordinator, location_id: int, name: str
    ) -> None:
        """Initialise the sensor for this location."""
        super().__init__(coordinator)
        self._location_id = location_id
        self._attr_unique_id = f"warmup_location_{location_id}_tariff"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"location_{location_id}")},
            manufacturer="Warmup",
            model="Location",
            name=name,
        )
        # Warmup doesn't say which currency its tariff is in.
        self._attr_native_unit_of_measurement = (
            f"{coordinator.hass.config.currency}/{UnitOfEnergy.KILO_WATT_HOUR}"
        )

    @property
    def _tariff(self) -> dict[str, Any] | None:
        return self.coordinator.client.get_location_tariff(self._location_id)

    @property
    def native_value(self) -> float | None:
        """Return the rate that applies now."""
        return current_rate(self._tariff, dt_util.now().time())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the standard and cheaper rates, and the cheaper rate's hours."""
        tariff = self._tariff
        if not tariff:
            return None
        return {
            "standard_rate": _to_float(tariff.get("cost")),
            "low_rate": _to_float(tariff.get("low")),
            "low_rate_start": tariff.get("start") or None,
            "low_rate_end": tariff.get("end") or None,
        }
