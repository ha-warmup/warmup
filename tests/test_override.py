"""Tests for overrides: the Boost preset, the set_override action and options."""

from datetime import datetime, time, timedelta

from homeassistant.components.climate import (
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_HOME,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warmup.climate import override_minutes
from custom_components.warmup.const import CONF_BOOST_DURATION, DOMAIN

from .common import TEST_PASSWORD, TEST_USERNAME, FakeWarmup4IE, make_device


def _device(run_mode="prog"):
    device = make_device(serial="AAA111", room_name="Kitchen")
    device.current_temperature = 19.0
    device.target_temperature = 21.0
    device.min_temp = 5.0
    device.max_temp = 30.0
    device.run_mode = run_mode
    device.override_temperature = 23.5
    device.comfort_temperature = 21.0
    return device


async def _setup(hass, device, options=None):
    FakeWarmup4IE.devices = [device]
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME.lower(),
        data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        CLIMATE_DOMAIN, DOMAIN, "warmup_AAA111"
    )
    return entry, entity_id


async def _set_preset(hass, entity_id, preset):
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_PRESET_MODE: preset},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_boost_preset(hass):
    """Boost overrides at the room's override temperature for an hour."""
    device = _device()
    _, entity_id = await _setup(hass, device)
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_PRESET_MODES] == [
        PRESET_AWAY,
        PRESET_HOME,
        PRESET_BOOST,
    ]

    await _set_preset(hass, entity_id, PRESET_BOOST)

    assert device.commands == [("set_override", 23.5, 60)]
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] == PRESET_BOOST


async def test_boost_uses_configured_duration_and_comfort_fallback(hass):
    """Boost lasts the configured time; with no override temperature, comfort."""
    device = _device()
    device.override_temperature = 0
    _, entity_id = await _setup(hass, device, options={CONF_BOOST_DURATION: 90})

    await _set_preset(hass, entity_id, PRESET_BOOST)

    assert device.commands == [("set_override", 21.0, 90)]


async def test_override_shows_as_boost_and_home_ends_it(hass):
    """A running override shows as Boost; Home returns the room to its schedule."""
    device = _device(run_mode="override")
    _, entity_id = await _setup(hass, device)
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] == PRESET_BOOST

    await _set_preset(hass, entity_id, PRESET_HOME)

    assert device.commands == [("set_temperature_to_auto",)]
    assert hass.states.get(entity_id).attributes[ATTR_PRESET_MODE] == PRESET_HOME


@pytest.mark.parametrize(
    ("data", "expected_minutes"),
    [
        ({}, 60),
        ({"duration": {"hours": 1, "minutes": 30}}, 90),
        ({"duration": "00:20:00"}, 20),
        ({"until": "18:30"}, 30),
        ({"until": "09:00"}, 15 * 60),  # tomorrow
        ({"until": 1439}, 5 * 60 + 59),  # unquoted 23:59 in YAML
    ],
)
async def test_set_override_action(hass, freezer, data, expected_minutes):
    """set_override runs until a time of day, for a duration, or for an hour."""
    await hass.config.async_update(time_zone="UTC")
    freezer.move_to("2026-11-26 18:00:00+00:00")
    device = _device()
    _, entity_id = await _setup(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_override",
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 22, **data},
        blocking=True,
    )

    assert device.commands == [("set_override", 22.0, expected_minutes)]


async def test_set_override_fahrenheit(hass):
    """The override temperature is in Home Assistant's unit and sent in Celsius."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    device = _device()
    _, entity_id = await _setup(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_override",
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 68, "duration": "01:00:00"},
        blocking=True,
    )

    assert device.commands[0][1] == pytest.approx(20.0)


async def test_set_override_validation(hass):
    """until and duration can't be combined, and the override can't exceed a day."""
    device = _device()
    _, entity_id = await _setup(hass, device)

    with pytest.raises(Exception, match="either until or duration"):
        await hass.services.async_call(
            DOMAIN,
            "set_override",
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_TEMPERATURE: 22,
                "until": "18:30",
                "duration": "01:00:00",
            },
            blocking=True,
        )
    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            "set_override",
            {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 22, "duration": "25:00:00"},
            blocking=True,
        )
    assert excinfo.value.translation_key == "override_duration_invalid"
    assert device.commands == []


def test_override_minutes_rounds_up_partial_minutes():
    """A partial minute counts as a whole one, so the override isn't cut short."""
    now = datetime(2026, 11, 26, 18, 0, 30, tzinfo=dt_util.UTC)
    assert override_minutes(time(18, 30), None, now) == 30
    assert override_minutes(None, timedelta(seconds=61), now) == 2


async def test_options_flow(hass):
    """The boost duration is set in the integration's options."""
    entry, _ = await _setup(hass, _device())

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_BOOST_DURATION: 45}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_BOOST_DURATION: 45}
