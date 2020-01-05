#!/usr/bin/env python
import setuptools

long_desc = open('README.rst').read()
setuptools.setup(
    name="warmup4ie",
    version='0.1.5',
    description='client library for 4IE thermostat sold by warmup',
    long_description=long_desc,
    license='Apache',
    author='Alexander Hinz',
    author_email='alex.hinz@plan-b-software.de',
    url='https://github.com/alex-0103/warmup4IE',
    packages=setuptools.find_packages(),
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License ',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        'Topic :: Home Automation',
        'Topic :: Software Development :: Libraries',
    ],
 )
