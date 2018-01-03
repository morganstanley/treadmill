"""Unit test for treadmill.sproc.version_monitor"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

import treadmill
from treadmill.sproc import version_monitor


class VersionMonitorTest(unittest.TestCase):
    """Test treadmill.sproc.version_monitor"""

    @mock.patch('treadmill.zkutils.get_default', mock.Mock(return_value=[]))
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    def test_save_version(self):
        """Test _save_version.
        """
        # Disable W0212: Test access protected members of admin module.
        # pylint: disable=W0212

        zkclient = mock.Mock()
        hostname = 'testhost'
        version = {'a': 'a'}

        version_monitor._save_version(zkclient, hostname, version)

        treadmill.zkutils.put.assert_has_calls([
            mock.call(mock.ANY, '/version.history/testhost', [version])
        ])


if __name__ == '__main__':
    unittest.main()
