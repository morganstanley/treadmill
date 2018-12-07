"""Unit test for node harvest.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import sys
import tempfile
import unittest
import tarfile

import mock

from treadmill import postmortem
from treadmill import utils


class PostmortemTest(unittest.TestCase):
    """Tests for teadmill.fs."""

    # Pylint complains about long names for test functions.
    # pylint: disable=C0103

    def setUp(self):
        self.tmroot = tempfile.mkdtemp()
        server_init_log = os.path.join('init', 'server_init', 'log')
        server_init_log_current = os.path.join(server_init_log, 'current')

        os.makedirs(os.path.join(self.tmroot, server_init_log))
        utils.touch(os.path.join(self.tmroot, server_init_log_current))

        self.service_log = os.path.join('running', 'foo', 'data', 'sys', 'bar',
                                        'data', 'log')
        self.service_log_current = os.path.join(self.service_log, 'current')

        os.makedirs(os.path.join(self.tmroot, self.service_log))
        utils.touch(os.path.join(self.tmroot, self.service_log_current))

        if sys.platform.startswith('linux'):
            os.makedirs(os.path.join(self.tmroot, 'localdisk_svc'))
            os.makedirs(os.path.join(self.tmroot, 'presence_svc'))
            os.makedirs(os.path.join(self.tmroot, 'network_svc'))
            os.makedirs(os.path.join(self.tmroot, 'cgroup_svc'))

        os.makedirs(os.path.join(self.tmroot, 'postmortem'))

    def tearDown(self):
        if self.tmroot and os.path.isdir(self.tmroot):
            shutil.rmtree(self.tmroot)

    @mock.patch('treadmill.subproc.check_output',
                mock.Mock(return_value='foo'))
    def test_collect(self):
        """test node information collection.
        """
        archive_path = os.path.join(self.tmroot,
                                    'postmortem',
                                    'archive.tar.gz')
        with tarfile.open(archive_path, 'w:gz') as archive:
            postmortem.collect(self.tmroot, archive, 'treadmill')
        with tarfile.open(archive_path, 'r:gz') as archive:
            listing = archive.getnames()
            self.assertTrue([
                path for path in listing
                if path.endswith('init/server_init/log/current')
            ])
            if os.name == 'posix':
                self.assertIn('diag/sysctl#-a', listing)


if __name__ == '__main__':
    unittest.main()
