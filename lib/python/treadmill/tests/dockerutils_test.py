"""Unit test for treadmill.dockerutils
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import dockerutils


class DockerUtilsTest(unittest.TestCase):
    """Test treadmill common docker utils
    """

    @mock.patch('resource.getrlimit')
    def test_init_ulimit(self, mock_getrlimit):
        """test ulimit init method
        """
        mock_getrlimit.return_value = (1, 2)

        # pylint: disable=protected-access
        self.assertEqual(
            dockerutils.init_ulimit([]),
            [
                {'Name': 'core', 'Soft': 1, 'Hard': 2},
                {'Name': 'data', 'Soft': 1, 'Hard': 2},
                {'Name': 'fsize', 'Soft': 1, 'Hard': 2},
                {'Name': 'nproc', 'Soft': 1, 'Hard': 2},
                {'Name': 'nofile', 'Soft': 1, 'Hard': 2},
                {'Name': 'rss', 'Soft': 1, 'Hard': 2},
                {'Name': 'stack', 'Soft': 1, 'Hard': 2},
            ]
        )
        mock_getrlimit.assert_has_calls([
            mock.call(4),   # RLIMIT_CORE
            mock.call(2),   # RLIMIT_DATA
            mock.call(1),   # RLIMIT_FSIZE
            mock.call(6),   # RLIMIT_NPROC
            mock.call(7),   # RLIMIT_NOFILE
            mock.call(5),   # RLIMIT_RSS
            mock.call(3),   # RLIMIT_STACK
        ])
        # self.assertEqual(sproc_docker._init_ulimit(None), [])
        self.assertEqual(
            dockerutils.init_ulimit(['nofile:10:10', 'core:20:20']),
            [
                {'Name': 'core', 'Soft': 20, 'Hard': 20},
                {'Name': 'data', 'Soft': 1, 'Hard': 2},
                {'Name': 'fsize', 'Soft': 1, 'Hard': 2},
                {'Name': 'nproc', 'Soft': 1, 'Hard': 2},
                {'Name': 'nofile', 'Soft': 10, 'Hard': 10},
                {'Name': 'rss', 'Soft': 1, 'Hard': 2},
                {'Name': 'stack', 'Soft': 1, 'Hard': 2},
            ]
        )
