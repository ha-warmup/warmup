"""Base entity for the Warmup integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
import requests

from .const import DOMAIN
from .coordinator import WarmupCoordinator
from .warmup4ie import Warmup4IEDevice, WarmupCommandError


async def async_run_command(
    hass: HomeAssistant,
    coordinator: WarmupCoordinator,
    command: Callable[..., Any],
    *args: Any,
) -> None:
    """Send a command to Warmup, then refresh every thermostat.

    Raises a translated HomeAssistantError if Warmup rejects the command or
    can't be reached; the refresh happens either way.
    """
    try:
        await hass.async_add_executor_job(command, *args)
    except WarmupCommandError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except requests.exceptions.RequestException as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"error": str(err)},
        ) from err
    finally:
        await coordinator.async_request_refresh()


def location_device_info(location_id: int, name: str) -> DeviceInfo:
    """Return the device info for a Warmup location."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"location_{location_id}")},
        manufacturer="Warmup",
        model="Location",
        name=name,
    )


class WarmupEntity(CoordinatorEntity[WarmupCoordinator]):
    """An entity belonging to one Warmup thermostat's device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: WarmupCoordinator, serial: str) -> None:
        """Initialise the entity for the thermostat with this serial number."""
        super().__init__(coordinator)
        self._serial = serial
        device = self._device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="Warmup",
            model=device.model.upper() if device.model else None,
            name=device.get_room_name(),
            serial_number=serial,
            sw_version=device.firmware_version,
            via_device_id=coordinator.location_device_ids.get(device.get_location_id()),
        )

    @property
    def _device(self) -> Warmup4IEDevice:
        """Return the latest data for this thermostat."""
        return self.coordinator.data[self._serial]

    @property
    def available(self) -> bool:
        """Return whether the thermostat is reachable."""
        return (
            super().available
            and self._serial in self.coordinator.data
            and not self._device.is_unavailable
        )


class WarmupLocationEntity(CoordinatorEntity[WarmupCoordinator]):
    """An entity belonging to a Warmup location's device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WarmupCoordinator, location_id: int, name: str, key: str
    ) -> None:
        """Initialise the entity for this location."""
        super().__init__(coordinator)
        self._location_id = location_id
        self._attr_unique_id = f"warmup_location_{location_id}_{key}"
        self._attr_device_info = location_device_info(location_id, name)


def warmup_locations(coordinator: WarmupCoordinator) -> dict[int, str]:
    """Return the name of each location that has a thermostat, by location id."""
    return {
        device.get_location_id(): device.get_location_name()
        for device in coordinator.data.values()
    }


WARMUP_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def parse_warmup_datetime(value: str | None) -> datetime | None:
    """Parse a Warmup "YYYY-MM-DD HH:MM:SS" time.

    Warmup gives these in the location's time zone, which is assumed to be
    Home Assistant's.
    """
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, WARMUP_DATETIME_FORMAT)
    except ValueError:
        return None
    return parsed.replace(tzinfo=dt_util.get_default_time_zone())
