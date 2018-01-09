"""Unit test for cgutils module.
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

# Disable W0611: Unused import
import tests.treadmill_test_skip_windows  # pylint: disable=W0611

import mock

import treadmill
from treadmill import cgutils


class CGutilsTest(unittest.TestCase):
    """Tests for teadmill.cgutils.
    """
    _BLKIO_THROTTLE_IOPS = os.path.join(
        os.path.dirname(__file__),
        'blkio.throttle.io_serviced.data'
    )

    _BLKIO_THROTTLE_BPS = os.path.join(
        os.path.dirname(__file__),
        'blkio.throttle.io_service_bytes.data'
    )

    _BLKIO_BPS_EMPTY = os.path.join(
        os.path.dirname(__file__),
        'blkio.io_service_bytes.empty.data'
    )

    _BLKIO_SECTORS_EMPTY = os.path.join(
        os.path.dirname(__file__),
        'blkio.sectors.empty.data'
    )

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('io.open', mock.mock_open())
    @mock.patch('treadmill.cgroups.makepath', mock.Mock())
    @mock.patch('treadmill.cgroups.set_value', mock.Mock())
    @mock.patch('treadmill.syscall.eventfd.eventfd',
                mock.Mock(return_value=42))
    def test_get_memory_oom_eventfd(self):
        """Test registration of oom events.
        """
        treadmill.cgroups.makepath.return_value = 'mock_oom_control'
        mock_handle = io.open.return_value
        mock_handle.fileno.return_value = 43

        res = cgutils.get_memory_oom_eventfd('some_cgrp')

        treadmill.syscall.eventfd.eventfd.assert_called_with(
            0, treadmill.syscall.eventfd.EFD_CLOEXEC
        )
        treadmill.cgroups.makepath.assert_called_with(
            'memory', 'some_cgrp', 'memory.oom_control'
        )
        io.open.assert_called_with('mock_oom_control')
        treadmill.cgroups.set_value.assert_called_with(
            'memory', 'some_cgrp', 'cgroup.event_control',
            # '<eventfd_fd> <oom_control_fd>'
            '42 43'
        )
        # Should be returning the eventfd socket
        self.assertEqual(res, 42)

    @mock.patch('treadmill.cgroups.get_mountpoint',
                mock.Mock(return_value='/cgroups'))
    @mock.patch('os.rmdir', mock.Mock())
    def test_delete_rec(self):
        """Tests recursive cgroup deletion."""
        cgroups_dir = os.path.join(self.root, 'cgroups')
        treadmill.cgroups.get_mountpoint.return_value = cgroups_dir

        group = os.path.join('treadmill', 'apps', 'test1')
        # Create a directory and subdirs for the cgroup
        os.makedirs(os.path.join(cgroups_dir, group, 'foo', 'bar', 'baz'))

        cgutils.delete('cpu', group)

        os.rmdir.assert_has_calls([
            mock.call(os.path.join(cgroups_dir, group, 'foo/bar/baz')),
            mock.call(os.path.join(cgroups_dir, group, 'foo/bar')),
            mock.call(os.path.join(cgroups_dir, group, 'foo')),
            mock.call(os.path.join(cgroups_dir, group)),
        ])

    @mock.patch('treadmill.cgroups.get_data', mock.Mock())
    def test_get_blkio_bps_info(self):
        """Test reading of blkio throttle bps information."""

        with io.open(self._BLKIO_THROTTLE_BPS) as f:
            data = f.read()
            treadmill.cgroups.get_data.side_effect = [data]

        data = cgutils.get_blkio_info('mycgrp',
                                      'blkio.throttle.io_service_bytes')

        treadmill.cgroups.get_data.assert_called_with(
            'blkio', 'mycgrp', 'blkio.throttle.io_service_bytes'
        )
        self.assertEqual(
            data['253:6'],
            {
                'Read': 331776,
                'Write': 74817536,
                'Sync': 0,
                'Async': 75149312,
                'Total': 75149312,
            }
        )

    @mock.patch('treadmill.cgroups.get_data', mock.Mock())
    def test_get_blkio_info_empty(self):
        """Test reading of blkio information with empty file"""

        with io.open(self._BLKIO_BPS_EMPTY) as f:
            data = f.read()
            treadmill.cgroups.get_data.side_effect = [data]

        data = cgutils.get_blkio_info('mycgrp',
                                      'blkio.io_service_bytes')
        treadmill.cgroups.get_data.assert_called_with(
            'blkio', 'mycgrp', 'blkio.io_service_bytes'
        )
        self.assertEqual(
            data,
            {}
        )

    @mock.patch('treadmill.cgroups.get_data', mock.Mock())
    def test_get_blkio_value_empty(self):
        """Test reading of blkio information with empty file"""

        with io.open(self._BLKIO_SECTORS_EMPTY) as f:
            data = f.read()
            treadmill.cgroups.get_data.side_effect = [data]

        data = cgutils.get_blkio_value('mycgrp',
                                       'blkio.sectors')
        treadmill.cgroups.get_data.assert_called_with(
            'blkio', 'mycgrp', 'blkio.sectors'
        )
        self.assertEqual(
            data,
            {}
        )

    @mock.patch('treadmill.cgroups.get_data', mock.Mock())
    def test_get_blkio_iops_info(self):
        """Test reading of blkio throttle iops information."""

        with io.open(self._BLKIO_THROTTLE_IOPS) as f:
            data = f.read()
            treadmill.cgroups.get_data.side_effect = [data]

        data = cgutils.get_blkio_info('mycgrp',
                                      'blkio.throttle.io_serviced')

        treadmill.cgroups.get_data.assert_called_with(
            'blkio', 'mycgrp', 'blkio.throttle.io_serviced'
        )
        self.assertEqual(
            data['253:6'],
            {
                'Read': 81,
                'Write': 18266,
                'Sync': 0,
                'Async': 18347,
                'Total': 18347,
            }
        )


if __name__ == '__main__':
    unittest.main()
