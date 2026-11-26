"""The Warmup integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
import requests

from .coordinator import WarmupCoordinator
from .entity import location_device_info
from .warmup4ie import Warmup4IE

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR]

type WarmupConfigEntry = ConfigEntry[WarmupCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: WarmupConfigEntry) -> bool:
    """Set up Warmup from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        warmup = await hass.async_add_executor_job(Warmup4IE, username, password)
    except requests.exceptions.RequestException as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to Warmup servers: {err}"
        ) from err

    if not warmup.setup_finished:
        raise ConfigEntryAuthFailed("Invalid authentication for the Warmup account")

    coordinator = WarmupCoordinator(hass, entry, warmup)
    await coordinator.async_config_entry_first_refresh()

    # Register the location devices first, so thermostat devices can link to
    # them with via_device_id.
    device_registry = dr.async_get(hass)
    for device in coordinator.data.values():
        location_id = device.get_location_id()
        if location_id not in coordinator.location_device_ids:
            location_device = device_registry.async_get_or_create_from_info(
                config_entry_id=entry.entry_id,
                device_info=location_device_info(
                    location_id, device.get_location_name()
                ),
            )
            coordinator.location_device_ids[location_id] = location_device.id

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WarmupConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
