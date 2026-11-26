"""Tests for Warmup diagnostics."""

import json

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.warmup.const import DOMAIN

from .common import TEST_PASSWORD, TEST_USERNAME, FakeWarmup4IE, make_device


async def test_diagnostics(hass, hass_client):
    """Diagnostics include the raw Warmup data, with personal details redacted."""
    device = make_device(serial="AAA111", room_name="Kitchen")
    device.model = "4ie"
    device.run_mode = "prog"
    device.is_fault_floor_2 = True
    device.raw_room = {"roomName": "Kitchen", "currentTemp": 215, "targetTemp": 200}
    device.raw_thermostat = {
        "deviceSN": "AAA111",
        "floor1Temp": "900",
        "floor2Temp": "235",
        "isFaultFloor1": True,
    }
    FakeWarmup4IE.devices = [device]
    FakeWarmup4IE.tariffs = {
        "loc1": {
            "electricity": {
                "cost": "0.24",
                "low": "",
                "start": "00:00",
                "end": "00:00",
            },
            "gas": None,
        }
    }
    FakeWarmup4IE.tariff_types = {"loc1": "single"}

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TEST_USERNAME,
        unique_id=TEST_USERNAME.lower(),
        data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diagnostics["entry"] == {
        "title": REDACTED,
        "unique_id": REDACTED,
        "data": {CONF_USERNAME: REDACTED, CONF_PASSWORD: REDACTED},
    }
    assert diagnostics["coordinator"]["last_update_success"] is True
    assert diagnostics["locations"] == [
        {
            "location_id": "loc1",
            "tariff_type": "single",
            "electricity": {
                "cost": "0.24",
                "low": "",
                "start": "00:00",
                "end": "00:00",
            },
            "gas": None,
        }
    ]

    (device_data,) = diagnostics["devices"]
    assert device_data["room_name"] == "Kitchen"
    assert device_data["location_name"] == REDACTED
    assert device_data["serial_number"] == REDACTED
    assert device_data["model"] == "4ie"
    assert device_data["is_fault_floor_2"] is True
    assert device_data["raw_room"]["currentTemp"] == 215
    assert device_data["raw_thermostat"] == {
        "deviceSN": REDACTED,
        "floor1Temp": "900",
        "floor2Temp": "235",
        "isFaultFloor1": True,
    }

    dumped = json.dumps(diagnostics)
    assert TEST_USERNAME not in dumped
    assert TEST_PASSWORD not in dumped
    assert "AAA111" not in dumped
