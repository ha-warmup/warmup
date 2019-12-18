"""Platform that offers a connection to a warmup device."""
import logging

import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateDevice
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, CONF_ROOM,
    TEMP_CELSIUS, PRECISION_HALVES)
from homeassistant.util.temperature import convert as convert_temperature
from homeassistant.exceptions import PlatformNotReady, InvalidStateError
import homeassistant.helpers.config_validation as cv

from homeassistant.components.climate.const import (
    CURRENT_HVAC_OFF,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_AUTO,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_HOME,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)

CONF_LOCATION = 'location'
CONF_TARGET_TEMP = 'target_temp'

DEFAULT_NAME = 'warmup4ie'
DEFAULT_TARGET_TEMP = 20

CONST_MODE_PROGRAM = "prog"  # Default room mode (treated as Home/Auto)
CONST_MODE_FIXED = "fixed" # Fixed temperature mode (treated as Home/Heat)
CONST_MODE_AWAY = "away" # WarmUp Geo Away or Holiday Mode (treated as Away/Auto)
CONST_MODE_FROST = "frost" # Frost Mode (treated as Away/Heat)
CONST_MODE_OFF = "off"  # Switch off heating in a zone

HVAC_MAP_WARMUP_HEAT = {
    CONST_MODE_PROGRAM: HVAC_MODE_AUTO,
    CONST_MODE_FIXED: HVAC_MODE_HEAT,
    CONST_MODE_AWAY: HVAC_MODE_AUTO,
    CONST_MODE_FROST: HVAC_MODE_HEAT,
    CONST_MODE_OFF: HVAC_MODE_OFF,
}

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE
SUPPORT_HVAC_HEAT = [HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF]
SUPPORT_PRESET = [PRESET_AWAY, PRESET_HOME]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_LOCATION): cv.string,
    vol.Required(CONF_ROOM): cv.string,
    vol.Optional(CONF_TARGET_TEMP,
                 default=DEFAULT_TARGET_TEMP): vol.Coerce(float),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo climate devices."""
    _LOGGER.info("Setting up platform for Warmup component")
    name = config.get(CONF_NAME)
    user = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    location = config.get(CONF_LOCATION)
    room = config.get(CONF_ROOM)
    target_temp = config.get(CONF_TARGET_TEMP)

    from warmup4ie import Warmup4IEDevice
    device = Warmup4IEDevice(user, password, location, room,
                             target_temp)
    if device is None or not device.setup_finished:
        raise PlatformNotReady

    add_entities(
        [Warmup(hass, name, device)])


class Warmup(ClimateDevice):
    """Representation of a Warmup device."""

    def __init__(self, hass, name, device):
        """Initialize the climate device."""
        _LOGGER.info("Setting up Warmup component")
        self._name = name
        self._support_flags = SUPPORT_FLAGS
        self._operation_list = [HVAC_MODE_AUTO, HVAC_MODE_HEAT]
        self._unit_of_measurement = TEMP_CELSIUS
        self._away = False
        self._on = True
        self._current_operation_mode = CONST_MODE_PROGRAM
        self._device = device
        self._step = PRECISION_HALVES
        self._min_temp = 5
        self._max_temp = 25

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get_current_temmperature()

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.
        Need to be one of HVAC_MODE_*.
        """
        return HVAC_MAP_WARMUP_HEAT.get(self._current_operation_mode, HVAC_MODE_AUTO)

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.
        Need to be a subset of HVAC_MODES.
        """
        return SUPPORT_HVAC_HEAT

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.
        Need to be one of CURRENT_HVAC_*.
        """
        if not self._on:
            return CURRENT_HVAC_OFF
        if not self._away:
            return CURRENT_HVAC_HEAT
        return CURRENT_HVAC_IDLE

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

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._step

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.get_target_temmperature()

    @property
    def target_temperature_high(self):
        """Return the maximum temperature."""
        return self._device.get_target_temperature_high()

    @property
    def target_temperature_low(self):
        """Return the minimum temperature."""
        return self._device.get_target_temperature_low()

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

        if hvac_mode == HVAC_MODE_OFF:
            self._on = False
            self._device.set_location_to_off()
            self._current_operation_mode = CONST_MODE_OFF

        elif hvac_mode == HVAC_MODE_AUTO:
            self._on = True
            self._device.set_temperature_to_auto()
            self._current_operation_mode = CONST_MODE_PROGRAM

        elif hvac_mode == HVAC_MODE_HEAT:
            self._on = True
            self._device.set_temperature_to_manual()
            self._current_operation_mode = CONST_MODE_FIXED

        else:
            raise InvalidStateError

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return convert_temperature(
            self._min_temp, self._unit_of_measurement, self.hass.config.units.temperature_unit
        )

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return convert_temperature(
            self._max_temp, self._unit_of_measurement, self.hass.config.units.temperature_unit
        )

    def update(self):
        """Fetch new state data for this device.
        This is the only method that should fetch new data for Home Assistant.
        """
        if not self._device.update_room():
            _LOGGER.error("Updating Warmup component failed")

        # set operation mode
        self._current_operation_mode = self._device.get_run_mode()

        # set whether device is in away mode
        if self._current_operation_mode == CONST_MODE_AWAY or self._current_operation_mode == CONST_MODE_FROST:
            self._away = True
        else:
            self._away = False

        # set whether device is on/off
        if self._current_operation_mode == CONST_MODE_OFF:
            self._on = False
        else:
            self._on = True