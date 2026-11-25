"""Tests for the Warmup coordinator and the climate entity's use of it."""

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warmup.const import DOMAIN

from .common import TEST_PASSWORD, TEST_USERNAME, FakeWarmup4IE, make_device


async def _setup(hass, *devices):
    """Set up an entry with the given fake devices; return (entry, entity_ids)."""
    FakeWarmup4IE.devices = list(devices)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME.lower(),
        data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_ids = [
        registry.async_get_entity_id(
            CLIMATE_DOMAIN, DOMAIN, f"warmup_{device.get_serial_number()}"
        )
        for device in devices
    ]
    return entry, entity_ids


def _device(serial="AAA111", room_name="Kitchen", run_mode="prog"):
    device = make_device(serial=serial, room_name=room_name)
    device.current_temperature = 19.0
    device.target_temperature = 21.0
    device.min_temp = 5.0
    device.max_temp = 30.0
    device.run_mode = run_mode
    return device


async def test_state_reflects_device_from_first_update(hass):
    """A thermostat in frost shows as away straight after setup."""
    _, (entity_id,) = await _setup(hass, _device(run_mode="frost"))

    state = hass.states.get(entity_id)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_PRESET_MODE] == PRESET_AWAY
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE


async def test_update_failure_makes_entities_unavailable(hass):
    """A failed update marks every thermostat unavailable until the next success."""
    entry, entity_ids = await _setup(
        hass, _device("AAA111", "Kitchen"), _device("BBB222", "Lounge")
    )

    FakeWarmup4IE.raise_connection_error = True
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert all(hass.states.get(e).state == STATE_UNAVAILABLE for e in entity_ids)

    FakeWarmup4IE.raise_connection_error = False
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert all(hass.states.get(e).state == HVACMode.AUTO for e in entity_ids)


async def test_rejected_update_logs_in_again(hass):
    """A rejected update (e.g. an expired token) logs in again and retries."""
    entry, (entity_id,) = await _setup(hass, _device())

    FakeWarmup4IE.rejected_updates = 1
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert FakeWarmup4IE.relogin_count == 1
    assert hass.states.get(entity_id).state == HVACMode.AUTO


async def test_rejected_login_starts_reauth(hass):
    """If logging in again is rejected, the user is asked to reauthenticate."""
    entry, (entity_id,) = await _setup(hass, _device())

    FakeWarmup4IE.rejected_updates = 1
    FakeWarmup4IE.relogin_should_succeed = False
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"].get("source") == "reauth" for flow in flows)
    assert entry.state is ConfigEntryState.LOADED


async def test_thermostat_reported_unavailable(hass):
    """A thermostat Warmup reports as unavailable is unavailable in HA."""
    device = _device()
    device.is_unavailable = True
    _, (entity_id,) = await _setup(hass, device)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_set_temperature_refreshes_state(hass):
    """Setting a temperature sends the command and shows the result at once."""
    device = _device()
    _, (entity_id,) = await _setup(hass, device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 23.5},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert device.commands == [("set_new_temperature", 23.5)]
    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_TEMPERATURE] == 23.5
    assert state.state == HVACMode.HEAT


async def test_set_hvac_mode_off(hass):
    """Turning a thermostat off sends the command and shows it as off."""
    device = _device()
    _, (entity_id,) = await _setup(hass, device)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert device.commands == [("set_location_to_off",)]
    state = hass.states.get(entity_id)
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.OFF


async def test_set_override_action(hass):
    """The warmup.set_override action sends an override to the thermostat."""
    device = _device()
    _, (entity_id,) = await _setup(hass, device)

    await hass.services.async_call(
        DOMAIN,
        "set_override",
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 22, "until": "18:30"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert device.commands == [("set_override", 22.0, "18:30")]
