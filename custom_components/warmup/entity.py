"""Base entity for the Warmup integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WarmupCoordinator
from .warmup4ie import Warmup4IEDevice


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
