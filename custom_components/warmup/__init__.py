"""The Warmup integration."""

from __future__ import annotations

import logging

import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .warmup4ie import Warmup4IE

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]

type WarmupConfigEntry = ConfigEntry[Warmup4IE]


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

    entry.runtime_data = warmup

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WarmupConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
