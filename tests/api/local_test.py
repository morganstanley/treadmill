"""Local API tests."""

import os
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

from treadmill.api import local
from treadmill.exc import FileNotFoundError

METRICS_DIR = '.../metrics'
ARCHIVES_DIR = '.../archives'

# do not complain about accessing protected member
# pylint: disable=W0212


class MetricsAPITest(unittest.TestCase):
    """treadmill.api.local._MetricsAPI tests."""

    def setUp(self):
        app_env = mock.Mock()
        app_env.metrics_dir = METRICS_DIR
        app_env.archives_dir = ARCHIVES_DIR

        app_env_func = mock.Mock()
        app_env_func.return_value = app_env

        self.met = local._MetricsAPI(app_env_func)

    def test_metrics_fpath(self):
        """Test the path for application and service rrd metrics"""
        self.assertEqual(
            self.met._metrics_fpath(app='proid.app#00123',
                                    uniq='asdf'),
            '{}/apps/proid.app-00123-asdf.rrd'.format(METRICS_DIR))
        self.assertEqual(
            self.met._metrics_fpath(service='webauthd'),
            '{}/core/webauthd.rrd'.format(METRICS_DIR))

    def test_unpack_id(self):
        """Test the unpack_id() method."""
        self.assertEqual(
            self.met._unpack_id('webauthd'), {'service': 'webauthd'})
        self.assertEqual(
            self.met._unpack_id('proid.app#123/asdf'), {'app': 'proid.app#123',
                                                        'uniq': 'asdf'})

    def test_file_path(self):
        """Test the publicly accessable file_path() method"""
        self.assertEqual(
            self.met.file_path('proid.app#00123/asdf'),
            '{}/apps/proid.app-00123-asdf.rrd'.format(METRICS_DIR))


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
            local._get_file(fname='no_such_file', arch_fname='no_such_archive',
                            arch_extract=True)


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
