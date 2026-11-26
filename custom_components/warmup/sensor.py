"""Sensor platform for the Warmup integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import WarmupConfigEntry
from .coordinator import WarmupCoordinator
from .entity import (
    WarmupEntity,
    WarmupLocationEntity,
    parse_warmup_datetime,
    warmup_locations,
)
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
    locations = warmup_locations(coordinator)
    async_add_entities(
        WarmupLocationSensor(coordinator, location_id, name, description)
        for location_id, name in locations.items()
        for description in LOCATION_SENSORS
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


def _off_peak_window(tariff: dict[str, Any] | None) -> tuple[time, time] | None:
    """Return the start and end of the tariff's cheaper rate, if it has one."""
    if not tariff or _to_float(tariff.get("low")) is None:
        return None
    start = _parse_time(tariff.get("start"))
    end = _parse_time(tariff.get("end"))
    if start is None or end is None or start == end:
        return None
    return start, end


def current_rate(tariff: dict[str, Any] | None, now: time) -> float | None:
    """Return the tariff's rate per kWh at this time of day.

    The cheaper (off-peak) rate applies from its start time until its end time,
    which may be on the next day; the standard rate applies at other times.
    """
    if not tariff:
        return None
    standard = _to_float(tariff.get("cost"))
    if (window := _off_peak_window(tariff)) is None:
        return standard
    start, end = window
    if start < end:
        off_peak = start <= now < end
    else:
        off_peak = now >= start or now < end
    return _to_float(tariff.get("low")) if off_peak else standard


def _off_peak_time(tariff: dict[str, Any] | None, index: int) -> str | None:
    """Return the off-peak start (index 0) or end (index 1) as HH:MM."""
    if (window := _off_peak_window(tariff)) is None:
        return None
    return window[index].strftime("%H:%M")


@dataclass(frozen=True, kw_only=True)
class WarmupLocationSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor for a Warmup location's tariff."""

    # Called with the coordinator's client and the location id.
    value_fn: Callable[[Any, int], StateType]
    # True for a rate, whose unit is Home Assistant's currency per kWh.
    is_rate: bool = False


def _fuel_sensors(fuel: str) -> tuple[WarmupLocationSensorEntityDescription, ...]:
    """Describe the rate sensors for one fuel's tariff."""

    def tariff(client: Any, location_id: int) -> dict[str, Any] | None:
        return client.get_location_tariff(location_id, fuel)

    return (
        WarmupLocationSensorEntityDescription(
            key=f"{fuel}_rate",
            translation_key=f"{fuel}_rate",
            is_rate=True,
            value_fn=lambda client, loc: current_rate(
                tariff(client, loc), dt_util.now().time()
            ),
        ),
        WarmupLocationSensorEntityDescription(
            key=f"{fuel}_standard_rate",
            translation_key=f"{fuel}_standard_rate",
            is_rate=True,
            value_fn=lambda client, loc: _to_float(
                (tariff(client, loc) or {}).get("cost")
            ),
        ),
        WarmupLocationSensorEntityDescription(
            key=f"{fuel}_off_peak_rate",
            translation_key=f"{fuel}_off_peak_rate",
            is_rate=True,
            value_fn=lambda client, loc: _to_float(
                (tariff(client, loc) or {}).get("low")
            ),
        ),
        WarmupLocationSensorEntityDescription(
            key=f"{fuel}_off_peak_start",
            translation_key=f"{fuel}_off_peak_start",
            value_fn=lambda client, loc: _off_peak_time(tariff(client, loc), 0),
        ),
        WarmupLocationSensorEntityDescription(
            key=f"{fuel}_off_peak_end",
            translation_key=f"{fuel}_off_peak_end",
            value_fn=lambda client, loc: _off_peak_time(tariff(client, loc), 1),
        ),
    )


def _holiday(client: Any, location_id: int) -> dict[str, Any]:
    return client.get_location_holiday(location_id) or {}


LOCATION_MODES = ["geo", "not_geo", "off", "frost", "holiday"]

LOCATION_SENSORS: tuple[WarmupLocationSensorEntityDescription, ...] = (
    *_fuel_sensors("electricity"),
    *_fuel_sensors("gas"),
    WarmupLocationSensorEntityDescription(
        key="holiday_start",
        translation_key="holiday_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda client, loc: parse_warmup_datetime(
            _holiday(client, loc).get("holStart")
        ),
    ),
    WarmupLocationSensorEntityDescription(
        key="holiday_end",
        translation_key="holiday_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda client, loc: parse_warmup_datetime(
            _holiday(client, loc).get("holEnd")
        ),
    ),
    WarmupLocationSensorEntityDescription(
        key="holiday_temperature",
        translation_key="holiday_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        # Warmup reports 0 when no holiday is set.
        value_fn=lambda client, loc: (
            _holiday(client, loc).get("holTemp") / 10
            if _holiday(client, loc).get("holStart")
            and _holiday(client, loc).get("holTemp") is not None
            else None
        ),
    ),
    WarmupLocationSensorEntityDescription(
        key="location_mode",
        translation_key="location_mode",
        device_class=SensorDeviceClass.ENUM,
        options=LOCATION_MODES,
        value_fn=lambda client, loc: (
            mode if (mode := client.get_location_mode(loc)) in LOCATION_MODES else None
        ),
    ),
    WarmupLocationSensorEntityDescription(
        key="tariff_type",
        translation_key="tariff_type",
        device_class=SensorDeviceClass.ENUM,
        options=["single", "dual"],
        value_fn=lambda client, loc: client.get_location_tariff_type(loc),
    ),
)


class WarmupLocationSensor(WarmupLocationEntity, SensorEntity):
    """A tariff, holiday or mode detail for a Warmup location."""

    entity_description: WarmupLocationSensorEntityDescription
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: WarmupCoordinator,
        location_id: int,
        name: str,
        description: WarmupLocationSensorEntityDescription,
    ) -> None:
        """Initialise the sensor for this location."""
        super().__init__(coordinator, location_id, name, description.key)
        self.entity_description = description
        if description.is_rate:
            # Warmup doesn't say which currency its tariff is in.
            self._attr_native_unit_of_measurement = (
                f"{coordinator.hass.config.currency}/{UnitOfEnergy.KILO_WATT_HOUR}"
            )
            self._attr_suggested_display_precision = 3

    @property
    def native_value(self) -> StateType | datetime:
        """Return the detail."""
        return self.entity_description.value_fn(
            self.coordinator.client, self._location_id
        )
