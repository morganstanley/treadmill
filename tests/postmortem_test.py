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

import mock

from treadmill import postmortem
from treadmill import subproc
from treadmill import utils


class PostmortemTest(unittest.TestCase):
    """Tests for teadmill.fs."""

    # Pylint complains about long names for test functions.
    # pylint: disable=C0103

    def setUp(self):
        self.tmroot = tempfile.mkdtemp()
        self.archive_root = tempfile.mkdtemp()
        self.tmp_dir = os.path.join(tempfile.gettempdir(),
                                    'postmortem-%d' % os.getpid())

        self.server_init_log = os.path.join('init', 'server_init', 'log')
        self.server_init_log_current = os.path.join(self.server_init_log,
                                                    'current')

        os.makedirs(os.path.join(self.tmroot, self.server_init_log))
        utils.touch(os.path.join(self.tmroot, self.server_init_log_current))

        self.service_log = os.path.join('running', 'foo', 'data', 'sys', 'bar',
                                        'data', 'log')
        self.service_log_current = os.path.join(self.service_log, 'current')

        os.makedirs(os.path.join(self.tmroot, self.service_log))
        utils.touch(os.path.join(self.tmroot, self.service_log_current))

        if sys.platform.startswith('linux'):
            os.makedirs('%s/localdisk_svc' % self.tmroot)
            os.makedirs('%s/network_svc' % self.tmroot)
            os.makedirs('%s/cgroup_svc' % self.tmroot)

    def tearDown(self):
        if self.tmroot and os.path.isdir(self.tmroot):
            shutil.rmtree(self.tmroot)

        if self.archive_root and os.path.isdir(self.archive_root):
            shutil.rmtree(self.archive_root)

        if self.tmp_dir and os.path.isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir)

    @mock.patch('shutil.copyfile', mock.Mock())
    @mock.patch('shutil.copytree', mock.Mock())
    @mock.patch('tempfile.mkdtemp',
                mock.Mock(return_value=os.path.join(
                    tempfile.gettempdir(), 'postmortem-%d' % os.getpid())))
    @mock.patch('treadmill.subproc.check_output',
                mock.Mock(return_value='foo'))
    def test_collect_init_services(self):
        """test node information collection.
        """
        # XXX(boysson): Should be all os.path.join below
        archive_file = os.path.join(self.archive_root, 'archive.tar')
        real_file = postmortem.collect(self.tmroot, archive_file)
        self.assertEqual(real_file, os.path.join(self.archive_root,
                                                 'archive.tar.gz'))

        path = os.path.splitdrive(os.path.join(self.tmroot,
                                               self.service_log_current))[1]
        shutil.copyfile.assert_any_call(
            os.path.join(self.tmroot, self.service_log_current),
            '%s%s' % (self.tmp_dir, path)
        )

        if sys.platform.startswith('linux'):
            subproc.check_output.assert_any_call(['sysctl', '-a'])
            subproc.check_output.assert_any_call(['tail', '-n', '100',
                                                  '/var/log/messages'])
            subproc.check_output.assert_any_call(['dmesg'])
            subproc.check_output.assert_any_call(['ifconfig'])

            shutil.copytree.assert_any_call(
                '%s/network_svc' % self.tmroot,
                '%s%s/network_svc' % (self.tmp_dir, self.tmroot)
            )
            shutil.copytree.assert_any_call(
                '%s/cgroup_svc' % self.tmroot,
                '%s%s/cgroup_svc' % (self.tmp_dir, self.tmroot)
            )
            shutil.copytree.assert_any_call(
                '%s/localdisk_svc' % self.tmroot,
                '%s%s/localdisk_svc' % (self.tmp_dir, self.tmroot)
            )


if __name__ == '__main__':
    unittest.main()
