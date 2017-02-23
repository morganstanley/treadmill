"""Unit test for treadmill.spawn.manifest_watch."""

import os
import time
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

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
        watch = manifest_watch.ManifestWatch('/does/not/exist')

        os.path.exists.return_value = False

        self.assertFalse(watch._check_path('test.yml'))

        os.path.exists.return_value = True

        self.assertFalse(watch._check_path('.test.yml'))
        self.assertFalse(watch._check_path('test'))
        self.assertTrue(watch._check_path('test.yml'))

    @mock.patch('os.chmod', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    def test_get_instance_path(self):
        """Tests that getting the instance path works correctly."""
        watch = manifest_watch.ManifestWatch('/does/not/exist')
        path = watch._get_instance_path('test.yml')

        self.assertEqual(path, '/does/not/exist/init/tm.test')

    @mock.patch('os.path.exists', mock.Mock(return_value=False))
    @mock.patch('os.chmod', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.utils.create_script', mock.Mock())
    @mock.patch('treadmill.spawn.manifest_watch.ManifestWatch._scan',
                mock.Mock())
    def test_create_instance(self):
        """Tests basic create instance funtionality."""
        watch = manifest_watch.ManifestWatch('/does/not/exist')

        watch._create_instance('test.yml')

        self.assertEquals(4, treadmill.fs.mkdir_safe.call_count)
        self.assertEquals(3, treadmill.utils.create_script.call_count)
        self.assertEquals(1, treadmill.spawn.manifest_watch.ManifestWatch
                          ._scan.call_count)

    @mock.patch('os.path.exists', mock.Mock(return_value=True))
    @mock.patch('os.chmod', mock.Mock())
    @mock.patch('time.sleep', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('shutil.rmtree', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.spawn.manifest_watch.ManifestWatch._scan',
                mock.Mock())
    def test_delete_instance(self):
        """Tests basic delete instance functionality."""
        watch = manifest_watch.ManifestWatch('/does/not/exist')
        watch = manifest_watch.ManifestWatch('/does/not/exist')

        watch._delete_instance('test.yml')

        self.assertEquals(1, treadmill.subproc.check_call.call_count)
        self.assertEquals(1, treadmill.subproc.check_call.call_count)
        self.assertEquals(1, time.sleep.call_count)
        self.assertEquals(1, treadmill.spawn.manifest_watch.ManifestWatch
                          ._scan.call_count)

    @mock.patch('os.listdir', mock.Mock())
    @mock.patch('os.path.exists', mock.Mock(return_value=True))
    @mock.patch('os.chmod', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch(
        'treadmill.spawn.manifest_watch.ManifestWatch._create_instance',
        mock.Mock())
    @mock.patch(
        'treadmill.spawn.manifest_watch.ManifestWatch._delete_instance',
        mock.Mock())
    def test_sync(self):
        """Tests the initial sync of the manifests."""
        os.listdir.side_effect = [
            ['.test1.yml', 'test2.yml', 'test4.yml', 'what'],
            ['manifest_watch', 'tm.test2', 'tm.test3']
        ]

        watch = manifest_watch.ManifestWatch('/does/not/exist')
        watch.sync()

        treadmill.spawn.manifest_watch.ManifestWatch._create_instance \
                 .assert_called_with('test4.yml')

        treadmill.spawn.manifest_watch.ManifestWatch._delete_instance \
                 .assert_called_with('test3.yml')


if __name__ == '__main__':
    unittest.main()
