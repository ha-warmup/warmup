"""Tests for the Warmup location controls: buttons, holiday and location mode."""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warmup.const import DOMAIN
from custom_components.warmup.warmup4ie import WarmupCommandError

from .common import (
    TEST_PASSWORD,
    TEST_USERNAME,
    FakeWarmup4IE,
    FakeWarmup4IEDevice,
    make_device,
)

NO_HOLIDAY = {"holStart": None, "holEnd": None, "holTemp": 0}
HOLIDAY = {
    "holStart": "2026-12-01 10:00:00",
    "holEnd": "2026-12-08 18:00:00",
    "holTemp": 100,
}


async def _setup(hass, *, enable_disabled: bool = False) -> MockConfigEntry:
    FakeWarmup4IE.devices = [
        make_device(serial="AAA111", room_name="Kitchen"),
        make_device(serial="BBB222", room_name="Lounge"),
    ]
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME.lower(),
        data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if enable_disabled:
        registry = er.async_get(hass)
        for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
            if reg_entry.disabled_by is not None:
                registry.async_update_entity(reg_entry.entity_id, disabled_by=None)
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _entity_id(hass, domain: str, key: str) -> str:
    return er.async_get(hass).async_get_entity_id(
        domain, DOMAIN, f"warmup_location_loc1_{key}"
    )


def _location_device_id(hass, entry) -> str:
    return (
        dr.async_get(hass)
        .async_get_device_by_identifier((DOMAIN, "location_loc1"), entry.entry_id)
        .id
    )


@pytest.mark.parametrize(
    ("key", "command"),
    [
        ("all_rooms_frost", "set_all_rooms_to_frost"),
        ("all_rooms_off", "set_all_rooms_to_off"),
        ("all_rooms_schedule", "set_all_rooms_to_program"),
        ("cancel_all_overrides", "cancel_all_overrides"),
    ],
)
async def test_location_buttons(hass, key, command):
    """Each location button sends its command once, for the whole location."""
    await _setup(hass)
    entity_id = _entity_id(hass, BUTTON_DOMAIN, key)
    assert entity_id is not None

    await hass.services.async_call(
        BUTTON_DOMAIN, SERVICE_PRESS, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert FakeWarmup4IE.location_commands == [(command, "loc1")]


async def test_location_button_rejected(hass):
    """A location command Warmup rejects raises a translated error."""
    await _setup(hass)
    FakeWarmup4IEDevice.command_error = WarmupCommandError("rejected")

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: _entity_id(hass, BUTTON_DOMAIN, "all_rooms_off")},
            blocking=True,
        )
    assert excinfo.value.translation_key == "command_failed"


async def test_holiday_sensors(hass, freezer):
    """The holiday binary sensor is on during the holiday; its details are sensors."""
    await hass.config.async_update(time_zone="UTC")
    freezer.move_to("2026-12-02 12:00:00+00:00")
    FakeWarmup4IE.holidays = {"loc1": HOLIDAY}
    FakeWarmup4IE.location_modes = {"loc1": "not_geo"}
    await _setup(hass, enable_disabled=True)

    assert (
        hass.states.get(_entity_id(hass, BINARY_SENSOR_DOMAIN, "holiday")).state
        == STATE_ON
    )
    assert (
        hass.states.get(_entity_id(hass, SENSOR_DOMAIN, "holiday_start")).state
        == "2026-12-01T10:00:00+00:00"
    )
    assert (
        hass.states.get(_entity_id(hass, SENSOR_DOMAIN, "holiday_end")).state
        == "2026-12-08T18:00:00+00:00"
    )
    assert (
        float(
            hass.states.get(
                _entity_id(hass, SENSOR_DOMAIN, "holiday_temperature")
            ).state
        )
        == 10.0
    )
    assert (
        hass.states.get(_entity_id(hass, SENSOR_DOMAIN, "location_mode")).state
        == "not_geo"
    )


async def test_holiday_not_running(hass, freezer):
    """Before a holiday starts, or with none set, the holiday sensor is off."""
    await hass.config.async_update(time_zone="UTC")
    freezer.move_to("2026-11-26 12:00:00+00:00")
    FakeWarmup4IE.holidays = {"loc1": HOLIDAY}
    entry = await _setup(hass, enable_disabled=True)
    holiday_id = _entity_id(hass, BINARY_SENSOR_DOMAIN, "holiday")
    assert hass.states.get(holiday_id).state == STATE_OFF

    FakeWarmup4IE.holidays["loc1"] = NO_HOLIDAY
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(holiday_id).state == STATE_OFF
    assert (
        hass.states.get(_entity_id(hass, SENSOR_DOMAIN, "holiday_start")).state
        == "unknown"
    )
    assert (
        hass.states.get(_entity_id(hass, SENSOR_DOMAIN, "holiday_temperature")).state
        == "unknown"
    )


async def test_holiday_sensor_on_in_holiday_mode(hass):
    """Warmup's holiday location mode turns the holiday sensor on."""
    FakeWarmup4IE.location_modes = {"loc1": "holiday"}
    await _setup(hass)

    assert (
        hass.states.get(_entity_id(hass, BINARY_SENSOR_DOMAIN, "holiday")).state
        == STATE_ON
    )


async def test_set_and_cancel_holiday(hass):
    """The holiday actions send the location, Celsius temperature and local times."""
    await hass.config.async_update(time_zone="Europe/London")
    entry = await _setup(hass)
    device_id = _location_device_id(hass, entry)

    await hass.services.async_call(
        DOMAIN,
        "set_holiday",
        {
            ATTR_DEVICE_ID: device_id,
            "start": "2026-12-01 10:00:00",
            "end": "2026-12-08T18:00:00+00:00",
            ATTR_TEMPERATURE: 10,
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "cancel_holiday", {ATTR_DEVICE_ID: device_id}, blocking=True
    )

    assert FakeWarmup4IE.location_commands == [
        ("set_holiday", "loc1", 10.0, "2026-12-01 10:00:00", "2026-12-08 18:00:00"),
        ("cancel_holiday", "loc1"),
    ]


async def test_set_holiday_converts_fahrenheit(hass):
    """A holiday temperature in Fahrenheit is sent to Warmup in Celsius."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry = await _setup(hass)

    await hass.services.async_call(
        DOMAIN,
        "set_holiday",
        {
            ATTR_DEVICE_ID: _location_device_id(hass, entry),
            "start": "2026-12-01 10:00:00",
            "end": "2026-12-02 10:00:00",
            ATTR_TEMPERATURE: 50,
        },
        blocking=True,
    )

    assert FakeWarmup4IE.location_commands[0][2] == pytest.approx(10.0)


async def test_set_holiday_validation(hass):
    """A holiday that ends before it starts, or a thermostat device, is rejected."""
    entry = await _setup(hass)
    location_id = _location_device_id(hass, entry)
    thermostat_id = (
        dr.async_get(hass)
        .async_get_device_by_identifier((DOMAIN, "AAA111"), entry.entry_id)
        .id
    )

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN,
            "set_holiday",
            {
                ATTR_DEVICE_ID: location_id,
                "start": "2026-12-08 10:00:00",
                "end": "2026-12-01 10:00:00",
                ATTR_TEMPERATURE: 10,
            },
            blocking=True,
        )
    assert excinfo.value.translation_key == "holiday_end_before_start"

    with pytest.raises(ServiceValidationError) as excinfo:
        await hass.services.async_call(
            DOMAIN, "cancel_holiday", {ATTR_DEVICE_ID: thermostat_id}, blocking=True
        )
    assert excinfo.value.translation_key == "not_a_location_device"
    assert FakeWarmup4IE.location_commands == []
