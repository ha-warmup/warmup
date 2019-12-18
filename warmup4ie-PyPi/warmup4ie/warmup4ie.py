"""
platform that offers a connection to a warmup4ie device.

this platform is inspired by the following code:
https://github.com/alyc100/SmartThingsPublic/tree/master/devicetypes/alyc100/\
warmup-4ie.src

to setup this component, you need to register to warmup first.
see
https://my.warmup.com/login

Then add to your
configuration.yaml

climate:
  - platform: warmup4ie
    name: YOUR_DESCRIPTION
    username: YOUR_E_MAIL_ADDRESS
    password: YOUR_PASSWORD
    location: YOUR_LOCATION_NAME
    room: YOUR_ROOM_NAME

# the following issues are not yet implemented, since i have currently no need
# for them
# OPEN  - holiday mode still missing
#       - commands for setting/retrieving programmed times missing
"""

import logging
import requests
from collections import namedtuple

_LOGGER = logging.getLogger(__name__)

RUN_MODE = {0: 'off',
            1: 'prog',
            2: 'overide',
            3: 'fixed',
            4: 'frost',
            5: 'away',
            6: 'flip',
            7: 'grad',
            8: 'relay'}
ROOM_MODE = {1: 'prog',
             3: 'fixed'}
HEATING_TARGET = {
    0: 'floor',
    1: 'air'
}


class Warmup4IE:
    TOKEN_URL = 'https://api.warmup.com/apps/app/v1'
    URL = 'https://apil.warmup.com/graphql'
    APP_TOKEN = \
        'M=;He<Xtg"$}4N%5k{$:PD+WA"]D<;#PriteY|VTuA>_iyhs+vA"4lic{6-LqNM:'
    HEADER = {'user-agent': 'WARMUP_APP',
              'accept-encoding': 'br, gzip, deflate',
              'accept': '*/*',
              'Connection': 'keep-alive',
              'content-type': 'application/json',
              'app-token': APP_TOKEN,
              'app-version': '1.8.1',
              'accept-language': 'de-de'}

    def __init__(self, user, password):
        """Initialize the climate device."""
        _LOGGER.info("Setting up Warmup4IE component")
        self._user = user
        self._password = password
        self._warmup_access_token = None

        self.setup_finished = False
        token_ok = self.connect()
        self._locations = {}
        self._rooms = {}
        self._all_devices = {}
        self.update_all_devices()

        if token_ok:
            self.setup_finished = True

    def connect(self):
        """retrieve access token from server"""
        body = {'request':
                    {'email': self._user,
                     'password': self._password,
                     'method': 'userLogin',
                     'appId': 'WARMUP-APP-V001'}
                }

        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was accepted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error("generating AccessToken failed, %s", response)
            return False
        # extract and store access token for later use
        self._warmup_access_token = response.json()['response']['token']
        return True

    def get_locations(self):
        """retrieve location ID that corrresponds to self._location_name"""
        # make sure we have an accessToken
        if self._warmup_access_token is None:
            _LOGGER.error("Access token is not set. Try calling connect first")
            return None
        body = {
            "account": {
                "email": self._user,
                "token": self._warmup_access_token
            },
            "request": {
                "method": "getLocations"
            }
        }
        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was accepted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error("initialising failed, %s", response)
            return None
        # extract and store locationId for later use
        locations = response.json()['response']['locations']
        return locations

    def get_all_devices(self):
        return self._all_devices

    def get_location_id(self, location_name):
        for l_id, l_name in self._locations.items():
            if l_name == location_name:
                return l_id
        return None

    def get_room_id(self, room_name):
        for r_id, r_name in self._rooms.items():
            if r_name == room_name:
                return r_id
        return None

    def get_device_by_name(self, room_name, location=None):
        location_id = None
        room_id = self.get_room_id(room_name)
        if location is not None:
            location_id = self.get_location_id(location)

        for device in self._all_devices:
            if room_id == device.room_id:
                if location_id is None or location_id == device.location_id:
                    return self._all_devices[device]
        return None

    def update_all_devices(self):
        """
        Update all devices that are registered with this account.

        """
        # make sure we have an accessToken
        if self._warmup_access_token is None:
            _LOGGER.error("Access token is not set. Try calling connect first")
            return None

        body = {
            "query":
                "query QUERY{ "
                "user{ "
                "allLocations: locations { "
                "id "
                "name "
                "rooms{ "
                "id "
                "roomName "
                "runModeInt "
                "targetTemp "
                "currentTemp "
                "awayTemp "
                "comfortTemp "
                "cost "
                "energy "
                "fixedTemp "
                "overrideTemp "
                "overrideDur "
                "roomModeInt "
                "sleepTemp "
                "targetTemp "
                "thermostat4ies {"
                "id "
                "deviceSN "
                "minTemp "
                "maxTemp "
                "airTemp "
                "floor1Temp "
                "floor2Temp "
                "heatingTargetInt"
                "}"
                "}  "
                "}"
                "}  "
                "} "
        }
        header_with_token = self.HEADER.copy()
        header_with_token['warmup-authorization'] = str(self._warmup_access_token)
        response = requests.post(url=self.URL, headers=header_with_token, json=body)
        # check if request was accepted and if request was successful
        if response.status_code != 200 or \
                response.json()['status'] != 'success':
            _LOGGER.error("updating new room failed, %s", response)
            return None
        # extract and store all devices
        device = namedtuple('Device', 'location_id room_id thermostat_id')
        locations = response.json()['data']['user']['allLocations']

        for location in locations:
            self._locations[location["id"]] = location["name"]
            for room in location['rooms']:
                self._rooms[room["id"]] = room["roomName"]
                for thermostat in room['thermostat4ies']:
                    key = device(location["id"], room["id"], thermostat["id"])
                    device_to_update = self._all_devices.get(key, None)
                    if device_to_update is None:
                        _LOGGER.error("Found thermostat with SN %s, name %s in location %s ",
                                      thermostat["deviceSN"], room["roomName"], location["name"])
                        device_to_update = Warmup4IEDevice(
                            location["id"],
                            location["name"],
                            room["id"],
                            room["roomName"],
                            thermostat["id"],
                            thermostat["deviceSN"],
                            self)
                        self._all_devices[key] = device_to_update
                    device_to_update.update_room(room, thermostat)
        return self._all_devices

    def set_override(self, room_id, temperature, hour, minute):
        if self._warmup_access_token is None:
            return
        body = {
            "account": {
                "email": self._user,
                "token": self._warmup_access_token
            },
            "request": {
                "method": "setOverride",
                "rooms": [room_id],
                "temp": "{:03d}".format(int(temperature * 10)),
                "until": "{:02}:{:02}".format(hour, minute),
                "type": 3
            }
        }

        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was accepted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error(
                "Setting override failed, %s", response)
            return None
        _LOGGER.info("Successfully set override, "
                     "response from server: '%s'", response.text)
        return response.json()['message']['setOverride']['overrideDur']

    def _set_location_mode(self, location_id, location_mode):
        """set device to frost protection mode"""
        # make sure the room/device is already configured
        if self._warmup_access_token is None:
            return
        body = {
            "account": {
                "email": self._user,
                "token": self._warmup_access_token
            },
            "request": {
                "method": "setModes",
                "values": {
                    "holEnd": "-",
                    "fixedTemp": "",
                    "holStart": "-",
                    "geoMode": "0",
                    "holTemp": "-",
                    "locId": location_id,
                    "locMode": location_mode
                }
            }
        }
        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was accepted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error(
                "Setting location mode to %s failed, %s", location_mode, response)
            return
        _LOGGER.info("Successfully set location mode to %s, response "
                     "from server: '%s'", location_mode, response.text)

    def _set_temperature(self, room_id, mode, temperature=None):
        # make sure the room/device is already configured
        if self._warmup_access_token is None:
            return
        body = {
            "account": {
                "email": self._user,
                "token": self._warmup_access_token
            },
            "request": {
                "method": "setProgramme",
                "roomId": room_id,
                "roomMode": mode
            }
        }

        if temperature is not None:
            body["request"]["fixed"] = {"fixedTemp": "{:03d}".format(int(temperature * 10))}

        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was accepted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error(
                "Setting room %s - mode to %s, temperature to %s failed, %s", room_id, mode, temperature, response)
            return None
        _LOGGER.info("Successfully set room %s - mode to %s, temperature to %s "
                     "response from server: '%s'", room_id, mode, temperature, response.text)
        return int(response.json()["message"]["targetTemp"]) / 10

    def set_location_to_frost(self, location_id):
        self._set_location_mode(location_id, "frost")

    def set_location_to_off(self, location_id):
        self._set_location_mode(location_id, "off")

    def set_temperature_to_auto(self, room_id):
        return self._set_temperature(room_id, "prog")

    def set_temperature_to_manual(self, room_id):
        return self._set_temperature(room_id, "fixed")

    def set_new_temperature(self, room_id, new_temperature):
        return self._set_temperature(room_id, "fixed", new_temperature)


class Warmup4IEDevice:
    """Representation of a warmup4ie device.
    According to the home assistant documentation this class should be packed
    and made available on PyPi.
    Perhaps later....
    """

    # pylint: disable-msg=too-many-arguments
    def __init__(self, location_id, location_name, room_id, room_name, device_id, serial_number, warmup4ie_account):
        """Initialize the climate device."""
        _LOGGER.info("Setting up Warmup4IE component")
        self._location_name = location_name
        self._loc_id = location_id
        self._room_id = room_id
        self._room_name = room_name
        self._device_id = device_id
        self._serial_number = serial_number
        self._warmup4ie_account = warmup4ie_account

        self._target_temperature = 0
        self._current_temperature = 0
        self._target_temperature_low = 0
        self._target_temperature_high = 0
        self._floor_temperature = 0
        self._floor_temperature_2 = 0
        self._air_temperature = 0
        self._away_temperature = 0
        self._comfort_temperature = 0
        self._cost = "0"
        self._energy = "0"
        self._fixed_temperature = 0
        self._override_temperature = 0
        self._override_duration = 0
        self._sleep_temperature = 0
        self._override_duration_mins = 0
        self._away = False
        self._on = True
        self._run_mode = None
        self._room_mode = None
        self._heating_target = None

    def get_run_mode(self):
        """return current mode, e.g. 'off', 'fixed', 'prog'."""
        return self._run_mode

    def update_room(self, room, thermostat):
        """Update room/device data for the given room name.

        """
        self._target_temperature = int(room['targetTemp']) / 10
        self._target_temperature_low = int(thermostat['minTemp']) / 10
        self._target_temperature_high = int(thermostat['maxTemp']) / 10
        self._current_temperature = int(room['currentTemp']) / 10
        self._floor_temperature = int(thermostat['floor1Temp']) / 10
        self._floor_temperature_2 = int(thermostat['floor2Temp']) / 10
        self._air_temperature = int(thermostat['airTemp']) / 10
        self._away_temperature = int(room['awayTemp']) / 10
        self._comfort_temperature = int(room['comfortTemp']) / 10
        self._cost = room['cost']
        self._energy = room['energy']
        self._fixed_temperature = int(room['fixedTemp']) / 10
        self._override_temperature = int(room['overrideTemp']) / 10
        self._override_duration_mins = int(room['overrideDur'])
        self._sleep_temperature = int(room['sleepTemp']) / 10
        self._run_mode = RUN_MODE.get(room['runModeInt'], None)
        self._room_mode = ROOM_MODE.get(room['roomModeInt'], None)
        self._heating_target = HEATING_TARGET.get(thermostat['heatingTargetInt'], None)

    def get_target_temperature(self):
        """return target temperature"""
        return self._target_temperature

    def get_current_temperature(self):
        """return current temperature"""
        return self._current_temperature

    def get_floor_temperature(self):
        """return floor temperature"""
        return self._floor_temperature

    def get_floor_temperature_2(self):
        """return floor second temperature"""
        return self._floor_temperature_2

    def get_air_temperature(self):
        """return air temperature"""
        return self._air_temperature

    def get_away_temperature(self):
        """return away temperature"""
        return self._away_temperature

    def get_comfort_temperature(self):
        """return comfort temperature"""
        return self._comfort_temperature

    def get_fixed_temperature(self):
        """return fixed temperature"""
        return self._fixed_temperature

    def get_override_temperature(self):
        """return override temperature"""
        return self._override_temperature

    def get_sleep_temperature(self):
        """return sleep temperature"""
        return self._sleep_temperature

    def get_energy(self):
        """return energy usage"""
        return self._energy

    def get_cost(self):
        """return energy cost"""
        return self._energy

    def get_override_duration_mins(self):
        """return the number of minutes the current override is set for"""
        return self._override_duration_mins

    def get_target_temperature_low(self):
        """return minimum temperature"""
        return self._target_temperature_low

    def get_target_temperature_high(self):
        """return maximum temperature"""
        return self._target_temperature_high

    def get_room_mode(self):
        return self._room_mode

    def get_heating_target(self):
        return self._heating_target

    def get_location_name(self):
        return self._location_name

    def get_location_id(self):
        return self._loc_id

    def get_room_name(self):
        return self._room_name

    def get_room_id(self):
        return self._room_id

    def get_serial_number(self):
        return self._serial_number

    def get_device_id(self):
        return self._device_id

    def set_new_temperature(self, new_temperature):
        """set new target temperature"""
        returned_temp = self._warmup4ie_account.set_new_temperature(self._room_id, new_temperature)
        if new_temperature != returned_temp:
            _LOGGER.info("Server declined to set new target temperature "
                         "to %.1f°C", new_temperature)
            return
        self._target_temperature = returned_temp
        _LOGGER.info("Successfully set new target temperature to %.1f°C",
                     self._target_temperature)

    def set_temperature_to_auto(self):
        """set device to automatic mode"""
        self._target_temperature = self._warmup4ie_account.set_temperature_to_auto(self._room_id)

    def set_temperature_to_manual(self):
        """set device to manual mode"""
        self._target_temperature = self._warmup4ie_account.set_temperature_to_manual(self._room_id)

    def set_location_to_frost(self):
        """set device to frost protection mode"""
        self._warmup4ie_account.set_location_to_frost(self._loc_id)

    def set_location_to_off(self):
        """ turn off device"""
        self._warmup4ie_account.set_location_to_off(self._loc_id)

    def set_override(self, temperature, hour, minute):
        self._override_duration_mins = self._warmup4ie_account.set_override(self._room_id, temperature, hour, minute)
