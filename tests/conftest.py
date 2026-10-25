"""Fixtures for the Warmup integration tests."""

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
