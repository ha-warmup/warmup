"""Shared test helpers for the Warmup integration tests."""

import requests

from custom_components.warmup.warmup4ie.warmup4ie import Warmup4IE, Warmup4IEDevice

TEST_USERNAME = "test@example.com"
TEST_PASSWORD = "test-password"


class FakeWarmup4IEDevice(Warmup4IEDevice):
    """A Warmup4IEDevice that doesn't need network access."""


def make_device(serial="SN123", room_name="Kitchen") -> FakeWarmup4IEDevice:
    """Build a fake device without hitting the network."""
    return FakeWarmup4IEDevice(
        location_id="loc1",
        location_name="Home",
        room_id="room1",
        room_name=room_name,
        device_id="dev1",
        serial_number=serial,
        warmup4ie_account=None,
    )


class FakeWarmup4IE(Warmup4IE):
    """A Warmup4IE client double that never touches the network.

    Mirrors the constructor's side effects (login + initial device fetch)
    without issuing any requests, so it can be used directly wherever
    production code does `Warmup4IE(username, password)`.
    """

    # Set at class level by tests, so the constructor behaves like the
    # scenario currently being tested (successful login, failed login, ...).
    login_should_succeed = True
    raise_connection_error = False

    def __init__(self, user, password):
        if FakeWarmup4IE.raise_connection_error:
            raise requests.exceptions.ConnectionError("no network in tests")

        self._user = user
        self._password = password
        self._warmup_access_token = "fake-token" if self.login_should_succeed else None

        self.setup_finished = False
        self._locations = {}
        self._rooms = {}
        self._all_devices = {}
        for device in getattr(FakeWarmup4IE, "devices", []):
            self._all_devices[device.get_serial_number()] = device

        if self.login_should_succeed:
            self.setup_finished = True

    def connect(self):
        return self.login_should_succeed

    def update_all_devices(self):
        return self._all_devices
