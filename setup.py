#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

extra = {}

setup(
    name = 'TracHtmlNotificationPlugin',
    version = '0.12.0.1',
    description = 'Send ticket notification with HTML part (t:#2625)',
    license = 'BSD',  # the same as Trac
    url = 'http://trac-hacks.org/wiki/TracHtmlNotificationPlugin',
    author = 'Jun Omae',
    author_email = 'jun66j5@gmail.com',
    packages = find_packages(exclude=['*.tests*']),
    package_data = {
        'trachtmlnotification': ['templates/*.html'],
    },
    entry_points = {
        'trac.plugins': [
            'trachtmlnotification.notification = trachtmlnotification.notification',
        ],
    },
    test_suite = 'trachtmlnotification.tests',
    **extra)
