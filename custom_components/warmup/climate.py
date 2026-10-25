"""Platform that offers a connection to a warmup device."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any, Dict

import voluptuous as vol
from .warmup4ie import Warmup4IE, Warmup4IEDevice

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    HVACAction,
    HVACMode,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    ClimateEntityFeature,
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
from homeassistant.helpers import entity_platform, issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from homeassistant.exceptions import InvalidStateError
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

from . import WarmupConfigEntry
from .const import DOMAIN

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

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TURN_ON |ClimateEntityFeature.TURN_OFF
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

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


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
    warmup: Warmup4IE = entry.runtime_data
    warmup_client = WarmupClient(warmup)

    entities = [
        WarmupThermostat(hass, device, warmup_client)
        for device in warmup.get_all_devices().values()
    ]
    async_add_entities(entities)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_OVERRIDE,
        SERVICE_SET_OVERRIDE_SCHEMA,
        "set_override",
    )


class WarmupClient:
    """Wrapper around the API client to throttle requests."""

    def __init__(self, warmup: Warmup4IE):
        """Initialise wrapper."""
        self._warmup = warmup

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Throttles calls to the warmup client update method."""
        _LOGGER.debug("Updating Warmup devices")
        self._warmup.update_all_devices()


class WarmupThermostat(ClimateEntity):
    """Representation of a Warmup device."""

    def __init__(self, hass, device: Warmup4IEDevice, client: WarmupClient):
        """Initialize the climate device."""
        _LOGGER.info("Setting up Warmup Thermostat %s", device.get_room_name())
        self._device = device
        self._client = client

        self.attributes = {}
        self._update_attributes_from_device()

        self._current_temperature = device.current_temperature
        self._target_temperature = device.target_temperature
        self._min_temp = device.min_temp
        self._max_temp = device.max_temp
        self._name = device.get_room_name()
        self._attr_unique_id = "warmup_" + device.get_serial_number()

        self._current_operation_mode = device.run_mode
        self._away = False
        self._on = True

        # https://developers.home-assistant.io/blog/2024/01/24/climate-climateentityfeatures-expanded
        self._enable_turn_on_off_backwards_compatibility = False

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVACMode.
        """
        return HVAC_MAP_WARMUP_HEAT.get(self._current_operation_mode, HVACMode.AUTO)

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of HVACAction.
        """
        if not self._on:
            return HVACAction.OFF
        if not self._away:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        if self._away:
            return PRESET_AWAY
        return PRESET_HOME

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return SUPPORT_PRESET

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""

        if preset_mode == PRESET_HOME:
            """Turn away mode off."""
            self._away = False
            self._device.set_temperature_to_auto()

        elif preset_mode == PRESET_AWAY:
            """Turn away mode on."""
            self._away = True
            self._device.set_location_to_frost()

        else:
            raise InvalidStateError

        pass

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._current_operation_mode = CONST_MODE_FIXED
        self._device.set_new_temperature(temperature)

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode.

        Switch device on if was previously off
        """

        if hvac_mode == HVACMode.OFF:
            self._on = False
            self._device.set_location_to_off()
            self._current_operation_mode = CONST_MODE_OFF

        elif hvac_mode == HVACMode.AUTO:
            self._on = True
            self._device.set_temperature_to_auto()
            self._current_operation_mode = CONST_MODE_PROGRAM

        elif hvac_mode == HVACMode.HEAT:
            self._on = True
            self._device.set_temperature_to_manual()
            self._current_operation_mode = CONST_MODE_FIXED

        else:
            raise InvalidStateError

    def turn_on(self) -> None:
        """Turn the entity on."""
        self.set_hvac_mode(HVACMode.AUTO)

    def turn_off(self) -> None:
        """Turn the entity off."""
        self.set_hvac_mode(HVACMode.OFF)

    def set_override(self, temperature, until=None):
        """Set a temperature override for this thermostat."""
        if until is None:
            until = (datetime.now() + timedelta(hours=1)).strftime("%H:%M")
        self._device.set_override(temperature, until)
        self.schedule_update_ha_state(True)

    def update(self):
        """Fetch new state data for this device.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._client.update()

        self._current_operation_mode = self._device.get_run_mode()
        self._target_temperature = self._device.target_temperature
        self._current_temperature = self._device.current_temperature
        self._min_temp = self._device.min_temp
        self._max_temp = self._device.max_temp

        self._update_attributes_from_device()

        # set whether device is in away mode
        if (
            self._current_operation_mode == CONST_MODE_AWAY
            or self._current_operation_mode == CONST_MODE_FROST
        ):
            self._away = True
        else:
            self._away = False

        # set whether device is on/off
        if self._current_operation_mode == CONST_MODE_OFF:
            self._on = False
        else:
            self._on = True

    def _update_attributes_from_device(self):
        _attributes = {
            "floor_temperature": self._device.floor_temperature,
            "air_temperature": self._device.air_temperature,
            "away_temperature": self._device.away_temperature,
            "comfort_temperature": self._device.comfort_temperature,
            "cost": self._device.cost,
            "energy": self._device.energy,
            "fixed_temperature": self._device.fixed_temperature,
            "override_temperature": self._device.override_temperature,
            "override_duration_mins": self._device.override_duration_mins,
            "sleep_temperature": self._device.sleep_temperature,
            "run_mode": self._device.run_mode,
            "room_mode": self._device.room_mode,
            "heating_target": self._device.heating_target,
        }
        self.attributes = _attributes

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        return {**super(WarmupThermostat, self).state_attributes, **self.attributes}

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        # return convert_temperature(
        #    self._device.min_temp, UnitOfTemperature.CELSIUS, self.hass.config.units.temperature_unit
        # )
        return self._device.min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        # return convert_temperature(
        #     self._device.max_temp, UnitOfTemperature.CELSIUS, self.hass.config.units.temperature_unit
        # )
        return self._device.max_temp

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.CELSIUS

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return PRECISION_HALVES

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC_HEAT
