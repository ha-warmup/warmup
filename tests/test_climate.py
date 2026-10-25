"""Tests for custom_components/warmup/climate.py."""

from unittest.mock import patch

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.warmup.const import DOMAIN

from .common import TEST_PASSWORD, TEST_USERNAME, FakeWarmup4IE, make_device

PATCH_TARGET_INIT = "custom_components.warmup.Warmup4IE"
PATCH_TARGET_FLOW = "custom_components.warmup.config_flow.Warmup4IE"


async def test_setup_entry_creates_expected_unique_ids(hass):
    """Entities created from a config entry use the historical unique_id scheme."""
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

    with patch(PATCH_TARGET_INIT, FakeWarmup4IE):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    unique_ids = {e.unique_id for e in entries}

    assert unique_ids == {"warmup_AAA111", "warmup_BBB222"}


async def test_setup_entry_adopts_existing_yaml_entity(hass):
    """A unique_id already registered (e.g. from the YAML platform) is adopted."""
    entity_registry = er.async_get(hass)
    # Simulate an entity that was created by the old YAML `platform: warmup` setup,
    # with no config entry attached.
    pre_existing = entity_registry.async_get_or_create(
        domain="climate",
        platform=DOMAIN,
        unique_id="warmup_AAA111",
        suggested_object_id="kitchen",
    )
    assert pre_existing.config_entry_id is None

    FakeWarmup4IE.devices = [make_device(serial="AAA111", room_name="Kitchen")]

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_USERNAME.lower(),
        data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )
    entry.add_to_hass(hass)

    with patch(PATCH_TARGET_INIT, FakeWarmup4IE):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    updated = entity_registry.async_get(pre_existing.entity_id)
    assert updated.unique_id == "warmup_AAA111"
    assert updated.config_entry_id == entry.entry_id
    # entity_id / history are preserved because the unique_id matched.
    assert updated.entity_id == pre_existing.entity_id


async def test_yaml_setup_platform_imports_and_raises_issue(hass):
    """The legacy YAML platform setup imports config and raises a repair issue."""
    from custom_components.warmup.climate import async_setup_platform

    with patch(PATCH_TARGET_FLOW, FakeWarmup4IE):
        await async_setup_platform(
            hass,
            {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
            async_add_entities=lambda *_args, **_kwargs: None,
        )
        await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_USERNAME] == TEST_USERNAME

    issue_registry = ir.async_get(hass)
    issue_id = f"yaml_deprecated_{TEST_USERNAME.lower()}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


async def test_yaml_setup_platform_idempotent_still_raises_issue(hass):
    """Running the YAML setup twice aborts the second import but still raises the issue."""
    from custom_components.warmup.climate import async_setup_platform

    with patch(PATCH_TARGET_FLOW, FakeWarmup4IE):
        for _ in range(2):
            await async_setup_platform(
                hass,
                {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
                async_add_entities=lambda *_args, **_kwargs: None,
            )
            await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    issue_registry = ir.async_get(hass)
    issue_id = f"yaml_deprecated_{TEST_USERNAME.lower()}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
