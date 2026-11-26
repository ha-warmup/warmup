"""Binary sensor platform for the Warmup integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import WarmupConfigEntry
from .entity import WarmupLocationEntity, parse_warmup_datetime, warmup_locations


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WarmupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Warmup binary sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        WarmupHolidaySensor(coordinator, location_id, name, "holiday")
        for location_id, name in warmup_locations(coordinator).items()
    )


class WarmupHolidaySensor(WarmupLocationEntity, BinarySensorEntity):
    """Whether a Warmup location is in holiday mode now."""

    _attr_translation_key = "holiday"

    @property
    def is_on(self) -> bool:
        """Return True while the location's holiday is running."""
        client = self.coordinator.client
        if client.get_location_mode(self._location_id) == "holiday":
            return True
        holiday = client.get_location_holiday(self._location_id) or {}
        start = parse_warmup_datetime(holiday.get("holStart"))
        end = parse_warmup_datetime(holiday.get("holEnd"))
        return start is not None and end is not None and start <= dt_util.now() < end
