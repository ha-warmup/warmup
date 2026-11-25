"""Data update coordinator for the Warmup integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import requests

from .const import DOMAIN
from .warmup4ie import Warmup4IE, Warmup4IEDevice

if TYPE_CHECKING:
    from . import WarmupConfigEntry

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=60)


class WarmupCoordinator(DataUpdateCoordinator[dict[str, Warmup4IEDevice]]):
    """Fetch all thermostats of a Warmup account in one request.

    The data is keyed by thermostat serial number.
    """

    config_entry: WarmupConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: WarmupConfigEntry, client: Warmup4IE
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Warmup4IEDevice]:
        """Fetch the latest state of every thermostat."""
        try:
            devices = await self.hass.async_add_executor_job(self._fetch_devices)
        except requests.exceptions.RequestException as err:
            raise UpdateFailed(f"Error communicating with Warmup: {err}") from err

        return {device.get_serial_number(): device for device in devices.values()}

    def _fetch_devices(self) -> dict:
        """Update all devices, logging in again once if the update is rejected."""
        devices = self.client.update_all_devices()
        if devices is not None:
            return devices

        # The access token may have expired.
        if not self.client.connect():
            raise ConfigEntryAuthFailed("Invalid authentication for the Warmup account")

        devices = self.client.update_all_devices()
        if devices is None:
            raise UpdateFailed("Warmup rejected the device update request")
        return devices
