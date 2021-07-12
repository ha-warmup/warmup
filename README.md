# Introduction

This software is a Custom Component to integrate Warmup devices into
[Home Assistant](https://www.home-assistant.io/).

[Warmup](https://www.warmup.co.uk/) manufacture underfloor heating and
control systems and their wifi-enabled home thermostat, [warmup
4IE](https://www.warmup.co.uk/thermostats/smart/4ie-underfloor-heating),
has an API. This software enables communication via this API, and allows
Home Assistant to read and control the device (currently just this one
model).

For instructions on how to **install** this component please keep
reading below.

There is more detailed documentation on the API and the information
returned from the device on the [documentation
wiki](https://github.com/ha-warmup/warmup/wiki). If you have issues
using this software then please check our [Issue
list](https://github.com/ha-warmup/warmup/issues) and if someone else
has not already, then do raise a new issue. If you wish you become more
involved with the project then please see our [guide to
contributing](https://github.com/ha-warmup/warmup/blob/master/CONTRIBUTING.md).

## History

This code is derived from some great work by
[\@alex0103](https://github.com/alex-0103) to create a [Home Assistant
Custom Component and Python
Package](https://github.com/alex-0103/warmup4IE). This has been improved
by a number of coders, notably
[\@foxy82](https://github.com/foxy82/warmup4IE) and the code was
origianlly inspired by [\@alyc100](https://github.com/alyc100)\'s
project for SmartThingsHub
[here](https://github.com/alyc100/SmartThingsPublic/blob/master/devicetypes/alyc100/warmup-4ie.src/warmup-4ie.groovy).
Many Thanks to all the contributors who helped us get here.!

Warmup Plc was not involved in the creation of this software and has not
sanctioned or endorsed it in any way. 4IE is a registered trademark of
Warmup Plc.

## License

This software is published under Apache 2.0 license. Please see LICENSE.md.

# Usage

The library is primary intended to interface the 4IE with home
assistant, but may also be used standalone.

## Home Assistant

To setup this component, you need to register to warmup first. see
<https://my.warmup.com/login>

Then copy the contents of the [warmup]{.title-ref} subfolder into
custom_components in your HA **config** folder, e.g.:

```sh
cd path/to/your/config

git clone https://github.com/ha-warmup/warmup.git /tmp/warmup

# remove any previous version
rm -r ./custom_components/warmup 2>/dev/null
mkdir -p ./custom_components/warmup
cp -r /tmp/warmup/warmup/* ./custom_components/warmup
# clean up
rm -rf /tmp/warmup/
```

NB: the component folder has been renamed from [warmup_cc]{.title-ref}
to simply [warmup]{.title-ref}, in line with recommendations from the HA
project.

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

Our wiki has some [ideas on how to configure warmup
devices](https://github.com/ha-warmup/warmup/wiki/Configuration-ideas)
in your Home Assistant instance.

## Standalone

You may install the library via pip using

```python
>>> pip install warmup4ie
```

After that, import the library, and away we go.

```python
>>> import warmup4ie
>>> warmup = warmup = warmup4ie.Warmup4IE('<e-mail>', '<password>',
>>> warmup.get_all_devices()
>>> device = warmup.get_device_by_name(\"Underfloor\") 
>>> device.get_current_temperature()
```

# Status

## Device Versions

Supported models:

-   4IE

This is currently the only model that developers and testers have
available to work on.

## Supported Features

At the moment the library supports reading current temperature, target
temperature plus other values from the thermostat and setting the target
temperature, switching between manual, automatic and frost protection
mode, switching the device off. and setting a temporary override.

For further information on versions please see the
[CHANGELOG](https://github.com/ha-warmup/warmup/blob/master/CHANGELOG.md)
