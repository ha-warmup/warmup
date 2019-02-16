Introduction
============

This is a library for communicating with a wifi-enabled home thermostat made by
`Warmup <https://www.warmup.co.uk/>`_. At the time of writing, this only 
includes the `warmup 4IE
<https://www.warmup.co.uk/thermostats/smart/4ie-underfloor-heating>`.

Warmup Plc was not involved in the creation of this
software and has not sanctioned or endorsed it in any way.

License
=======

This software is available under Apache license. Please see LICENSE.txt.


Usage
=====

Getting Started
---------------

Import the library, and away we go.

    >>> import warmup4ie
    >>> device = warmup4ie.Warmup4IEDevice('<e-mail>', '<password>', 
    '<location>', '<room>', <inital target temp>)
    >>> device.get_current_temmperature()
    {'raw': 21.0}

Device Versions
---------------

Supported models:

- 4IE

Since I only have access to the 4IE, that is the model that the development 
has occured with. 

Supported Features
------------------

Many of the features documented in the manufacturer's API reference do not seem
to work. For example, /tstat/save_energy seems to be broken. This library
should not implement those broken features.

Release Notes
=============

0.1.0
-----

- inital release