"""Unit test for cgroups engine module.
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

from treadmill import fs
from treadmill.metrics import engine


class CgroupReaderTest(unittest.TestCase):
    """Test cgroups engine CgroupReader"""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        fs.mkdir_safe(os.path.join(self.root, 'init', 'fw'))
        fs.mkdir_safe(os.path.join(self.root, 'init', 'eventd'))
        fs.mkdir_safe(os.path.join(self.root, 'apps', 'foo'))

        # initialize common patchers
        self.app_metrics = mock.Mock()
        self.patchers = [
            mock.patch(
                'treadmill.cgroups._get_mountpoint',
                mock.Mock(return_value='/cgroups'),
            ),
            mock.patch(
                'treadmill.fs.linux.maj_min_to_blk',
                mock.Mock(return_value='/dev/sda3'),
            ),
            mock.patch(
                'treadmill.metrics.engine.CgroupReader._get_block_dev_version',
                mock.Mock(return_value=('/dev/foo', '1:0')),
            ),
            mock.patch(
                'treadmill.metrics.app_metrics',
                self.app_metrics,
            ),
        ]

        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

        for patcher in self.patchers:
            patcher.stop()

    def test_read_system(self):
        """Test read_system of engine.CgroupReader"""
        # default & configurable cgroup prefixes
        for cgroup_prefix in ['treadmill', 'tmpcz4qr_nl']:
            self.app_metrics.reset_mock()
            reader = engine.CgroupReader(self.root, cgroup_prefix)
            reader.read_system('treadmill')
            self.app_metrics.assert_called_once_with(
                cgroup_prefix, '/dev/sda3'
            )

            self.app_metrics.reset_mock()
            reader.read_system('system.slice')
            self.app_metrics.assert_called_once_with(
                'system.slice', '/dev/sda3'
            )

    def test_read_service(self):
        """Test read_service of engine.CgroupReader"""
        for cgroup_prefix in ['treadmill', 'tmprumsnf_y']:
            self.app_metrics.reset_mock()
            reader = engine.CgroupReader(self.root, cgroup_prefix)

            reader.read_service('fw')
            self.app_metrics.assert_called_once_with(
                '{0}/core/fw'.format(cgroup_prefix), None
            )

    def test_read_services(self):
        """Test read_services of engine.CgroupReader"""
        for cgroup_prefix in ['treadmill', 'tmp9c2q8lj2']:
            self.app_metrics.reset_mock()
            reader = engine.CgroupReader(self.root, cgroup_prefix)

            snapshot = reader.read_services(detail=True)
            self.assertSetEqual(set(snapshot.keys()), {'eventd', 'fw'})

            self.app_metrics.assert_has_calls(
                [
                    mock.call('{0}/core/fw'.format(cgroup_prefix), None),
                    mock.call('{0}/core/eventd'.format(cgroup_prefix), None),
                ],
                any_order=True
            )

    def test_read_app(self):
        """Test read_app of engine.CgroupReader"""
        for cgroup_prefix in ['treadmill', 'tmp5s8o17g5']:
            self.app_metrics.reset_mock()
            reader = engine.CgroupReader(self.root, cgroup_prefix)

            names = reader.read_app('foo')
            self.app_metrics.assert_called_once_with(
                '{0}/apps/foo'.format(cgroup_prefix), '/dev/foo'
            )

    def test_read_apps(self):
        """Test read_apps of engine.CgroupReader"""
        for cgroup_prefix in ['treadmill', 'tmphqy2ut38']:
            self.app_metrics.reset_mock()
            reader = engine.CgroupReader(self.root, cgroup_prefix)

            snapshot = reader.read_apps(detail=True)
            self.assertListEqual(list(snapshot), ['foo'])

            self.app_metrics.assert_called_once_with(
                '{0}/apps/foo'.format(cgroup_prefix), '/dev/foo'
            )


if __name__ == '__main__':
    unittest.main()
