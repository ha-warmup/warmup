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
    RUN_MODE = {0:'off',
                1:'prog',
                3:'fixed',
                4:'frost',
                5:'away'}

    #pylint: disable-msg=too-many-arguments
    def __init__(self, user, password, location, room, target_temp):
        """Initialize the climate device."""
        _LOGGER.info("Setting up Warmup4IE component")
        self._user = user
        self._password = password
        self._location_name = location
        self._room_name = room
        self._target_temperature = target_temp

        self._warmup_access_token = None
        self._loc_id = None
        self._room = None
        self._current_temperature = 0
        self._away = False
        self._on = True

        self.setup_finished = False
        token_ok = self._generate_access_token()

        location_ok = self._get_locations()

        room_ok = self.update_room()
        if token_ok and location_ok and room_ok:
            self.setup_finished = True

    def get_run_mode(self):
        """return current mode, e.g. 'off', 'fixed', 'prog'."""
        if self._room is None:
            return 'off'
        return self.RUN_MODE[self._room['runModeInt']]

    def update_room(self):
        """Update room/device data for the given room name.

        """
        # make sure the location is already configured
        if self._loc_id is None or \
                self._warmup_access_token is None or \
                self._room_name is None:
            return False

        body = {
                "query": "query QUERY{ user{ currentLocation: location { id name rooms{ id roomName runModeInt targetTemp currentTemp thermostat4ies {minTemp maxTemp}}  }}  } "
        }
        header_with_token = self.HEADER.copy()
        header_with_token['warmup-authorization'] = str(self._warmup_access_token)
        response = requests.post(url=self.URL, headers=header_with_token, json=body)
        # check if request was acceppted and if request was successful
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
        return True
    '''
    def update_room(self):
        """Update room/device data for the given room name.

        """
        # make sure the location is already configured
        if self._loc_id is None or \
                self._warmup_access_token is None or \
                self._room_name is None:
            return False

        body = {
            "account": {
                "email": self._user,
                "token": self._warmup_access_token},
            "request": {
                "method": "getRooms",
                "locId": self._loc_id}
        }
        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was acceppted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error("updating room failed, %s", response)
            return False
        # extract and store roomId for later use
        rooms = response.json()['response']['rooms']
        room_updated = False
        for room in rooms:
            if room['roomName'] == self._room_name:
                self._room = room
                _LOGGER.info("Successfully updated data for room '%s' "
                             "with ID %s", self._room['roomName'],
                             self._room['roomId'])
                room_updated = True
                break
        if not room_updated:
            return False
        # update temperatures values
        self._target_temperature = int(self._room['targetTemp'])/10
        self._target_temperature_low = int(self._room['minTemp'])/10
        self._target_temperature_high = int(self._room['maxTemp'])/10
        self._current_temperature = int(self._room['currentTemp'])/10
        return True
    '''
    def get_target_temmperature(self):
        """return target temperature"""
        return self._target_temperature

    def get_current_temmperature(self):
        """return currrent temperature"""
        return self._current_temperature

    def get_target_temperature_low(self):
        """return minimum temperature"""
        return self._target_temperature_low

    def get_target_temperature_high(self):
        """return maximum temperature"""
        return self._target_temperature_high

    def _generate_access_token(self):
        """retrieve access token from server"""
        body = {'request':
                {'email': self._user,
                 'password': self._password,
                 'method': 'userLogin',
                 'appId': 'WARMUP-APP-V001'}
                }

        response = requests.post(url=self.TOKEN_URL, headers=self.HEADER, json=body)
        # check if request was acceppted and if request was successful
        if response.status_code != 200 or \
                response.json()['status']['result'] != 'success':
            _LOGGER.error("generating AccessToken failed, %s", response)
            return False
        # extract and store access token for later use
        self._warmup_access_token = response.json()['response']['token']
        return True

    def _get_locations(self):
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

