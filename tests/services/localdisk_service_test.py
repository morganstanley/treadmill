"""Unit test for localdisk_service - Treadmill local disk service.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import os
import shutil
import tempfile
import unittest

import mock
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

import treadmill
from treadmill import localdiskutils
from treadmill.services import localdisk_service


class LocalDiskServiceTest(unittest.TestCase):
    """Unit tests for the local disk service implementation.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_event_handlers(self):
        """Test event_handlers request.
        """
        svc = localdisk_service.LocalDiskResourceService(
            block_dev='/dev/block',
            read_bps='100M',
            write_bps='100M',
            read_iops=1000,
            write_iops=1000

        )

        self.assertEqual(
            svc.event_handlers(),
            []
        )

    @mock.patch('treadmill.lvm.vgdisplay', mock.Mock())
    def test_report_status(self):
        """Test service status reporting.
        """
        # Access to a protected member _vg_status
        # pylint: disable=W0212

        svc = localdisk_service.LocalDiskResourceService(
            block_dev='/dev/block',
            read_bps='100M',
            write_bps='100M',
            read_iops=1000,
            write_iops=1000
        )
        svc._vg_status = {'test': 'me'}

        status = svc.report_status()

        self.assertEqual(status, {
            'test': 'me',
            'read_bps': '100M',
            'write_bps': '100M',
            'read_iops': 1000,
            'write_iops': 1000
        })

    @mock.patch('treadmill.cgroups.create', mock.Mock())
    @mock.patch('treadmill.cgroups.set_value', mock.Mock())
    @mock.patch('treadmill.fs.create_filesystem', mock.Mock())
    @mock.patch('treadmill.lvm.lvcreate', mock.Mock())
    @mock.patch('treadmill.lvm.lvdisplay', mock.Mock())
    @mock.patch('treadmill.localdiskutils.refresh_vg_status',
                mock.Mock())
    def test_on_create_request(self):
        """Test processing of a localdisk create request.
        """
        # Access to a protected member _vg_status
        # pylint: disable=W0212

        svc = localdisk_service.LocalDiskResourceService(
            block_dev='/dev/block',
            read_bps='100M',
            write_bps='100M',
            read_iops=1000,
            write_iops=1000
        )
        svc._vg_status = {
            'extent_size': 4 * 1024**3,
            'extent_free': 512,
        }
        request = {
            'size': '100M',
        }
        request_id = 'myproid.test-0-ID1234'
        treadmill.lvm.lvdisplay.return_value = {
            'block_dev': '/dev/test',
            'dev_major': 42,
            'dev_minor': 43,
            'extent_size': 10,
            'name': 'ID1234',
        }

        localdisk = svc.on_create_request(request_id, request)

        treadmill.lvm.lvcreate.assert_called_with(
            volume='ID1234',
            group='treadmill',
            size_in_bytes=100 * 1024 * 1024,
        )
        self.assertTrue(
            treadmill.localdiskutils.refresh_vg_status.called
        )
        cgrp = os.path.join('treadmill/apps', request_id)
        treadmill.cgroups.create.assert_called_with(
            'blkio', cgrp
        )

        treadmill.cgroups.set_value.assert_has_calls(
            [
                mock.call('blkio', cgrp,
                          'blkio.throttle.read_bps_device',
                          '42:43 20971520'),
                mock.call('blkio', cgrp,
                          'blkio.throttle.read_iops_device',
                          '42:43 100'),
                mock.call('blkio', cgrp,
                          'blkio.throttle.write_bps_device',
                          '42:43 20971520'),
                mock.call('blkio', cgrp,
                          'blkio.throttle.write_iops_device',
                          '42:43 100'),
            ],
            any_order=True
        )
        self.assertEqual(
            localdisk,
            {
                'block_dev': '/dev/test',
                'dev_major': 42,
                'dev_minor': 43,
                'extent_size': 10,
                'name': 'ID1234',
            }
        )

    @mock.patch('treadmill.cgroups.create', mock.Mock())
    @mock.patch('treadmill.cgroups.set_value', mock.Mock())
    @mock.patch('treadmill.fs.create_filesystem', mock.Mock())
    @mock.patch('treadmill.lvm.lvcreate', mock.Mock())
    @mock.patch('treadmill.lvm.lvdisplay', mock.Mock())
    @mock.patch('treadmill.localdiskutils.refresh_vg_status',
                mock.Mock())
    def test_on_create_request_existing(self):
        """Test processing of a localdisk create request when volume already
        created.
        """
        # Access to a protected member _vg_status
        # pylint: disable=W0212

        svc = localdisk_service.LocalDiskResourceService(
            block_dev='/dev/block',
            read_bps='100M',
            write_bps='100M',
            read_iops=1000,
            write_iops=1000
        )
        svc._vg_status = {
            'extent_size': 4 * 1024**3,
            'extent_free': 512,
        }
        treadmill.lvm.lvdisplay.return_value = {
            'block_dev': '/dev/test',
            'dev_major': 42,
            'dev_minor': 43,
            'extent_size': 10,
            'name': 'ID1234',
        }
        request = {
            'size': '100M',
        }
        request_id = 'myproid.test-0-ID1234'
        localdisk = svc.on_create_request(request_id, request)
        # Reset all mocks
        treadmill.cgroups.create.reset_mock()
        treadmill.cgroups.set_value.reset_mock()
        treadmill.fs.create_filesystem.reset_mock()
        treadmill.lvm.lvcreate.reset_mock()
        treadmill.lvm.lvdisplay.reset_mock()
        treadmill.localdiskutils.refresh_vg_status.reset_mock()
        treadmill.lvm.lvdisplay.return_value = {
            'block_dev': '/dev/test',
            'dev_major': 24,
            'dev_minor': 34,
            'extent_size': 10,
            'name': 'ID1234',
        }
        # Issue a second request
        localdisk = svc.on_create_request(request_id, request)

        self.assertFalse(treadmill.lvm.lvcreate.called)
        self.assertFalse(
            treadmill.localdiskutils.refresh_vg_status.called
        )
        cgrp = os.path.join('treadmill/apps', request_id)
        treadmill.cgroups.create.assert_called_with(
            'blkio', cgrp
        )
        treadmill.cgroups.set_value.assert_has_calls(
            [
                mock.call('blkio', cgrp,
                          'blkio.throttle.read_bps_device',
                          '24:34 20971520'),
                mock.call('blkio', cgrp,
                          'blkio.throttle.read_iops_device',
                          '24:34 100'),
                mock.call('blkio', cgrp,
                          'blkio.throttle.write_bps_device',
                          '24:34 20971520'),
                mock.call('blkio', cgrp,
                          'blkio.throttle.write_iops_device',
                          '24:34 100'),
            ],
            any_order=True
        )
        self.assertEqual(
            localdisk,
            {
                'block_dev': '/dev/test',
                'dev_major': 24,
                'dev_minor': 34,
                'extent_size': 10,
                'name': 'ID1234',
            }
        )

    @mock.patch('treadmill.lvm.lvdisplay', mock.Mock())
    @mock.patch('treadmill.lvm.lvremove', mock.Mock())
    @mock.patch('treadmill.localdiskutils.refresh_vg_status',
                mock.Mock())
    def test_on_delete_request(self):
        """Test processing of a localdisk delete request.
        """
        # Access to a protected member
        # pylint: disable=W0212

        svc = localdisk_service.LocalDiskResourceService(
            block_dev='/dev/block',
            read_bps='100M',
            write_bps='100M',
            read_iops=1000,
            write_iops=1000
        )
        request_id = 'myproid.test-0-ID1234'

        svc.on_delete_request(request_id)

        treadmill.lvm.lvremove.assert_called_with('ID1234', group='treadmill')
        self.assertTrue(
            treadmill.localdiskutils.refresh_vg_status.called
        )

    @mock.patch('treadmill.lvm.vgdisplay', mock.Mock())
    def test__refresh_vg_status(self):
        """Test LVM volume group status querying.
        """
        # Access to a protected member
        # pylint: disable=W0212

        treadmill.lvm.vgdisplay.return_value = {
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
        }

        status = localdiskutils.refresh_vg_status('FOO')

        treadmill.lvm.vgdisplay.assert_called_with(group='FOO')
        self.assertEqual(
            status,
            {
                'extent_free': 24,
                'extent_nb': 24,
                'extent_size': 4194304,
                'name': 'test',
                'size': 100663296,
            }
        )

    @mock.patch('treadmill.lvm.pvcreate', mock.Mock())
    @mock.patch('treadmill.lvm.vgactivate', mock.Mock())
    @mock.patch('treadmill.lvm.vgcreate', mock.Mock())
    def test__init_vg(self):
        """Test LVM volume group initialization.
        """
        # pylint: disable=W0212

        treadmill.lvm.vgactivate.side_effect = [
            subprocess.CalledProcessError(returncode=5, cmd='lvm'),
            0,
        ]

        localdiskutils.init_vg('test-group', '/dev/test')

        treadmill.lvm.pvcreate.assert_called_with(device='/dev/test')
        treadmill.lvm.vgcreate.assert_called_with(
            'test-group',
            device='/dev/test'
        )
        treadmill.lvm.vgactivate.assert_called_with('test-group')

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.localdiskutils.loop_dev_for',
                mock.Mock())
    @mock.patch('treadmill.localdiskutils.init_loopback_devices',
                mock.Mock())
    @mock.patch('treadmill.localdiskutils.create_image',
                mock.Mock())
    def test__init_block_dev(self):
        """Create a backing block device for LVM's Treadmill volume group.
        """
        # pylint: disable=W0212

        localdiskutils.loop_dev_for.side_effect = [
            subprocess.CalledProcessError(returncode=1, cmd='losetup'),
            '/dev/test'
        ]

        res = localdiskutils.init_block_dev('treadmill.img', '/bar', '2G')

        self.assertTrue(localdiskutils.init_loopback_devices.called)
        localdiskutils.create_image.assert_called_with(
            localdiskutils.TREADMILL_IMG,
            '/bar',
            '2G'
        )
        self.assertEqual(res, '/dev/test')

    @mock.patch('os.stat', mock.Mock())
    @mock.patch('os.unlink', mock.Mock())
    @mock.patch('treadmill.fs.create_excl', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.sysinfo.disk_usage', mock.Mock(
        return_value=collections.namedtuple('struct', 'free')(10 * 1024**3)
    ))
    def test__create_image(self):
        """Test image file creation.
        """
        # pylint: disable=W0212

        localdiskutils.create_image('foo', '/bar', '-2G')

        treadmill.fs.mkdir_safe.assert_called_with('/bar')
        os.stat.assert_called_with('/bar/foo')
        os.unlink.assert_called_with('/bar/foo')
        treadmill.fs.create_excl.assert_called_with(
            '/bar/foo',
            (10 * 1024**3) - (2 * 1024**3),  # 10G free - 2G reserve
        )


if __name__ == '__main__':
    unittest.main()
