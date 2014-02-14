# -*- coding: utf-8 -*-

import unittest

from trachtmlnotification.tests import notification


def suite():
    suite = unittest.TestSuite()
    suite.addTest(notification.suite())
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
