"""Tests for treadmill.runtime.linux.image.docker.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import tempfile
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows   # pylint: disable=W0611

from treadmill import fs
from treadmill.runtime.linux.image import _docker


class DockerTest(unittest.TestCase):
    """test docker function for linux native runtime
    """

    def setUp(self):
        self.root_dir = tempfile.mkdtemp()
        fs.mkdir_safe(os.path.join(self.root_dir, 'docker', 'etc'))

    def tearDown(self):
        if self.root_dir and os.path.isdir(self.root_dir):
            shutil.rmtree(self.root_dir)

    @mock.patch('treadmill.utils.get_uid_gid', mock.Mock(return_value=(1, 1)))
    def test__create_overlay_passwd(self):
        """Test create overlay passwd file
        """
        # pylint: disable=protected-access
        _docker._create_overlay_passwd(self.root_dir, 'me')
        passwd = os.path.join(self.root_dir, 'docker', 'etc', 'passwd')
        self.assertTrue(os.path.isfile(passwd))
        with io.open(passwd) as f:
            self.assertEqual(
                'root:x:0:0:root:/root:/bin/sh\nme:x:1:1::/:/sbin/nologin\n',
                f.read()
            )

    @mock.patch(
        'grp.getgrgid',
        mock.Mock(return_value=mock.Mock(gr_name='foo'))
    )
    @mock.patch('treadmill.utils.get_uid_gid', mock.Mock(return_value=(1, 1)))
    def test__create_overlay_group(self):
        """Test create overlay group file
        """
        # pylint: disable=protected-access
        _docker._create_overlay_group(self.root_dir, 'me')
        group = os.path.join(self.root_dir, 'docker', 'etc', 'group')
        self.assertTrue(os.path.isfile(group))
        with io.open(group) as f:
            self.assertEqual(
                'root:x:0\nfoo:x:1\n',
                f.read()
            )


if __name__ == '__main__':
    unittest.main()
