"""
Unit test for cgutils module.
"""

import builtins
import os
import shutil
import tempfile
import unittest

import mock

import treadmill
from treadmill import cgutils


class CGutilsTest(unittest.TestCase):
    """Tests for teadmill.cgutils.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('builtins.open')
    @mock.patch('treadmill.cgroups.makepath', mock.Mock())
    @mock.patch('treadmill.cgroups.set_value', mock.Mock())
    @mock.patch('treadmill.syscall.eventfd.eventfd',
                mock.Mock(return_value=42))
    def test_get_memory_oom_eventfd(self, mock_open):
        """Test registration of oom events.
        """
        treadmill.cgroups.makepath.return_value = 'mock_oom_control'
        mock_fileobj = mock_open.return_value
        mock_filectx = mock_fileobj.__enter__.return_value
        mock_filectx.fileno.return_value = 43

        res = cgutils.get_memory_oom_eventfd('some_cgrp')

        treadmill.syscall.eventfd.eventfd.assert_called_with(
            0, treadmill.syscall.eventfd.EFD_CLOEXEC
        )
        treadmill.cgroups.makepath.assert_called_with(
            'memory', 'some_cgrp', 'memory.oom_control'
        )
        builtins.open.assert_called_with('mock_oom_control')
        treadmill.cgroups.set_value.assert_called_with(
            'memory', 'some_cgrp', 'cgroup.event_control',
            # '<eventfd_fd> <oom_control_fd>'
            '42 43'
        )
        # Should be returning the eventfd socket
        self.assertEqual(res, 42)


if __name__ == '__main__':
    unittest.main()
