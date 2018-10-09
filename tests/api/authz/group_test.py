"""Cell API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import grp
from collections import namedtuple

import unittest

import mock

from treadmill.api.authz import group


_MockGrp = namedtuple('grp', ['gr_mem'])


class GroupAuthzTest(unittest.TestCase):
    """treadmill.api.authz.group tests."""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('grp.getgrnam', mock.Mock())
    def test_authorize(self):
        """Dummy test for treadmill.api.cell.get()"""
        # set templates directly.
        grp_authz = group.API(groups=['treadmill.{proid}'])
        grp.getgrnam.return_value = _MockGrp(['u1'])
        authorized, why = grp_authz.authorize(
            'u1@realm', 'create', 'r1', 'proidX.a', {}
        )
        self.assertTrue(authorized)
        grp.getgrnam.assert_called_with('treadmill.proidX')

        authorized, why = grp_authz.authorize(
            'u2@realm', 'create', 'r1', 'proidX.a', {}
        )
        self.assertFalse(authorized)


if __name__ == '__main__':
    unittest.main()
