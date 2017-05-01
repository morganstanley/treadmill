"""Local API tests."""

import os
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

from treadmill.api import local
from treadmill.exc import (FileNotFoundError, InvalidInputError)

METRICS_DIR = '.../metrics'
ARCHIVES_DIR = '.../archives'

# do not complain about accessing protected member
# pylint: disable=W0212


class MetricsAPITest(unittest.TestCase):
    """treadmill.api.local._MetricsAPI tests."""

    def setUp(self):
        tm_env = mock.Mock()
        tm_env.metrics_dir = METRICS_DIR
        tm_env.archives_dir = ARCHIVES_DIR

        tm_env_func = mock.Mock()
        tm_env_func.return_value = tm_env

        self.met = local._MetricsAPI(tm_env_func)

    def test_metrics_fpath(self):
        """Test the path for application and service rrd metrics"""
        self.assertEqual(
            self.met._metrics_fpath(app='proid.app#00123',
                                    uniq='asdf'),
            '{}/apps/proid.app-00123-asdf.rrd'.format(METRICS_DIR))
        self.assertEqual(
            self.met._metrics_fpath(service='test'),
            '{}/core/test.rrd'.format(METRICS_DIR))

    def test_unpack_id(self):
        """Test the unpack_id() method."""
        self.assertEqual(self.met._unpack_id('test'), {'service': 'test'})
        self.assertEqual(
            self.met._unpack_id('proid.app#123/asdf'), {'app': 'proid.app#123',
                                                        'uniq': 'asdf'})

    def test_file_path(self):
        """Test the publicly accessable file_path() method"""
        self.assertEqual(
            self.met.file_path('proid.app#00123/asdf'),
            '{}/apps/proid.app-00123-asdf.rrd'.format(METRICS_DIR))


class LogAPITest(unittest.TestCase):
    """treadmill.api.local._LogAPI tests."""

    def setUp(self):
        tm_env = mock.Mock()

        tm_env_func = mock.Mock()
        tm_env_func.return_value = tm_env

        self.log = local._LogAPI(tm_env_func)

    # Don't complain about unused parameters
    # pylint: disable=W0613
    @mock.patch('__builtin__.open', return_value=mock.MagicMock())
    @mock.patch('treadmill.api.local._fragment', return_value='invoked')
    def test_get(self, mopen, _):
        """Test the _LogAPI.get() method."""
        self.log._get_logfile = mock.Mock()
        with self.assertRaises(InvalidInputError):
            self.log.get('no/such/log/exists', start=-1)

        self.assertEqual(
            self.log.get('no/such/log/exists',
                         start=0, limit=3),
            'invoked')


class HelperFuncTests(unittest.TestCase):
    """treadmill.api.local top level function tests."""

    @mock.patch('thread.get_ident', mock.Mock(return_value='123'))
    def test_temp_file_name(self):
        """Dummy test of _temp_file_name()."""
        self.assertEqual(local._temp_file_name(), '/tmp/local-123.temp')

    def test_get_file(self):
        """Test the _get_file() func."""
        self.assertEqual(local._get_file(__file__), __file__)

        with self.assertRaises(FileNotFoundError):
            local._get_file('no_such_file', arch_extract=False)

        with self.assertRaises(FileNotFoundError):
            local._get_file(fname='no_such_file',
                            arch_fname='no_such_archive',
                            arch_extract=True)

    def test_fragment_file(self):
        """Test the _fragment() func."""
        self.assertEqual(list(local._fragment(iter(xrange(10)))), range(10))

        self.assertEqual(
            list(local._fragment(iter(xrange(10)), limit=2)),
            range(2))

        self.assertEqual(
            list(local._fragment(iter(xrange(10)), start=0, limit=3)),
            range(3))

        self.assertEqual(
            list(local._fragment(iter(xrange(10)), start=1, limit=4)),
            range(1, 5))

        self.assertEqual(
            list(local._fragment(iter(xrange(10)), start=5)),
            range(5, 10))

        self.assertEqual(
            list(local._fragment(iter(xrange(10)), start=8, limit=8)),
            [8, 9])

        self.assertEqual(
            list(local._fragment(iter(xrange(10)), start=8, limit=40)),
            [8, 9])

        with self.assertRaises(InvalidInputError):
            list(local._fragment(iter(xrange(10)), start=99))

        with self.assertRaises(InvalidInputError):
            list(local._fragment(iter(xrange(10)), 99, limit=5))

    def test_fragment_in_reverse(self):
        """Test the _fragment_in_reverse() func."""
        self.assertEqual(
            list(local._fragment_in_reverse(iter(xrange(10)))),
            list(reversed(xrange(10))))

        self.assertEqual(
            list(local._fragment_in_reverse(iter(xrange(10)), limit=2)),
            [9, 8])

        self.assertEqual(
            list(local._fragment_in_reverse(iter(xrange(10)), 0, limit=3)),
            [9, 8, 7])

        self.assertEqual(
            list(local._fragment_in_reverse(iter(xrange(10)), 1, 4)),
            range(8, 4, -1))

        self.assertEqual(
            list(local._fragment_in_reverse(iter(xrange(10)), start=5)),
            [4, 3, 2, 1, 0])

        self.assertEqual(
            list(local._fragment_in_reverse(iter(xrange(10)), 8, limit=8)),
            [1, 0])

        self.assertEqual(
            list(local._fragment_in_reverse(iter(xrange(10)), 8, limit=40)),
            [1, 0])

        self.assertEqual(
            list(local._fragment_in_reverse(iter(xrange(10)), 8, 1)),
            [1])

        with self.assertRaises(InvalidInputError):
            list(local._fragment_in_reverse(iter(xrange(10)), start=99))

        with self.assertRaises(InvalidInputError):
            list(local._fragment_in_reverse(iter(xrange(10)), 99, limit=9))


class APITest(unittest.TestCase):
    """Basic API tests."""

    def test_archive(self):
        """Test the _get_file() func."""
        api = local.API()
        os.environ['TREADMILL_APPROOT'] = os.getcwd()

        with self.assertRaises(FileNotFoundError):
            api.archive.get('no/such/archive')


if __name__ == '__main__':
    unittest.main()
