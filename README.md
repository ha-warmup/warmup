# Introduction

This software is a Custom Component to integrate 
Warmup under-floor heating devices into 
[Home Assistant](https://www.home-assistant.io/). 
It is compatible with the Home Assistant Community Store (HACS).

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)

[Warmup Plc](https://www.warmup.co.uk/) 
manufacture under-floor heating (UFH) and control systems, 
including a range of wifi-enabled home thermostats. 
Some of these thermostats, such as the 
[4IE](https://www.warmup.co.uk/thermostats/smart/4ie-underfloor-heating) 
and 6IE, have an API. 
This software enables communication via this API, 
and allows Home Assistant to read and control the supported devices, 
using a python script to perform the integration. 

You may install this integration from the 
Home Assistant Community Store (HACS), 
or continue reading below for instructions 
on the **manual installation** of this component.


## License

This software is published under Apache 2.0 license. Please see LICENSE.md.

# Usage

The library is primary intended to interface the 4IE with home
assistant, but may also be used standalone.

## Register with My Warmup

Before you can use this component, 
you need to register for a Warmup account. 
See <https://my.warmup.com/login>


## Home Assistant Community Store

If you have HACS installed, then use this button

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=ha-warmup&repository=warmup&category=integration)

Alternatively Explore HACS Repositories and search for `warmup`

See more detailed instuctions on [installing `warmup` in HACS](docs/install-in-HACS.md)


## Manual installation

Here are instructions for you to install this software as a 
**Custom Component** that is manually included 
in a **Home Assistant Core** installation 
(manual using Python virtual environment). 

### Install custom component

You need to copy the contents of the `custom_components/warmup` subfolder 
into in your HA **config** folder, e.g.:

```sh
cd path/to/your/config

git clone https://github.com/ha-warmup/warmup.git /tmp/warmup

# remove any previous version
rm -r ./custom_components/warmup 2>/dev/null
mkdir -p ./custom_components/warmup
cp -r /tmp/warmup/custom_components/warmup/* ./custom_components/warmup
# clean up
rm -rf /tmp/warmup/
```

#### alternative versions

If you are testing a specific branch, like `dev`, then you would `git clone -b dev https...etc` to get the branch you need. 

In the unlikely event that you cannot manually install 
the HACS compatible version of this custom component, 
you may go back to the last release before HACS compatibility, 
[Release v23.02](https://github.com/ha-warmup/warmup/releases/tag/v23.02). 
Please refer to the README inside that source file for the 
legacy commands to deploy the custom component manually.

#### Warnings in logs

Note that once you have successfully 
deployed the custom component and restarted you Home Assistant, 
you should see the following warning in the logs:

    WARNING [homeassistant.loader] 
    We found a custom integration warmup which has not been tested by Home Assistant. 
    This component might cause stability problems, be sure to disable it if you experience issues with Home Assistant

This is a positive sign, as it means 
the custom component has been successfully loaded. Great! - now carry on.


## Configuration

### Add the warmup platform manually via YAML

Then add to your configuration.yaml:

```yaml
climate:
  - platform: warmup
    username: YOUR_E_MAIL_ADDRESS
    password: YOUR_PASSWORD
```

-   **username** (required): the username used to login to the warmup
    web site
-   **password** (required): the password used to login to the warmup
    web site; may be moved to the secrets.yaml file. See
    [secrets](https://www.home-assistant.io/docs/configuration/secrets/)

After restarting home assistant, the component will be loaded
automatically.

#### Tip when changing config

If you are winding up having to do multiple restarts because Home Assistant won't shutdown with the updated config file (because when it checks the config file, integration warmup not found) you can get around that by using the CLI command `ha core restart`.    

Alternatively, with the menu restructuring, the menu entry for _Stop Server_ isn't accessible.  However you can use the keyboard short cut 'c' and type restart to find that choice. Once the server has stopped you can move the config entry in and do a `ha core start` 


### Add your devices to the dashboard

Our wiki has some [ideas on how to configure warmup
devices](https://github.com/ha-warmup/warmup/wiki/Configuration-ideas)
in your Home Assistant instance.


## Other installation types

We do **not currently** have instructions for using this software as 
a _Custom repository_ for **Home Assistant Operating System** (HAOS) 
or **Home Assistant Container** deployments, 
but you are welcome to use our issue tracker 
to discuss any potential improvements to this project. 


### Standalone

_OLD instructions_

You may install the library via pip using

```python
>>> pip install warmup4ie
```

After that, import the library, and away you go.

```python
>>> import warmup4ie
>>> warmup = warmup = warmup4ie.Warmup4IE('<e-mail>', '<password>',
>>> warmup.get_all_devices()
>>> device = warmup.get_device_by_name(\"Underfloor\") 
>>> device.get_current_temperature()
```




# Status

## Supported models

* 4IE
    - this is the device for which this project was launched, so has reasonable support
* 6IE
    - this newer device has shown teething issues here, but seems to work with some caveats
    - try keeping your wifi network SSID length <= 32 characters and password <= 15 characters
    - you cannot set it up as 'living room', but you can choose 'kitchen' and change through the warmup web interface 
    - please see [6ie Thermostat compatibility issues #33](https://github.com/ha-warmup/warmup/issues/33) for details

Note that some models may not have `comma` on the keyboard, which may also limit your choice of wireless network SSID and Password.

## Supported Features

At the moment the library supports reading current temperature, target
temperature plus other values from the thermostat and setting the target
temperature, switching between manual, automatic and frost protection
mode, switching the device off, and setting a temporary override.

For further information on versions please see the
[CHANGELOG](https://github.com/ha-warmup/warmup/blob/master/CHANGELOG.md)

## Find out more

There is more detailed documentation on the API and the information
returned from the device on the [documentation
wiki](https://github.com/ha-warmup/warmup/wiki). If you have issues
using this software then please check our [Issue
list](https://github.com/ha-warmup/warmup/issues) and if someone else
has not already, then do raise a new issue. If you wish you become more
involved with the project then please see our [guide to
contributing](https://github.com/ha-warmup/warmup/blob/master/CONTRIBUTING.md).

### `ha-warmup` is an independent project

Please note that Warmup Plc were not involved 
in the creation of this software. 
We do, however, acknowledge their ownership of 
registered trademarks relating to their brand and products. 

### History

Many Thanks to all the contributors helped us get here!

Originally inspired by 
[\@alyc100](https://github.com/alyc100)\'s
project for SmartThingsHub
[here](https://github.com/alyc100/SmartThingsPublic/blob/master/devicetypes/alyc100/warmup-4ie.src/warmup-4ie.groovy), 
this code is derived from some great work by
[\@alex0103](https://github.com/alex-0103) to create a [Home Assistant
Custom Component and Python
Package](https://github.com/alex-0103/warmup4IE). 
That has been improved by a number of coders, notably
[\@foxy82](https://github.com/foxy82/warmup4IE), 
with valuable contributions and support from 
[\@artmg](https://github.com/artmg/warmup), 
[\@rct](https://github.com/rct/warmup), 
[\@robchandhok](https://github.com/robchandhok/warmup),
[\@kkoenen](https://github.com/kkoenen/warmup).
 
Thank you to the community who continue to 
be involved with and support this project, 
and encourage others to use it. 

