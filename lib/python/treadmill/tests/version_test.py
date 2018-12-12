"""Unit test for treadmill.version.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import version


class VersionTest(unittest.TestCase):
    """Test treadmill.version"""

    @mock.patch('treadmill.zkutils.get_default', mock.Mock(return_value=[]))
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    def test_save_version(self):
        """Test save_version.
        """
        zkclient = mock.Mock()
        hostname = 'testhost'
        node_version = {'a': 'a'}

        version.save_version(zkclient, hostname, node_version)

        treadmill.zkutils.put.assert_has_calls([
            mock.call(mock.ANY, '/version/testhost', node_version),
            mock.call(mock.ANY, '/version.history/testhost', [node_version])
        ])


if __name__ == '__main__':
    unittest.main()
