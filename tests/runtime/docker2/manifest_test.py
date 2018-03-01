"""Unit test for treadmill.runtime.docker2._manifest.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# Disable C0302: Too many lines in module.
# pylint: disable=C0302

import os
import shutil
import socket
import stat
import tempfile
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_skip_windows   # pylint: disable=W0611
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock


from treadmill.runtime.docker2 import _manifest as app_manifest


class Docker2RuntimeManifestTest(unittest.TestCase):
    """Tests for treadmill.runtime.docker2._manifest."""

    def setUp(self):
        self.tm_env = mock.Mock(
            root='/var/tmp/treadmill/app/approot',
            cell='testcell',
            zkurl='zookeeper://foo@foo:123',
            apps_dir='apps',
        )
        self.maxDiff = None

    def tearDown(self):
        pass

    @mock.patch('treadmill.dist.TREADMILL_BIN', '/path/to/treadcmill34')
    @mock.patch('treadmill.runtime.docker2._manifest._get_user_uid_gid',
                mock.Mock(return_value=(274091, 19290)))
    def test_generate_command(self):
        cmd = app_manifest._generate_command(
            'sleep 10', 'foo'
        )
        self.assertEqual(cmd, 'sleep 10')

        cmd = app_manifest._generate_command(
            'docker://testwt2', 'foo'
        )
        self.assertEqual(
            cmd,
            (
                'exec /path/to/treadcmill34 sproc docker'
                ' --unique_id foo'
                ' --envdirs /env,/services/foo/env'
                ' --image testwt2'
                ' --volume /var/tmp:/var/tmp:rw'
                ' --volume /var/spool:/var/spool:rw'
            )
        )

        cmd = app_manifest._generate_command(
            'docker://testwt2 foo bar', 'foo'
        )
        self.assertEqual(
            cmd,
            (
                'exec /path/to/treadcmill34 sproc docker'
                ' --unique_id foo'
                ' --envdirs /env,/services/foo/env'
                ' --image testwt2'
                ' --volume /var/tmp:/var/tmp:rw'
                ' --volume /var/spool:/var/spool:rw'
                ' --'
                ' foo bar'
            )
        )


if __name__ == '__main__':
    unittest.main()
