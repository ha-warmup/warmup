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


class Warmup4IEDevice():
    """Representation of a warmup4ie device.
    According to the home assistant documentation this class should be packed
    and made available on PyPi.
    Perhaps later....
    """
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

    #pylint: disable-msg=too-many-arguments
    def __init__(self, user, password, location = None, room = None, target_temp = 0):
        """Initialize the climate device."""
        _LOGGER.info("Setting up Warmup4IE component")
        self._user = user
        self._password = password
        self._location_name = location
        self._room_name = room
        self._target_temperature = target_temp

        self._all_devices = None
        self._warmup_access_token = None
        self._loc_id = None
        self._room = None
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
        self.sleep_temperature = 0
        self._override_duration_mins = 0
        self._away = False
        self._on = True

        self.setup_finished = False
        token_ok = self._generate_access_token()

        self._all_devices = self.get_all_devices()

        if self._all_devices is not None and self._location_name is None:
            self._location_name = self._all_devices[0].loc_name
        if self._all_devices is not None and self._room_name is None:
            self._room_name = self._all_devices[0].room_name

        location_ok = self._get_location_from_name()

        room_ok = self.update_room()
        if token_ok and location_ok and room_ok:
            self.setup_finished = True

    def get_run_mode(self):
        """return current mode, e.g. 'off', 'fixed', 'prog'."""
        if self._room is None:
            return 'off'
        return self.RUN_MODE[self._room['runModeInt']]

    def get_all_devices(self, update = False):
        """Return all devices that are registered with this account.

        """
        if not update and self._all_devices is not None:
            return self._all_devices

        # make sure we have an accessToken
        if self._warmup_access_token is None:
            return None

        body = {
                "query":"query QUERY{ user{ allLocations: locations{ id name rooms{ id roomName thermostat4ies{id deviceSN  } } }}  } "
        }
        header_with_token = self.HEADER.copy()
        header_with_token['warmup-authorization'] = str(self._warmup_access_token)
        response = requests.post(url=self.URL, headers=header_with_token, json=body)
        # check if request was acceppted and if request was successful
        if response.status_code != 200 or \
                response.json()['status'] != 'success':
            _LOGGER.error("updating new room failed, %s", response)
            return None
        # extract and store all devices
        devices = list()
        device = namedtuple('Device', 'loc_name loc_id room_name room_id thermostat_id thermostat_SN')
        locations = response.json()['data']['user']['allLocations']

        for location in locations:
            for room in location['rooms']:
                for thermostat in room['thermostat4ies']:
                    devices.append(device(location["name"],location["id"],room["roomName"], room["id"],thermostat["id"],thermostat["deviceSN"]))
                    _LOGGER.info("Found thermostat with SN %s ",thermostat["deviceSN"])
        if len(devices):
            _LOGGER.info("Found %i thermostats",len(devices))
        else:
            _LOGGER.error("No thermostats found!")
            return None
        return devices

    def update_room(self):
        """Update room/device data for the given room name.

        """
        # make sure the location is already configured
        if self._loc_id is None or \
                self._warmup_access_token is None or \
                self._room_name is None:
            return False

        body = {
                "query": "query QUERY{ user{ currentLocation: location { id name rooms{ id roomName runModeInt targetTemp currentTemp awayTemp comfortTemp cost energy fixedTemp overrideTemp overrideDur roomModeInt sleepTemp targetTemp thermostat4ies {minTemp maxTemp airTemp floor1Temp floor2Temp heatingTargetInt}}  }}  } "
        }
        header_with_token = self.HEADER.copy()
        header_with_token['warmup-authorization'] = str(self._warmup_access_token)
        response = requests.post(url=self.URL, headers=header_with_token, json=body)
        # check if request was accepted and if request was successful
        if response.status_code != 200 or \
                response.json()['status'] != 'success':
            _LOGGER.error("updating new room failed, %s", response)
            return False
        # extract and store roomId for later use
        rooms = response.json()['data']['user']['currentLocation']['rooms']
        room_updated = False
        for room in rooms:
            if room['roomName'] == self._room_name:
                self._room = room
                _LOGGER.info("Successfully updated data for room '%s' "
                             "with ID %s", self._room['roomName'],
                             self._room['id'])
                room_updated = True
                break
        if not room_updated:
            return False
        # update temperatures values
        self._target_temperature = int(self._room['targetTemp'])/10
        self._target_temperature_low = int(self._room['thermostat4ies'][0]['minTemp'])/10
        self._target_temperature_high = int(self._room['thermostat4ies'][0]['maxTemp'])/10
        self._current_temperature = int(self._room['currentTemp'])/10
        self._floor_temperature = int(self._room['thermostat4ies'][0]['floor1Temp'])/10
        self._floor_temperature_2 = int(self._room['thermostat4ies'][0]['floor2Temp'])/10
        self._air_temperature = int(self._room['thermostat4ies'][0]['airTemp'])/10
        self._away_temperature = int(self._room['awayTemp'])/10
        self._comfort_temperature = int(self._room['comfortTemp'])/10
        self._cost = self._room['cost']
        self._energy = self._room['energy']
        self._fixed_temperature = int(self._room['fixedTemp'])/10
        self._override_temperature = int(self._room['overrideTemp'])/10
        self._override_duration_mins = int(self._room['overrideDur'])
        self.sleep_temperature = int(self._room['sleepTemp'])/10
        return True

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

    def get_location_name(self):
        return self._location_name

    def get_location_id(self):
        return self._loc_id

    def get_room_name(self):
        return self._room_name

    def get_room_id(self):
        return self._room['id']

    def get_SN(self):
        for device in self._all_devices:
            if device.loc_id == self._loc_id and device.room_id == self._room['id']:
                return device.thermostat_SN
        return None

    def _generate_access_token(self):
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

    def _get_location_from_name(self):
        """retrieve location ID that corrresponds to self._location_name"""
        # make sure we have an accessToken
        if self._warmup_access_token is None:
            return False
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
        # check if request was acceppted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error("initialising failed, %s", response)
            return False
        # extract and store locationId for later use
        locations = response.json()['response']['locations']
        for loc in locations:
            if loc['name'] == self._location_name:
                self._loc_id = loc['id']
                _LOGGER.info(
                    "Successfully fetched location ID %s for location '%s'",
                    self._loc_id, self._location_name)
                break
        if self._loc_id is None:
            return False
        return True

    def set_new_temperature(self, new_temperature):
        """set new target temperature"""
        # make sure the room/device is already configured
        if self._room is None or self._warmup_access_token is None:
            return
        body = {
            "account": {
                "email": self._user,
                "token": self._warmup_access_token
            },
            "request": {
                "method": "setProgramme",
                "roomId": self._room['id'],
                "roomMode": "fixed",
                "fixed": {
                    "fixedTemp": "{:03d}".format(int(new_temperature * 10))
                }
            }
        }
        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was acceppted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error(
                "Setting new target temperature failed, %s", response)
            return
        response_temp = response.json()["message"]["targetTemp"]
        if new_temperature != int(response_temp)/10:
            _LOGGER.info("Server declined to set new target temperature "
                         "to %.1f°C; response from server: '%s'",
                         new_temperature, response.text)
            return
        self._target_temperature = new_temperature
        _LOGGER.info("Successfully set new target temperature to %.1f°C; "
                     "response from server: '%s'",
                     self._target_temperature, response.text)

    def set_temperature_to_auto(self):
        """set device to automatic mode"""
        # make sure the room/device is already configured
        if self._room is None or self._warmup_access_token is None:
            return
        body = {
            "account": {
                "email": self._user,
                "token": self._warmup_access_token
            },
            "request": {
                "method": "setProgramme",
                "roomId": self._room['id'],
                "roomMode": "prog"
            }
        }
        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was acceppted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error(
                "Setting new target temperature to auto failed, %s", response)
            return
        _LOGGER.info("Successfully set new target temperature to auto, "
                     "response from server: '%s'", response.text)

    def set_temperature_to_manual(self):
        """set device to manual mode"""
        # make sure the room/device is already configured
        if self._room is None or self._warmup_access_token is None:
            return
        body = {
            "account": {
                "email": self._user,
                "token": self._warmup_access_token
            },
            "request": {
                "method": "setProgramme",
                "roomId": self._room['id'],
                "roomMode": "fixed"
            }
        }
        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was acceppted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error(
                "Setting new target temperature to "
                "manual failed, %s", response)
            return

        _LOGGER.info("Successfully set new target temperature to manual, "
                     "response from server: '%s'", response.text)

    def set_location_to_frost(self):
        """set device to frost protection mode"""
        # make sure the room/device is already configured
        if self._loc_id is None or self._warmup_access_token is None:
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
                    "locId": self._loc_id,
                    "locMode": "frost"
                }
            }
        }
        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was acceppted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error(
                "Setting location to frost protection failed, %s", response)
            return
        _LOGGER.info("Successfully set location to frost protection, response "
                     "from server: '%s'", response.text)

    def set_location_to_off(self):
        """ turn off device"""
        # make sure the room/device is already configured
        if self._loc_id is None or self._warmup_access_token is None:
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
                    "locId": self._loc_id,
                    "locMode": "off"
                }
            }
        }
        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was acceppted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error("Setting location to off mode failed, %s", response)
            return
        _LOGGER.info("Successfully set location to off mode, "
                     "response from server: '%s'", response.text)

