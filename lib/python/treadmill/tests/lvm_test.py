"""Unit test for lvm - Linux Volume Manager
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

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import lvm


class LVMTest(unittest.TestCase):
    """Tests for teadmill.fs."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_pvcreate(self):
        """Test LVM Physical Volume creation"""
        lvm.pvcreate('some_blockdev')

        treadmill.subproc.check_call.assert_called_with(
            [
                'lvm', 'pvcreate',
                '--force',
                '--yes',
                'some_blockdev',
            ]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_pvremove(self):
        """Test LVM Physical Volume removal"""
        lvm.pvremove('some_blockdev')

        treadmill.subproc.check_call.assert_called_with(
            [
                'lvm', 'pvremove',
                '--force',
                'some_blockdev',
            ]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_vgcreate(self):
        """Test LVM Volume Group creation"""
        lvm.vgcreate('some_group', 'some_blockdev')

        treadmill.subproc.check_call.assert_called_with(
            [
                'lvm', 'vgcreate',
                '--autobackup', 'n',
                'some_group',
                'some_blockdev',
            ]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_vgremove(self):
        """Test LVM Volume Group deletion"""
        lvm.vgremove('some_group')

        treadmill.subproc.check_call.assert_called_with(
            [
                'lvm', 'vgremove',
                '--force',
                'some_group',
            ]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_vgactivate(self):
        """Test LVM Volume Group activation"""
        lvm.vgactivate('some_group')

        treadmill.subproc.check_call.assert_called_with(
            [
                'lvm', 'vgchange',
                '--activate', 'y',
                'some_group',
            ]
        )

    @mock.patch('treadmill.subproc.check_output', mock.Mock())
    def test_vgdisplay(self):
        """Test display of LVM group information.
        """
        treadmill.subproc.check_output.return_value = (
            '  test:r/w:772:-1:0:0:0:-1:0:1:1:98304:4096:'
            '24:0:24:Vsj4xA-45Ad-v4Rp-VOOf-XzEf-Gxwr-erL7Zu\n'
        )

        vg = lvm.vgdisplay('test')

        treadmill.subproc.check_output.assert_called_with(
            [
                'lvm',
                'vgdisplay',
                '--colon',
                'test',
            ]
        )
        self.assertEqual(
            vg,
            {
                'access': 'r/w',
                'extent_alloc': 0,
                'extent_free': 24,
                'extent_nb': 24,
                'extent_size': 4096,
                'lv_cur': 0,
                'lv_max': 0,
                'lv_open_count': 0,
                'max_size': -1,
                'name': 'test',
                'number': -1,
                'pv_actual': 1,
                'pv_cur': 1,
                'pv_max': 0,
                'size': 98304,
                'status': '772',
                'uuid': 'Vsj4xA-45Ad-v4Rp-VOOf-XzEf-Gxwr-erL7Zu',
            },
        )

    @mock.patch('treadmill.subproc.check_output', mock.Mock())
    def test_vgsdisplay(self):
        """Test display of list of LVM groups informations.
        """
        treadmill.subproc.check_output.return_value = (
            '  test:r/w:772:-1:0:0:0:-1:0:1:1:98304:4096:'
            '24:0:24:Vsj4xA-45Ad-v4Rp-VOOf-XzEf-Gxwr-erL7Zu\n'
            '  treadmill:r/w:772:-1:0:5:5:-1:0:1:1:35467264:4096:'
            '8659:1711:6948:MXvxzQ-gnXF-BXia-1pVo-KOH1-aJ4m-pIfnY8\n'
        )

        vgs = lvm.vgsdisplay()

        treadmill.subproc.check_output.assert_called_with(
            [
                'lvm',
                'vgdisplay',
                '--colon',
            ]
        )
        self.assertEqual(
            vgs,
            [
                {
                    'access': 'r/w',
                    'extent_alloc': 0,
                    'extent_free': 24,
                    'extent_nb': 24,
                    'extent_size': 4096,
                    'lv_cur': 0,
                    'lv_max': 0,
                    'lv_open_count': 0,
                    'max_size': -1,
                    'name': 'test',
                    'number': -1,
                    'pv_actual': 1,
                    'pv_cur': 1,
                    'pv_max': 0,
                    'size': 98304,
                    'status': '772',
                    'uuid': 'Vsj4xA-45Ad-v4Rp-VOOf-XzEf-Gxwr-erL7Zu',
                },
                {
                    'access': 'r/w',
                    'extent_alloc': 1711,
                    'extent_free': 6948,
                    'extent_nb': 8659,
                    'extent_size': 4096,
                    'lv_cur': 5,
                    'lv_max': 0,
                    'lv_open_count': 5,
                    'max_size': -1,
                    'name': 'treadmill',
                    'number': -1,
                    'pv_actual': 1,
                    'pv_cur': 1,
                    'pv_max': 0,
                    'size': 35467264,
                    'status': '772',
                    'uuid': 'MXvxzQ-gnXF-BXia-1pVo-KOH1-aJ4m-pIfnY8',
                },
            ]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_lvcreate(self):
        """Test LVM Logical Volume creation.
        """
        lvm.lvcreate('some_volume', '1024', 'some_group')

        treadmill.subproc.check_call.assert_called_with(
            [
                'lvm', 'lvcreate',
                '--autobackup', 'n',
                '--wipesignatures', 'y',
                '--size', '1024B',
                '--name', 'some_volume',
                'some_group',
            ]
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_lvremove(self):
        """Test LVM Logical Volume deletion.
        """
        lvm.lvremove('some_volume', 'some_group')

        treadmill.subproc.check_call.assert_called_with(
            [
                'lvm', 'lvremove',
                '--autobackup', 'n',
                '--force',
                'some_group/some_volume',
            ]
        )

    @mock.patch('treadmill.subproc.check_output', mock.Mock())
    def test_lvdisplay(self):
        """Test display of LVM volume information.
        """
        treadmill.subproc.check_output.return_value = (
            '  /dev/test/test-lv:test:3:1:-1:0:24576:'
            '3:-1:0:-1:253:5\n'
        )

        lv = lvm.lvdisplay('test-lv', 'test')

        treadmill.subproc.check_output.assert_called_with(
            [
                'lvm',
                'lvdisplay',
                '--colon',
                'test/test-lv',
            ]
        )
        self.assertEqual(
            lv,
            {
                'block_dev': '/dev/test/test-lv',
                'dev_major': 253,
                'dev_minor': 5,
                'extent_alloc': -1,
                'extent_size': 3,
                'group': 'test',
                'name': 'test-lv',
                'open_count': 0,
            },
        )

    @mock.patch('treadmill.subproc.check_output', mock.Mock())
    def test_lvsdisplay(self):
        """Test display of list of LVM volumes informations.
        """
        treadmill.subproc.check_output.return_value = (
            '  /dev/test/test-lv:test:3:1:-1:0:24576:'
            '3:-1:0:-1:253:5\n'
            '  /dev/treadmill/oRHxZN5QldMdz:treadmill:3:1:-1:1:10485760:'
            '1280:-1:0:-1:253:0\n'
            '  /dev/treadmill/ESE0g3hyf7nxv:treadmill:3:1:-1:1:2097152:'
            '256:-1:0:-1:253:1\n'
            '  /dev/treadmill/p8my37oRJGcd5:treadmill:3:1:-1:1:204800:'
            '25:-1:0:-1:253:2\n'
            '  /dev/treadmill/njZhRefmf6jQp:treadmill:3:1:-1:1:1024000:'
            '125:-1:0:-1:253:3\n'
            '  /dev/treadmill/yRImNK9cnix2T:treadmill:3:1:-1:1:204800:'
            '25:-1:0:-1:253:4\n'
        )

        lvs = lvm.lvsdisplay()

        treadmill.subproc.check_output.assert_called_with(
            [
                'lvm',
                'lvdisplay',
                '--colon',
            ]
        )
        self.assertEqual(
            lvs,
            [
                {
                    'block_dev': '/dev/test/test-lv',
                    'dev_major': 253,
                    'dev_minor': 5,
                    'extent_alloc': -1,
                    'extent_size': 3,
                    'group': 'test',
                    'name': 'test-lv',
                    'open_count': 0,
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
                    'block_dev': '/dev/treadmill/p8my37oRJGcd5',
                    'dev_major': 253,
                    'dev_minor': 2,
                    'extent_alloc': -1,
                    'extent_size': 25,
                    'group': 'treadmill',
                    'name': 'p8my37oRJGcd5',
                    'open_count': 1,
                },
                {
                    'block_dev': '/dev/treadmill/njZhRefmf6jQp',
                    'dev_major': 253,
                    'dev_minor': 3,
                    'extent_alloc': -1,
                    'extent_size': 125,
                    'group': 'treadmill',
                    'name': 'njZhRefmf6jQp',
                    'open_count': 1,
                },
                {
                    'block_dev': '/dev/treadmill/yRImNK9cnix2T',
                    'dev_major': 253,
                    'dev_minor': 4,
                    'extent_alloc': -1,
                    'extent_size': 25,
                    'group': 'treadmill',
                    'name': 'yRImNK9cnix2T',
                    'open_count': 1,
                },
            ]
        )


if __name__ == '__main__':
    unittest.main()
