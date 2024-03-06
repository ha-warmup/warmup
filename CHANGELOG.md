Change log
==========

This file is intended to give you an idea of 
what is new in different versions of the software, 
so that you can decide whether to upgrade, 
which version might suit you the best, 
and what issues you might face.

The most recent versions come first, and the Release Versions 
are based on date using format YYYY.M.D (no leading zeroes)

## Unreleased

Recent features from development that have not been formally released yet:

### Added

* 

### Changed

* 

### Fixed

* 

### Documented

* 

### Deprecated

* 

### Removed

* 


## 2024.2.7 Pre-release

Prepare for HA Core 2025.1 release, by moving deprecated Contants to Enums. Triggered by HA Core 2023.12 release logging deprecation warnings on startup.

### Added

* 

### Changed

* 

### Fixed

* 38ef7ae Updated to use new ENUM constants instead of deprecated ones (Issue #65)
* 

### Documented

* d743cb6 more testing methods in CONTRIBUTING.md
* 0677520 minor doc link for installation types
* e66cebf Include full documention for HACS installation with images
* 01b4bb7 How to disable actions when they fail in your OWN fork
* 909513e Contributing pre-releases (beta versions)
* 

### Deprecated

* 

### Removed

* 


## 2023.3.27

Ready to include in HACS default repositories 

### Added

* 03d09df use hassfest validation for HA custom_component compaibility checks
* 5b2ace6 Add HACS validate action to workflows
* df9d8cc more dev guidelines in CONTRIBUTING.md

### Fixed

* c8eb031 Clarify HACS validation in Actions
* 4820e4f removed invalid entries from hacs.json
* 


## 2023.3.22

This is a bugfix release. The previous release had a broken HACS manifest.

### Added

* 9d4d24d some additions notes and suggestions for project contributors
* d9733d9 Tip when changing config, plus slight re-org, in README.md

### Fixed

* 418503e Bumped version in manifest.json (missed during 2023.3.19 release)



## 2023.3.19

This is a MAJOR release. Previously this project was focussed on 
a manually installed cusom_component. This release re-organised it 
to be primarily a HACS integration that still works if installed manually.

See README for details of new usage, and how to obtain old release if you have issues

### Added

* f345c03 Include HACS metadata files, and recent additions to components manifest
* 57bfef6 Add unique id to the WarmupThermostat entity.
* d9e4755 Added support notes for 6ie model
* b91983a additional notes on devices supported from issue #33

### Changed

* 0175088 Reorgansied documentation (especially README) to adjust for new focus on HACS install, with manual as alternative
* b60d38a Update README instructions for backwards compatibility with manual installations
* e272be1 Restructured folders ready for HACS compatibility – moved the `warmup` folder into a new `custom_components` folder
* 5fc20de Clarified install instructions following user feedback #30 #31
* f4a2ca9 Converted README and LICENSE to Markdown

### Fixed

* b8d34e7 bring `dev` branch up to date so it can start receiving PRs for testing
* 6dedb42 removed `temperature utility` ready to use new `TemperatureConverter` where needed - fix for #42

### Deprecated

* none

### Removed

* Old documentation referring to HACS not being supported


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

