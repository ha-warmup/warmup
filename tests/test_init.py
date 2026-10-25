"""Tests for custom_components/warmup/__init__.py (setup/unload of entries)."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warmup.const import DOMAIN

from .common import TEST_PASSWORD, TEST_USERNAME, FakeWarmup4IE, make_device

PATCH_TARGET = "custom_components.warmup.Warmup4IE"


async def _make_entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME.lower(),
        data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_entry_success(hass):
    """A valid entry sets up successfully and stores the client in runtime_data."""
    FakeWarmup4IE.devices = [make_device()]
    entry = await _make_entry(hass)

    with patch(PATCH_TARGET, FakeWarmup4IE):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert isinstance(entry.runtime_data, FakeWarmup4IE)


async def test_setup_entry_auth_failed_triggers_reauth(hass):
    """An entry with bad credentials fails setup and starts a reauth flow."""
    FakeWarmup4IE.login_should_succeed = False
    entry = await _make_entry(hass)

    with patch(PATCH_TARGET, FakeWarmup4IE):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"].get("source") == "reauth" for flow in flows)


async def test_setup_entry_connection_error_not_ready(hass):
    """A connection error leaves the entry in SETUP_RETRY so HA retries later."""
    FakeWarmup4IE.raise_connection_error = True
    entry = await _make_entry(hass)

    with patch(PATCH_TARGET, FakeWarmup4IE):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass):
    """An entry can be unloaded cleanly."""
    FakeWarmup4IE.devices = [make_device()]
    entry = await _make_entry(hass)

    with patch(PATCH_TARGET, FakeWarmup4IE):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
