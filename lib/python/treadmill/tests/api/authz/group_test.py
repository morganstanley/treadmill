"""Group Authz API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from collections import namedtuple
import unittest

import mock

import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill.api.authz import group


_MockGrp = namedtuple('grp', ['gr_mem'])


class GroupAuthzTest(unittest.TestCase):
    """treadmill.api.authz.group tests."""

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @mock.patch('grp.getgrnam')
    def test_authorize(self, mock_getgrnam):
        """Dummy test for treadmill.api.cell.get()"""
        # set templates directly.
        grp_authz = group.API(groups=['treadmill.{proid}'])
        mock_getgrnam.return_value = _MockGrp(['u1'])

        authorized, _ = grp_authz.authorize(
            'u1@realm', 'create', 'r1', {'pk': 'proidX.a'}
        )
        self.assertTrue(authorized)
        mock_getgrnam.assert_called_with('treadmill.proidX')

        authorized, _ = grp_authz.authorize(
            'u1@realm', 'bulk_delete', 'r1', {'pk': 'proidX',
                                              'rsrc': '[whatever]'}
        )
        self.assertTrue(authorized)
        mock_getgrnam.assert_called_with('treadmill.proidX')

        authorized, _ = grp_authz.authorize(
            'u2@realm', 'create', 'r1', {'pk': 'proidX.a'}
        )
        self.assertFalse(authorized)


if __name__ == '__main__':
    unittest.main()
