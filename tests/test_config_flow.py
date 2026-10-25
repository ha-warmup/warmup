"""Tests for the Warmup config flow."""

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType

from custom_components.warmup.const import DOMAIN

from .common import TEST_PASSWORD, TEST_USERNAME, FakeWarmup4IE

PATCH_TARGET = "custom_components.warmup.config_flow.Warmup4IE"


async def test_user_flow_success(hass):
    """A correct username/password creates a config entry."""
    with patch(PATCH_TARGET, FakeWarmup4IE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_USERNAME
    assert result2["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }


async def test_user_flow_invalid_auth(hass):
    """A failed login shows an invalid_auth error and does not create an entry."""
    FakeWarmup4IE.login_should_succeed = False
    with patch(PATCH_TARGET, FakeWarmup4IE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass):
    """A network failure shows a cannot_connect error."""
    FakeWarmup4IE.raise_connection_error = True
    with patch(PATCH_TARGET, FakeWarmup4IE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(hass):
    """A second entry for the same (lowercased) username aborts."""
    with patch(PATCH_TARGET, FakeWarmup4IE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )

        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_USERNAME: TEST_USERNAME.upper(),
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "already_configured"


async def test_import_from_yaml_creates_entry(hass):
    """YAML config is imported into a config entry."""
    with patch(PATCH_TARGET, FakeWarmup4IE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_USERNAME] == TEST_USERNAME


async def test_import_from_yaml_idempotent(hass):
    """Importing the same YAML config twice aborts the second time."""
    with patch(PATCH_TARGET, FakeWarmup4IE):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )

        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reauth_flow_updates_password(hass):
    """The reauth flow updates the password on the existing entry."""
    with patch(PATCH_TARGET, FakeWarmup4IE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
        )
        entry = hass.config_entries.async_entries(DOMAIN)[0]

        entry.async_start_reauth(hass)
        await hass.async_block_till_done()

        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert len(flows) == 1
        reauth_flow = flows[0]
        assert reauth_flow["step_id"] == "reauth_confirm"

        new_password = "new-password"
        result2 = await hass.config_entries.flow.async_configure(
            reauth_flow["flow_id"],
            {CONF_PASSWORD: new_password},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == new_password
    assert entry.data[CONF_USERNAME] == TEST_USERNAME
