"""Tests for the Warmup sensor platform."""

from datetime import time

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
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warmup.const import DOMAIN
from custom_components.warmup.sensor import current_rate

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


ELECTRICITY = {"cost": "0.24", "low": "0.07", "start": "00:30", "end": "04:30"}
GAS = {"cost": "0.06", "low": "", "start": "00:00", "end": "00:00"}


def _location_entity_id(hass, key: str) -> str:
    return er.async_get(hass).async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"warmup_location_loc1_{key}"
    )


async def _setup_with_location_sensors_enabled(hass) -> None:
    FakeWarmup4IE.tariffs = {"loc1": {"electricity": ELECTRICITY, "gas": GAS}}
    FakeWarmup4IE.tariff_types = {"loc1": "dual"}
    config_entry = await _setup(hass, _device())
    registry = er.async_get(hass)
    for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id):
        if entry.unique_id.startswith("warmup_location_"):
            registry.async_update_entity(entry.entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_location_sensors_on_location_device(hass):
    """Each location's device gets the tariff sensors, all disabled by default."""
    FakeWarmup4IE.tariffs = {"loc1": {"electricity": ELECTRICITY, "gas": GAS}}
    config_entry = await _setup(hass, _device())

    registry = er.async_get(hass)
    location_entries = [
        entry
        for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id)
        if entry.unique_id.startswith("warmup_location_")
    ]
    assert {entry.unique_id for entry in location_entries} == {
        f"warmup_location_loc1_{key}"
        for fuel in ("electricity", "gas")
        for key in (
            f"{fuel}_rate",
            f"{fuel}_standard_rate",
            f"{fuel}_off_peak_rate",
            f"{fuel}_off_peak_start",
            f"{fuel}_off_peak_end",
        )
    } | {"warmup_location_loc1_tariff_type"}
    assert all(
        entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        for entry in location_entries
    )

    device = dr.async_get(hass).async_get(location_entries[0].device_id)
    assert device.name == "Home"
    assert device.identifiers == {(DOMAIN, "location_loc1")}
    assert device.model == "Location"
    assert config_entry.entry_id == device.config_entry_id


async def test_location_sensor_values(hass, freezer):
    """The tariff sensors show each rate, the off-peak hours and the tariff type."""
    freezer.move_to("2026-11-26 12:00:00+00:00")
    await hass.config.async_update(currency="GBP", time_zone="UTC")
    await _setup_with_location_sensors_enabled(hass)

    def state(key):
        return hass.states.get(_location_entity_id(hass, key))

    rate = state("electricity_rate")
    assert rate.entity_id == "sensor.home_electricity_rate"
    assert float(rate.state) == 0.24  # midday is outside 00:30-04:30
    assert rate.attributes[ATTR_UNIT_OF_MEASUREMENT] == "GBP/kWh"
    assert float(state("electricity_standard_rate").state) == 0.24
    assert float(state("electricity_off_peak_rate").state) == 0.07
    assert state("electricity_off_peak_start").state == "00:30"
    assert state("electricity_off_peak_end").state == "04:30"

    assert float(state("gas_rate").state) == 0.06
    assert float(state("gas_standard_rate").state) == 0.06
    assert state("gas_off_peak_rate").state == "unknown"
    assert state("gas_off_peak_start").state == "unknown"
    assert state("gas_off_peak_end").state == "unknown"

    tariff_type = state("tariff_type")
    assert tariff_type.state == "dual"
    assert tariff_type.attributes["options"] == ["single", "dual"]


async def test_location_sensor_rate_during_off_peak(hass, freezer):
    """During the off-peak hours, the current rate is the off-peak rate."""
    freezer.move_to("2026-11-26 01:00:00+00:00")
    await hass.config.async_update(time_zone="UTC")
    await _setup_with_location_sensors_enabled(hass)

    rate = hass.states.get(_location_entity_id(hass, "electricity_rate"))
    assert float(rate.state) == 0.07


async def test_location_sensors_without_tariff(hass):
    """A location without tariffs has unknown values."""
    config_entry = await _setup(hass, _device())
    registry = er.async_get(hass)
    entity_id = _location_entity_id(hass, "electricity_rate")
    registry.async_update_entity(entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unknown"


@pytest.mark.parametrize(
    ("start", "end", "now", "expected"),
    [
        ("00:30", "04:30", time(0, 30), 0.07),  # start of window
        ("00:30", "04:30", time(4, 29), 0.07),
        ("00:30", "04:30", time(4, 30), 0.24),  # end is exclusive
        ("00:30", "04:30", time(12, 0), 0.24),
        ("23:30", "05:30", time(23, 45), 0.07),  # window past midnight
        ("23:30", "05:30", time(2, 0), 0.07),
        ("23:30", "05:30", time(12, 0), 0.24),
        ("00:00", "00:00", time(2, 0), 0.24),  # no window
    ],
)
def test_current_rate(start, end, now, expected):
    """The cheaper rate applies inside its window, the standard rate outside."""
    tariff = {"cost": "0.24", "low": "0.07", "start": start, "end": end}
    assert current_rate(tariff, now) == expected


def test_current_rate_without_low_rate():
    """Without a cheaper rate, the standard rate always applies."""
    tariff = {"cost": "0.24", "low": "", "start": "00:30", "end": "04:30"}
    assert current_rate(tariff, time(1, 0)) == 0.24
    assert current_rate(None, time(1, 0)) is None
