"""Fixtures for the Warmup integration tests."""

from unittest.mock import patch

import pytest

from .common import FakeWarmup4IE

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for every test in this suite."""
    yield


@pytest.fixture(autouse=True)
def reset_fake_warmup4ie():
    """Make sure each test starts from a clean FakeWarmup4IE scenario."""
    FakeWarmup4IE.login_should_succeed = True
    FakeWarmup4IE.raise_connection_error = False
    FakeWarmup4IE.devices = []
    yield
    FakeWarmup4IE.login_should_succeed = True
    FakeWarmup4IE.raise_connection_error = False
    FakeWarmup4IE.devices = []


@pytest.fixture(autouse=True)
def fake_warmup4ie_for_entry_setup():
    """Keep entry setup off the network.

    A config flow that creates an entry also sets that entry up, which
    constructs a Warmup4IE in __init__.py.
    """
    with patch("custom_components.warmup.Warmup4IE", FakeWarmup4IE):
        yield
