"""Unit test for node harvest.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest

import mock

from treadmill import postmortem
from treadmill import subproc


class postmortemTest(unittest.TestCase):
    """Tests for teadmill.fs."""

    # Pylint complains about long names for test functions.
    # pylint: disable=C0103

    def setUp(self):
        self.tmroot = tempfile.mkdtemp()
        self.archive_root = tempfile.mkdtemp()
        self.tmp_dir = '/tmp/postmortem-%d' % os.getpid()

        os.makedirs('%s/init/server_init/log' % self.tmroot)
        os.mknod('%s/init/server_init/log/current' % self.tmroot)

        os.makedirs('%s/running/foo/data/sys/bar/data/log' % self.tmroot)
        os.mknod('%s/running/foo/data/sys/bar/data/log/current' % self.tmroot)

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
                mock.Mock(return_value='/tmp/postmortem-%d' % os.getpid()))
    @mock.patch('treadmill.subproc.check_output',
                mock.Mock(return_value='foo'))
    def test_collect_init_services(self):
        """test node information collection.
        """
        # XXX(boysson): Should be all os.path.join below
        archive_file = '%s/archive.tar' % self.archive_root
        real_file = postmortem.collect(self.tmroot, archive_file)
        self.assertEqual(real_file, '%s/archive.tar.gz' % self.archive_root)

        shutil.copyfile.assert_any_call(
            '%s/init/server_init/log/current' % self.tmroot,
            '%s%s/init/server_init/log/current' % (self.tmp_dir,
                                                   self.tmroot)
        )
        shutil.copyfile.assert_any_call(
            '%s/running/foo/data/sys/bar/data/log/current' % self.tmroot,
            '%s%s/running/foo/data/sys/bar/data/log/current' % (self.tmp_dir,
                                                                self.tmroot)
        )

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
