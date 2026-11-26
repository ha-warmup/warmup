"""Tests for the Warmup sensor platform."""

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_UNAVAILABLE,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warmup.const import DOMAIN

from .common import TEST_PASSWORD, TEST_USERNAME, FakeWarmup4IE, make_device

SERIAL = "AAA111"


def _device():
    device = make_device(serial=SERIAL, room_name="Kitchen")
    device.floor_temperature = 21.5
    device.floor_temperature_2 = 0.0
    device.air_temperature = 19.0
    device.energy = "1.23"
    device.cost = "0.29"
    device.is_fault_floor_2 = True
    return device


async def _setup(hass, device) -> MockConfigEntry:
    FakeWarmup4IE.devices = [device]
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME.lower(),
        data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _entity_id(hass, key: str) -> str:
    return er.async_get(hass).async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"warmup_{SERIAL}_{key}"
    )


async def test_temperature_sensors(hass):
    """Floor and air temperatures are sensors on the thermostat's device."""
    await _setup(hass, _device())

    floor = hass.states.get(_entity_id(hass, "floor_temperature"))
    assert floor.entity_id == "sensor.kitchen_floor_temperature"
    assert float(floor.state) == 21.5
    assert floor.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert floor.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    assert floor.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS

    air = hass.states.get(_entity_id(hass, "air_temperature"))
    assert float(air.state) == 19.0


async def test_energy_sensor_for_energy_dashboard(hass):
    """Today's energy is a total_increasing kWh sensor, usable in the Energy dashboard."""
    await _setup(hass, _device())

    energy = hass.states.get(_entity_id(hass, "energy_today"))
    assert float(energy.state) == 1.23
    assert energy.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert energy.attributes[ATTR_STATE_CLASS] == SensorStateClass.TOTAL_INCREASING
    assert energy.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR


async def test_energy_resets_at_midnight(hass):
    """Warmup resets today's energy to zero, which the sensor reports as is."""
    device = _device()
    entry = await _setup(hass, device)

    device.energy = "0.00"
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert float(hass.states.get(_entity_id(hass, "energy_today")).state) == 0.0


async def test_cost_sensor_disabled_by_default(hass):
    """Today's cost starts disabled."""
    await _setup(hass, _device())

    entry = er.async_get(hass).async_get(_entity_id(hass, "cost_today"))
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entry.entity_id) is None


async def test_cost_sensor_uses_home_assistant_currency(hass):
    """Once enabled, today's cost is in the currency configured in Home Assistant."""
    await hass.config.async_update(currency="GBP")
    config_entry = await _setup(hass, _device())

    registry = er.async_get(hass)
    entity_id = _entity_id(hass, "cost_today")
    registry.async_update_entity(entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    cost = hass.states.get(entity_id)
    assert float(cost.state) == 0.29
    assert cost.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.MONETARY
    assert cost.attributes[ATTR_UNIT_OF_MEASUREMENT] == "GBP"
    assert ATTR_STATE_CLASS not in cost.attributes


async def test_unconnected_probe_starts_disabled(hass):
    """A probe Warmup reports as faulty at setup gets a disabled sensor."""
    await _setup(hass, _device())

    entry = er.async_get(hass).async_get(_entity_id(hass, "floor_temperature_2"))
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entry.entity_id) is None

    connected = er.async_get(hass).async_get(_entity_id(hass, "floor_temperature"))
    assert connected.disabled_by is None


async def test_probe_fault_makes_sensor_unavailable(hass):
    """A probe that becomes faulty makes its sensor unavailable, not a bogus value."""
    device = _device()
    entry = await _setup(hass, device)

    device.is_fault_floor_1 = True
    device.floor_temperature = 90.0
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    floor = hass.states.get(_entity_id(hass, "floor_temperature"))
    assert floor.state == STATE_UNAVAILABLE
    assert float(hass.states.get(_entity_id(hass, "air_temperature")).state) == 19.0


async def test_missing_energy_value(hass):
    """An empty energy value from Warmup is reported as unknown."""
    device = _device()
    device.energy = ""
    await _setup(hass, device)

    assert hass.states.get(_entity_id(hass, "energy_today")).state == "unknown"
