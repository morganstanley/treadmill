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

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch(
        'treadmill.cgroups._get_mountpoint',
        mock.Mock(return_value='/cgroups'))
    @mock.patch(
        'treadmill.fs.linux.maj_min_to_blk',
        mock.Mock(return_value='/dev/sda3'))
    @mock.patch(
        'treadmill.metrics.engine.CgroupReader._get_block_dev_version',
        mock.Mock(return_value=('/dev/foo', '1:0')))
    @mock.patch(
        'treadmill.metrics.app_metrics',
        mock.Mock())
    def test_read(self):
        """Test _read of engine.CgroupReader"""
        engine_obj = engine.CgroupReader(self.root, 0)

        self.assertEqual(
            set(engine_obj.cache['treadmill'].keys()),
            set(['core', 'apps', 'treadmill'])
        )

        self.assertEqual(
            set(engine_obj.cache['core'].keys()),
            set(['fw', 'eventd'])
        )

        self.assertEqual(
            set(engine_obj.cache['app'].keys()),
            set(['foo'])
        )

        self.assertEqual(
            set(engine_obj.list()),
            set(['treadmill.core',
                 'treadmill.apps',
                 'treadmill.treadmill',
                 'core.eventd',
                 'core.fw',
                 'app.foo'])
        )
