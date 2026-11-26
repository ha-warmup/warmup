"""Actions for the Warmup integration."""

from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter
import voluptuous as vol

from .const import DOMAIN
from .coordinator import WarmupCoordinator
from .entity import WARMUP_DATETIME_FORMAT, async_run_command, warmup_locations

SERVICE_SET_HOLIDAY = "set_holiday"
SERVICE_CANCEL_HOLIDAY = "cancel_holiday"

ATTR_START = "start"
ATTR_END = "end"

SET_HOLIDAY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_START): cv.datetime,
        vol.Required(ATTR_END): cv.datetime,
        vol.Required(ATTR_TEMPERATURE): vol.Coerce(float),
    }
)
CANCEL_HOLIDAY_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


def _location(
    hass: HomeAssistant, device_id: str
) -> tuple[WarmupCoordinator, int | str]:
    """Return the coordinator and location id for a Warmup location device."""
    device = dr.async_get(hass).async_get(device_id)
    location_key = next(
        (
            identifier[1].removeprefix("location_")
            for identifier in (device.identifiers if device else ())
            if identifier[0] == DOMAIN and identifier[1].startswith("location_")
        ),
        None,
    )
    if location_key is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_a_location_device",
        )
    entry = hass.config_entries.async_get_entry(device.config_entry_id)
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="entry_not_loaded",
        )
    coordinator: WarmupCoordinator = entry.runtime_data
    for location_id in warmup_locations(coordinator):
        if str(location_id) == location_key:
            return coordinator, location_id
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="not_a_location_device",
    )


def _warmup_time(value: datetime) -> str:
    """Format a time for Warmup, in Home Assistant's (and the location's) zone."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_local(value).strftime(WARMUP_DATETIME_FORMAT)


async def _async_set_holiday(call: ServiceCall) -> None:
    hass = call.hass
    coordinator, location_id = _location(hass, call.data[ATTR_DEVICE_ID])
    start, end = call.data[ATTR_START], call.data[ATTR_END]
    if _warmup_time(end) <= _warmup_time(start):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="holiday_end_before_start",
        )
    temperature = TemperatureConverter.convert(
        call.data[ATTR_TEMPERATURE],
        hass.config.units.temperature_unit,
        UnitOfTemperature.CELSIUS,
    )
    await async_run_command(
        hass,
        coordinator,
        coordinator.client.set_holiday,
        location_id,
        temperature,
        _warmup_time(start),
        _warmup_time(end),
    )


async def _async_cancel_holiday(call: ServiceCall) -> None:
    coordinator, location_id = _location(call.hass, call.data[ATTR_DEVICE_ID])
    await async_run_command(
        call.hass, coordinator, coordinator.client.cancel_holiday, location_id
    )


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Warmup actions."""
    hass.services.async_register(
        DOMAIN, SERVICE_SET_HOLIDAY, _async_set_holiday, schema=SET_HOLIDAY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CANCEL_HOLIDAY,
        _async_cancel_holiday,
        schema=CANCEL_HOLIDAY_SCHEMA,
    )
