"""Unit tests for local disk utils.
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
from treadmill import localdiskutils
from treadmill import subproc


class LocalDiskTest(unittest.TestCase):
    """Unit tests for local disk utils"""

    @mock.patch('treadmill.lvm.vgactivate', mock.Mock())
    @mock.patch('treadmill.lvm.lvsdisplay', mock.Mock())
    @mock.patch('treadmill.localdiskutils.init_block_dev',
                mock.Mock())
    @mock.patch('treadmill.localdiskutils.init_vg', mock.Mock())
    @mock.patch('treadmill.localdiskutils.refresh_vg_status',
                mock.Mock())
    def test_initialize_quick(self):
        """Test service initialization (quick restart).
        """
        # pylint: disable=W0212

        img_location = '/image_dir'
        img_size = 42

        treadmill.lvm.vgactivate.return_value = True

        treadmill.lvm.lvsdisplay.return_value = [
            {
                'block_dev': '/dev/treadmill/ESE0g3hyf7nxv',
                'dev_major': 253,
                'dev_minor': 1,
                'extent_alloc': -1,
                'extent_size': 256,
                'group': 'treadmill',
                'name': 'ESE0g3hyf7nxv',
                'open_count': 1,
            },
            {
                'block_dev': '/dev/treadmill/oRHxZN5QldMdz',
                'dev_major': 253,
                'dev_minor': 0,
                'extent_alloc': -1,
                'extent_size': 1280,
                'group': 'treadmill',
                'name': 'oRHxZN5QldMdz',
                'open_count': 1,
            },
        ]

        localdiskutils.setup_image_lvm(
            localdiskutils.TREADMILL_IMG,
            img_location,
            img_size
        )

        treadmill.lvm.vgactivate.assert_called_with(group='treadmill')

        # If present, we should *not* try to re-init the volume group
        self.assertFalse(
            treadmill.localdiskutils.init_block_dev.called
        )
        self.assertFalse(treadmill.localdiskutils.init_vg.called)

    @mock.patch('treadmill.lvm.vgactivate', mock.Mock())
    @mock.patch('treadmill.lvm.lvsdisplay', mock.Mock())
    @mock.patch('treadmill.localdiskutils.init_block_dev',
                mock.Mock())
    @mock.patch('treadmill.localdiskutils.init_vg', mock.Mock())
    @mock.patch('treadmill.localdiskutils.refresh_vg_status',
                mock.Mock())
    def test_initialize_img(self):
        """Test service initialization (image).
        """
        # pylint: disable=W0212

        img_location = '/image_dir'
        img_size = 42

        treadmill.lvm.vgactivate.side_effect = \
            subproc.CalledProcessError(returncode=5, cmd='lvm')
        mock_init_blkdev = treadmill.localdiskutils.init_block_dev
        mock_init_blkdev.return_value = '/dev/test'
        treadmill.lvm.lvsdisplay.return_value = []

        localdiskutils.setup_image_lvm(
            localdiskutils.TREADMILL_IMG,
            img_location,
            img_size
        )

        treadmill.lvm.vgactivate.assert_called_with(group='treadmill')
        mock_init_blkdev.assert_called_with('treadmill.img', '/image_dir', 42)
        treadmill.localdiskutils.init_vg.assert_called_with(
            'treadmill',
            '/dev/test',
        )

    @mock.patch('treadmill.lvm.vgactivate', mock.Mock())
    @mock.patch('treadmill.lvm.lvsdisplay', mock.Mock())
    @mock.patch('treadmill.localdiskutils.init_block_dev',
                mock.Mock())
    @mock.patch('treadmill.localdiskutils.init_vg', mock.Mock())
    @mock.patch('treadmill.localdiskutils.refresh_vg_status',
                mock.Mock())
    def test_initialize_blk(self):
        """Test service initialization (block device).
        """
        # pylint: disable=W0212

        block_dev = '/dev/test'

        treadmill.lvm.vgactivate.side_effect = \
            subproc.CalledProcessError(returncode=5, cmd='lvm')
        treadmill.lvm.lvsdisplay.return_value = []

        localdiskutils.setup_device_lvm(block_dev)

        treadmill.lvm.vgactivate.assert_called_with(group='treadmill')
        # If provided, we should try to create the block device
        self.assertFalse(
            treadmill.localdiskutils.init_block_dev.called
        )
        treadmill.localdiskutils.init_vg.assert_called_with(
            'treadmill',
            '/dev/test',
        )
