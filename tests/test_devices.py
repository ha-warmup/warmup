"""Tests for the devices created for Warmup thermostats."""

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warmup.const import DOMAIN

from .common import TEST_PASSWORD, TEST_USERNAME, FakeWarmup4IE, make_device


async def _setup(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME.lower(),
        data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_device_per_thermostat(hass):
    """Each thermostat gets a device, and its climate entity belongs to it."""
    device = make_device(serial="AAA111", room_name="Kitchen")
    device.model = "4ie"
    device.firmware_version = "0370"
    FakeWarmup4IE.devices = [device]

    entry = await _setup(hass)

    device_entry = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, "AAA111"), entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.config_entry_id == entry.entry_id
    assert device_entry.name == "Kitchen"
    assert device_entry.manufacturer == "Warmup"
    assert device_entry.model == "4IE"
    assert device_entry.serial_number == "AAA111"
    assert device_entry.sw_version == "0370"

    entity = er.async_get(hass).async_get(
        er.async_get(hass).async_get_entity_id(CLIMATE_DOMAIN, DOMAIN, "warmup_AAA111")
    )
    assert entity.device_id == device_entry.id
    assert hass.states.get(entity.entity_id).attributes[ATTR_FRIENDLY_NAME] == "Kitchen"


async def test_existing_entity_keeps_entity_id(hass):
    """An entity registered before devices existed is attached to its new device."""
    registry = er.async_get(hass)
    existing = registry.async_get_or_create(
        domain=CLIMATE_DOMAIN,
        platform=DOMAIN,
        unique_id="warmup_AAA111",
        suggested_object_id="kitchen",
    )
    assert existing.device_id is None
    FakeWarmup4IE.devices = [make_device(serial="AAA111", room_name="Kitchen")]

    await _setup(hass)

    updated = registry.async_get(existing.entity_id)
    assert updated.entity_id == existing.entity_id
    assert updated.device_id is not None


async def test_thermostat_linked_to_location_device(hass):
    """Each thermostat's device is connected via its location's device."""
    FakeWarmup4IE.devices = [make_device(serial="AAA111", room_name="Kitchen")]

    entry = await _setup(hass)

    registry = dr.async_get(hass)
    location = registry.async_get_device_by_identifier(
        (DOMAIN, "location_loc1"), entry.entry_id
    )
    assert location is not None
    assert location.name == "Home"
    assert location.model == "Location"

    thermostat = registry.async_get_device_by_identifier(
        (DOMAIN, "AAA111"), entry.entry_id
    )
    assert thermostat.via_device_id == location.id


async def test_existing_thermostat_device_gets_linked(hass):
    """A thermostat device registered before locations existed is linked on setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME.lower(),
        data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )
    entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    existing = registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "AAA111")}, name="Kitchen"
    )
    assert existing.via_device_id is None
    FakeWarmup4IE.devices = [make_device(serial="AAA111", room_name="Kitchen")]

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    location = registry.async_get_device_by_identifier(
        (DOMAIN, "location_loc1"), entry.entry_id
    )
    assert registry.async_get(existing.id).via_device_id == location.id
