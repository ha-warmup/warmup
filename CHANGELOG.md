Change log
==========

This file is intended to give you an idea of 
what is new in different versions of the software, 
so that you can decide whether to upgrade, 
which version might suit you the best, 
and what issues you might face.

The most recent versions come first, and the Release Dates are YYYY-MM-DD

## Unreleased

Recent features from development that have not been formally released yet:

### Added

* 

### Changed

* 

### Fixed

* 

### Deprecated

* 

### Removed

* 


## 2021.5.23

Mainly intended to keep the component working once HA 2021.6 is released - thanks to @rct for his contributions

### Added

* Manifest now refers to our issue tracker
* Added version into manifest

### Changed

* Switched to versioning format YYYY.M.D (no leading zeroes)
* removed _cc from folder name
* updated instructions in readme

### Fixed

* "Version Error" in HA log on start up #25



## 0.1.6 - 2020-01-05

### Changed

* Multiple devices are updated in a single HTTP request

### Added

- Set Override method
- Access to the following information from the thermostat
    - target_temperature_low
    - target_temperature_high
    - floor_temperature
    - floor_temperature_2
    - air_temperature
    - away_temperature
    - comfort_temperature
    - cost
    - energy
    - fixed_temperature
    - override_temperature
    - override_duration
    - sleep_temperature
    - override_duration_mins


## 0.1.5 - 2019-05-18

### Added

* getter methods for location, location id, room name, room id and serial number

0.1.4
-----

- added functionality to allow configuration of Warmup4IE thermostat via HA UI Config entry.


0.1.3
-----

- changed http-request to use the new api.
- adapted file names to comply with the new naming structure of HA introduced with 0.92

0.1.2
-----

- bug fixes

0.1.1
-----

- bug fixes

0.1.0
-----

- initial release

