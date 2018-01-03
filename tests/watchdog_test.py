"""Unit test for watchdog - Simple Watchdog System.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import io
import os
import shutil
import tempfile
import unittest

import mock

from treadmill import watchdog


class WatchdogTest(unittest.TestCase):
    """Tests for teadmill.watchdog.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.watchdog = watchdog.Watchdog(self.root)
        # Setup some entries
        for name, age in [('.tmp', 0),
                          ('foo', 10),
                          ('bar_30s', 15),
                          ('baz#lala', 40)]:
            fname = os.path.join(self.root, name)
            with io.open(fname, 'w') as f:
                f.write(name)
            os.utime(fname, (age, age))
        os.mkdir(os.path.join(self.root, 'food'))

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('os.unlink', mock.Mock())
    @mock.patch('os.chmod', mock.Mock())
    def test_initialize(self):
        """Test the watchdog dir initialization.
        """
        self.watchdog.initialize()

        os.unlink.assert_has_calls(
            [
                mock.call(os.path.join(self.root, 'foo')),
                mock.call(os.path.join(self.root, 'bar_30s')),
                mock.call(os.path.join(self.root, 'baz#lala')),
            ],
            any_order=True
        )
        self.assertEqual(os.unlink.call_count, 3)
        os.chmod.assert_called_with(self.root, 0o1777)

    @mock.patch('time.time', mock.Mock(return_value=0))
    def test_check_success(self):
        """Check the return value when all watchdog are alive.
        """
        result = self.watchdog.check()
        self.assertEqual(result, [])

    @mock.patch('time.time', mock.Mock(return_value=100))
    def test_check_failed_all(self):
        """Check the return value when all watchdog died.
        """
        result = self.watchdog.check()
        self.assertEqual(
            sorted(result),
            sorted([('foo', 10.0, 'foo'),
                    ('bar_30s', 15.0, 'bar_30s'),
                    ('baz#lala', 40.0, 'baz#lala')])
        )

    @mock.patch('time.time', mock.Mock(return_value=10))
    def test_check_failed_1(self):
        """Check the return value when one watchdog died.
        """
        result = self.watchdog.check()
        self.assertEqual(
            result,
            [('foo', 10.0, 'foo')]
        )

    @mock.patch('time.time', mock.Mock(return_value=15))
    def test_check_failed_2(self):
        """Check the return value when two watchdog died.
        """
        result = self.watchdog.check()
        self.assertEqual(
            sorted(result),
            sorted([('foo', 10.0, 'foo'),
                    ('bar_30s', 15.0, 'bar_30s')])
        )

    @mock.patch('time.time', mock.Mock(return_value=0))
    def test_create(self):
        """Test the watchdog heartbeat function.
        """
        l1 = self.watchdog.create('test1', '30s')
        self.assertTrue(os.path.isfile(os.path.join(self.root, 'test1')))
        self.assertEqual(
            os.path.join(self.root, 'test1'),
            l1.filename
        )
        with io.open(os.path.join(self.root, 'test1'), 'r') as f:
            self.assertEqual(f.read(), '')
        self.assertEqual(
            os.lstat(l1.filename).st_mtime,
            30
        )

        l2 = self.watchdog.create('test2', '2h', 'test message')
        self.assertTrue(os.path.isfile(os.path.join(self.root, 'test2')))
        self.assertEqual(
            os.path.join(self.root, 'test2'),
            l2.filename
        )
        with io.open(os.path.join(self.root, 'test2'), 'r') as f:
            self.assertEqual(f.read(), 'test message')
        self.assertEqual(
            os.lstat(l2.filename).st_mtime,
            60 * 60 * 2
        )

    @mock.patch('os.unlink', mock.Mock())
    def test_remove(self):
        """Test the watchdog removal function.
        """
        l1 = self.watchdog.create('test')

        l1.remove()

        os.unlink.assert_called_with(l1.filename)

        # Check that removing a watchdog that was already clean doesn't throw
        os.unlink.reset_mock()
        os.unlink.side_effect = OSError(errno.ENOENT, 'No such file')

        l1.remove()

        os.unlink.assert_called_with(l1.filename)

        # Make sure other errors still work
        os.unlink.reset_mock()
        os.unlink.side_effect = OSError(errno.EPERM, 'No access')

        self.assertRaises(OSError, l1.remove)

    @mock.patch('os.utime', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=0))
    @mock.patch('treadmill.watchdog.Watchdog.Lease._write', mock.Mock())
    def test_heartbeat(self):
        """Test the watchdog heartbeat function handles missing lease files.
        """
        # Access to a protected member _write of a client class
        # pylint: disable=W0212

        l1 = self.watchdog.create('test')

        # Ignore the first _write call
        watchdog.Watchdog.Lease._write.reset_mock()

        os.utime.side_effect = OSError(errno.ENOENT, 'No such file')

        l1.heartbeat()

        # It would be time.time() + timeout
        os.utime.assert_called_with(l1.filename, (l1.timeout, l1.timeout))
        self.assertTrue(watchdog.Watchdog.Lease._write.called)

    def test_names(self):
        """Tests watchdog name patterns.
        """
        self.watchdog.create('test', '5s', 'test')
        self.watchdog.create('app_run-test', '5s', 'test')
        self.watchdog.create('app_run-foo.bar#1234567890', '5s', 'test')
        self.watchdog.create('app_run-foo@a-b.bar#1234567890', '5s', 'test')


if __name__ == '__main__':
    unittest.main()
