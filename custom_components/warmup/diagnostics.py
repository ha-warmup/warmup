"""Diagnostics support for the Warmup integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import WarmupConfigEntry

# Location names are often addresses; serial numbers identify the hardware.
TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    "title",
    "unique_id",
    "location_name",
    "serial_number",
    "deviceSN",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WarmupConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    client = coordinator.client

    devices = []
    location_ids = []
    for device in coordinator.data.values():
        location_id = device.get_location_id()
        if location_id not in location_ids:
            location_ids.append(location_id)
        devices.append(
            {
                "room_name": device.get_room_name(),
                "location_id": location_id,
                "location_name": device.get_location_name(),
                "serial_number": device.get_serial_number(),
                "model": device.model,
                "firmware_version": device.firmware_version,
                "run_mode": device.run_mode,
                "room_mode": device.room_mode,
                "heating_target": device.heating_target,
                "is_unavailable": device.is_unavailable,
                "is_fault_air": device.is_fault_air,
                "is_fault_floor_1": device.is_fault_floor_1,
                "is_fault_floor_2": device.is_fault_floor_2,
                "raw_room": device.raw_room,
                "raw_thermostat": device.raw_thermostat,
            }
        )

    locations = [
        {
            "location_id": location_id,
            "tariff_type": client.get_location_tariff_type(location_id),
            "electricity": client.get_location_tariff(location_id, "electricity"),
            "gas": client.get_location_tariff(location_id, "gas"),
        }
        for location_id in location_ids
    ]

    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "unique_id": entry.unique_id,
                "data": dict(entry.data),
            },
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "update_interval": str(coordinator.update_interval),
            },
            "locations": locations,
            "devices": devices,
        },
        TO_REDACT,
    )
