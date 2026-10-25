"""Config flow for the Warmup integration."""

from __future__ import annotations

import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN
from .warmup4ie import Warmup4IE

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_login(hass, username: str, password: str) -> None:
    """Validate the user credentials by logging in to the Warmup servers.

    Raises InvalidAuth if the login failed, or a requests exception if the
    Warmup servers could not be reached.
    """
    warmup = await hass.async_add_executor_job(Warmup4IE, username, password)
    if not warmup.setup_finished:
        raise InvalidAuth


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""


class WarmupConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Warmup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._reauth_entry_data: dict[str, Any] | None = None

    async def _async_try_login(
        self, username: str, password: str
    ) -> dict[str, str]:
        """Attempt a login and return a dict of errors (empty if none)."""
        errors: dict[str, str] = {}
        try:
            await _validate_login(self.hass, username, password)
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except requests.exceptions.RequestException:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected exception validating Warmup login")
            errors["base"] = "unknown"
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step started by a user from the UI."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            errors = await self._async_try_login(username, password)

            if not errors:
                await self.async_set_unique_id(username.lower())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=username,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle import of a YAML configured platform entry."""
        username = import_config[CONF_USERNAME]
        password = import_config[CONF_PASSWORD]

        await self.async_set_unique_id(username.lower())
        self._abort_if_unique_id_configured()

        errors = await self._async_try_login(username, password)
        if errors:
            # Keep the previous behaviour of failing setup quietly for YAML;
            # the repair issue created by climate.py tells the user what to
            # do next.
            return self.async_abort(reason=errors["base"])

        return self.async_create_entry(
            title=username,
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
            },
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauthentication flow."""
        self._reauth_entry_data = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication, asking for an updated password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        username = reauth_entry.data[CONF_USERNAME]

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            errors = await self._async_try_login(username, password)

            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={CONF_USERNAME: username},
        )
