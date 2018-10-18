"""Unit test for treadmill.spawn.manifest_watch.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill.spawn import manifest_watch


class ManifestWatchTest(unittest.TestCase):
    """Tests for teadmill.spawn.manifest_watch."""

    # Disable W0212: Access to a protected member
    # pylint: disable=W0212

    @mock.patch('os.chmod', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('os.path.exists', mock.Mock())
    def test_check_path(self):
        """Tests that the manifiest watch validates manifest filenames."""
        watch = manifest_watch.ManifestWatch('/does/not/exist', 2)

        os.path.exists.return_value = False

        self.assertFalse(watch._check_path('test.yml'))

        os.path.exists.return_value = True

        self.assertFalse(watch._check_path('.test.yml'))
        self.assertFalse(watch._check_path('test'))
        self.assertTrue(watch._check_path('test.yml'))

    @mock.patch('io.open', mock.mock_open(), create=True)
    @mock.patch('os.path.exists', mock.Mock(return_value=False))
    @mock.patch('os.chmod', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.fs.symlink_safe', mock.Mock())
    @mock.patch('treadmill.templates.create_script', mock.Mock())
    @mock.patch('treadmill.spawn.manifest_watch.ManifestWatch._scan',
                mock.Mock())
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={}))
    def test_create_instance(self):
        """Tests basic create instance functionality."""
        watch = manifest_watch.ManifestWatch('/does/not/exist', 2)

        watch._create_instance('test.yml')

        self.assertEqual(4, treadmill.fs.mkdir_safe.call_count)
        self.assertEqual(2, treadmill.templates.create_script.call_count)
        self.assertEqual(1, treadmill.fs.symlink_safe.call_count)
        io.open.assert_has_calls(
            [
                mock.call(
                    '/does/not/exist/apps/jobs/test/data/manifest', 'w'),
                mock.call(
                    '/does/not/exist/apps/jobs/test/timeout-finish', 'w')
            ],
            any_order=True
        )
        self.assertEqual(
            1,
            treadmill.spawn.manifest_watch.ManifestWatch._scan.call_count
        )

    @mock.patch('os.listdir', mock.Mock())
    @mock.patch('os.path.exists', mock.Mock(return_value=True))
    @mock.patch('os.chmod', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch(
        'treadmill.spawn.manifest_watch.ManifestWatch._create_instance',
        mock.Mock())
    def test_sync(self):
        """Tests the initial sync of the manifests."""
        os.listdir.side_effect = [
            ['.test1.yml', 'test4.yml', 'what'],
        ]

        watch = manifest_watch.ManifestWatch('/does/not/exist', 2)
        watch.sync()

        treadmill.spawn.manifest_watch.ManifestWatch._create_instance \
                 .assert_called_with('/does/not/exist/manifest/test4.yml')


if __name__ == '__main__':
    unittest.main()
