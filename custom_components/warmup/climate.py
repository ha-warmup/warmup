"""Platform that offers a connection to a warmup device."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    PRECISION_HALVES,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import InvalidStateError
from homeassistant.helpers import entity_platform, issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import voluptuous as vol

from . import WarmupConfigEntry
from .const import DOMAIN
from .coordinator import WarmupCoordinator
from .warmup4ie import Warmup4IEDevice

""" temperature utility will stop working in HA 2023.4. Removed it for now, as CELCIUS is the only temperature standard this module supports anyway. """
# from homeassistant.util.temperature import convert as convert_temperature

_LOGGER = logging.getLogger(__name__)

ATTR_UNTIL = "until"

CONF_LOCATION = "location"
CONF_TARGET_TEMP = "target_temp"

DEFAULT_NAME = "warmup4ie"
DEFAULT_TARGET_TEMP = 20

CONST_MODE_PROGRAM = "prog"  # Default room mode (treated as Home/Auto)
CONST_MODE_FIXED = "fixed"  # Fixed temperature mode (treated as Home/Heat)
CONST_MODE_AWAY = "away"  # WarmUp Geo Away or Holiday Mode (treated as Away/Auto)
CONST_MODE_FROST = "frost"  # Frost Mode (treated as Away/Heat)
CONST_MODE_OFF = "off"  # Switch off heating in a zone

HVAC_MAP_WARMUP_HEAT = {
    CONST_MODE_PROGRAM: HVACMode.AUTO,
    CONST_MODE_FIXED: HVACMode.HEAT,
    CONST_MODE_AWAY: HVACMode.AUTO,
    CONST_MODE_FROST: HVACMode.HEAT,
    CONST_MODE_OFF: HVACMode.OFF,
}

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)
SUPPORT_HVAC_HEAT = [HVACMode.HEAT, HVACMode.AUTO, HVACMode.OFF]
SUPPORT_PRESET = [PRESET_AWAY, PRESET_HOME, PRESET_BOOST]

# Kept only so that users who still have `climate: - platform: warmup`
# in configuration.yaml don't get a broken config on upgrade. The platform
# no longer creates entities directly: it imports the YAML config into a
# config entry (see async_setup_platform below) and the entities are then
# created from that config entry by async_setup_entry.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)

SERVICE_SET_OVERRIDE = "set_override"
SERVICE_SET_OVERRIDE_SCHEMA = {
    vol.Required(ATTR_TEMPERATURE): vol.Coerce(float),
    vol.Optional(ATTR_UNTIL): cv.string,
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML configured platform into a config entry.

    No entities are created here any more. This only triggers an import
    flow to create (or find the existing) config entry, and raises a
    repair issue telling the user that the YAML configuration is
    deprecated and can be removed.
    """
    username = config[CONF_USERNAME]

    issue_id = f"yaml_deprecated_{username.lower()}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version=None,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="yaml_deprecated",
        translation_placeholders={"username": username},
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=dict(config),
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WarmupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Warmup climate entities from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        WarmupThermostat(coordinator, serial) for serial in coordinator.data
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_OVERRIDE,
        SERVICE_SET_OVERRIDE_SCHEMA,
        "async_set_override",
    )


class WarmupThermostat(CoordinatorEntity[WarmupCoordinator], ClimateEntity):
    """Representation of a Warmup thermostat."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_hvac_modes = SUPPORT_HVAC_HEAT
    _attr_preset_modes = SUPPORT_PRESET
    _attr_supported_features = SUPPORT_FLAGS
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = PRECISION_HALVES

    def __init__(self, coordinator: WarmupCoordinator, serial: str) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._serial = serial
        self._attr_unique_id = "warmup_" + serial
        device = self._device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            manufacturer="Warmup",
            model=device.model.upper() if device.model else None,
            name=device.get_room_name(),
            serial_number=serial,
            sw_version=device.firmware_version,
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

    @property
    def _is_off(self) -> bool:
        return self._device.run_mode == CONST_MODE_OFF

    @property
    def _is_away(self) -> bool:
        return self._device.run_mode in (CONST_MODE_AWAY, CONST_MODE_FROST)

    @property
    def native_current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def native_target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.target_temperature

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._device.min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._device.max_temp

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        return HVAC_MAP_WARMUP_HEAT.get(self._device.run_mode, HVACMode.AUTO)

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation.

        The Warmup API doesn't report whether the heating is on, so it is
        inferred from the current and target temperatures.
        """
        if self._is_off:
            return HVACAction.OFF
        if self._is_away:
            return HVACAction.IDLE
        current = self._device.current_temperature
        target = self._device.target_temperature
        if target is not None and current <= target:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._is_away:
            return PRESET_AWAY
        return PRESET_HOME

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the thermostat's other readings and settings."""
        device = self._device
        return {
            "floor_temperature": device.floor_temperature,
            "air_temperature": device.air_temperature,
            "away_temperature": device.away_temperature,
            "comfort_temperature": device.comfort_temperature,
            "cost": device.cost,
            "energy": device.energy,
            "fixed_temperature": device.fixed_temperature,
            "override_temperature": device.override_temperature,
            "override_duration_mins": device.override_duration_mins,
            "sleep_temperature": device.sleep_temperature,
            "run_mode": device.run_mode,
            "room_mode": device.room_mode,
            "heating_target": device.heating_target,
        }

    async def _async_send(self, command: Callable[..., Any], *args: Any) -> None:
        """Send a command to Warmup, then refresh every thermostat."""
        await self.hass.async_add_executor_job(command, *args)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_HOME:
            await self._async_send(self._device.set_temperature_to_auto)
        elif preset_mode == PRESET_AWAY:
            await self._async_send(self._device.set_location_to_frost)
        else:
            raise InvalidStateError

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._async_send(self._device.set_new_temperature, temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            await self._async_send(self._device.set_location_to_off)
        elif hvac_mode == HVACMode.AUTO:
            await self._async_send(self._device.set_temperature_to_auto)
        elif hvac_mode == HVACMode.HEAT:
            await self._async_send(self._device.set_temperature_to_manual)
        else:
            raise InvalidStateError

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_override(
        self, temperature: float, until: str | None = None
    ) -> None:
        """Set a temperature override for this thermostat."""
        if until is None:
            until = (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        await self._async_send(self._device.set_override, temperature, until)
