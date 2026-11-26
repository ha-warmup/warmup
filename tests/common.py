"""Shared test helpers for the Warmup integration tests."""

import requests

from custom_components.warmup.warmup4ie.warmup4ie import Warmup4IE, Warmup4IEDevice

TEST_USERNAME = "test@example.com"
TEST_PASSWORD = "test-password"


class FakeWarmup4IEDevice(Warmup4IEDevice):
    """A Warmup4IEDevice that records commands instead of sending them.

    Commands change the device's state the way the Warmup servers would, so
    the next coordinator refresh reports the result.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = []

    # When set, every command raises this instead of being recorded.
    command_error = None

    def _check_command(self):
        if FakeWarmup4IEDevice.command_error is not None:
            raise FakeWarmup4IEDevice.command_error

    def set_new_temperature(self, new_temperature):
        self._check_command()
        self.commands.append(("set_new_temperature", new_temperature))
        self.target_temperature = new_temperature
        self.run_mode = "fixed"

    def set_temperature_to_auto(self):
        self._check_command()
        self.commands.append(("set_temperature_to_auto",))
        self.run_mode = "prog"

    def set_temperature_to_manual(self):
        self._check_command()
        self.commands.append(("set_temperature_to_manual",))
        self.run_mode = "fixed"

    def set_room_to_off(self):
        self._check_command()
        self.commands.append(("set_room_to_off",))
        self.run_mode = "off"

    def set_room_to_frost(self):
        self._check_command()
        self.commands.append(("set_room_to_frost",))
        self.run_mode = "frost"

    def set_location_to_frost(self):
        self._check_command()
        self.commands.append(("set_location_to_frost",))
        self.run_mode = "frost"

    def set_location_to_off(self):
        self._check_command()
        self.commands.append(("set_location_to_off",))
        self.run_mode = "off"

    def set_override(self, temperature, until):
        self._check_command()
        self.commands.append(("set_override", temperature, until))
        self.run_mode = "override"


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
    # Number of upcoming update_all_devices calls that are rejected (as when
    # the access token has expired), and the result of logging in again.
    # Location id -> {fuel: tariff dict}, and location id -> tariff type.
    tariffs = {}
    tariff_types = {}
    rejected_updates = 0
    relogin_should_succeed = True
    relogin_count = 0

    def __init__(self, user, password):
        if FakeWarmup4IE.raise_connection_error:
            raise requests.exceptions.ConnectionError("no network in tests")

        self._user = user
        self._password = password
        self._warmup_access_token = "fake-token" if self.login_should_succeed else None

        self.setup_finished = False
        self._locations = {}
        self._location_tariffs = FakeWarmup4IE.tariffs
        self._location_tariff_types = FakeWarmup4IE.tariff_types
        self._rooms = {}
        self._all_devices = {}
        for device in getattr(FakeWarmup4IE, "devices", []):
            self._all_devices[device.get_serial_number()] = device

        if self.login_should_succeed:
            self.setup_finished = True

    def connect(self):
        FakeWarmup4IE.relogin_count += 1
        return FakeWarmup4IE.relogin_should_succeed

    def update_all_devices(self):
        if FakeWarmup4IE.raise_connection_error:
            raise requests.exceptions.ConnectionError("no network in tests")
        if FakeWarmup4IE.rejected_updates:
            FakeWarmup4IE.rejected_updates -= 1
            return None
        return self._all_devices
