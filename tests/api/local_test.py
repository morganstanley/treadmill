"""Local API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import unittest

import mock

import six

from treadmill.api import local
# pylint: disable=W0622
from treadmill.exc import (LocalFileNotFoundError, InvalidInputError)

APPS_DIR = '.../apps'
ARCHIVES_DIR = '.../archives'
METRICS_DIR = '.../metrics'
RUNNING_DIR = '.../running'

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

        self.met = local.mk_metrics_api(tm_env_func)()

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

    @mock.patch('treadmill.rrdutils.get_json_metrics')
    def test_get(self, mock_):
        """Test the _MetricsAPI.get() method."""
        self.met._get_rrd_file = mock.Mock(return_value='rrd.file')
        self.met.get('id', 'foo', as_json=True)
        mock_.assert_called_with('rrd.file', 'foo')


class LogAPITest(unittest.TestCase):
    """treadmill.api.local._LogAPI tests."""

    def setUp(self):
        tm_env = mock.Mock()
        tm_env.apps_dir = APPS_DIR
        tm_env.archives_dir = ARCHIVES_DIR
        tm_env.running_dir = RUNNING_DIR

        tm_env_func = mock.Mock()
        tm_env_func.return_value = tm_env

        self.log = local.mk_logapi(tm_env_func)()

    # Don't complain about unused parameters
    # pylint: disable=W0613
    @mock.patch('io.open', mock.mock_open())
    @mock.patch('treadmill.api.local._fragment',
                mock.Mock(spec_set=True, return_value='invoked'))
    @mock.patch('treadmill.api.local._get_file',
                mock.Mock(spec_set=True))
    def test_get(self):
        """Test the _LogAPI.get() method."""
        with self.assertRaises(InvalidInputError):
            self.log.get('no/such/log/exists', start=-1)

        self.assertEqual(
            self.log.get('no/such/log/exists',
                         start=0, limit=3),
            'invoked')

    @mock.patch('treadmill.api.local._get_file')
    def test_get_logfile_new(self, _get_file_mock):
        """Test _LogAPI._get_logfile_new()."""
        # ARCHIVED
        self.log._get_logfile_new('proid.app#123', 'uniq', 'service', 'foo')
        _get_file_mock.assert_called_once_with(
            '.../apps/proid.app-123-uniq/data/services/foo/data/log/current',
            arch_fname='.../archives/proid.app-123-uniq.service.tar.gz',
            arch_extract=True,
            arch_extract_fname='services/foo/data/log/current')

        _get_file_mock.reset_mock()

        # RUNNING
        self.log._get_logfile_new('proid.app#123', 'running', 'service', 'foo')
        _get_file_mock.assert_called_once_with(
            '.../running/proid.app#123/data/services/foo/data/log/current',
            arch_fname='.../archives/proid.app-123-running.service.tar.gz',
            arch_extract=False,
            arch_extract_fname='services/foo/data/log/current')

    @mock.patch('treadmill.api.local._get_file')
    def test_get_logfile_old(self, _get_file_mock):
        """Test _LogAPI._get_logfile_old()."""
        # ARCHIVED
        self.log._get_logfile_old('app#123', 'uniq', 'service', 'foo')
        _get_file_mock.assert_called_once_with(
            '.../apps/app-123-uniq/services/foo/log/current',
            arch_fname='.../archives/app-123-uniq.service.tar.gz',
            arch_extract=True,
            arch_extract_fname='services/foo/log/current')

        _get_file_mock.reset_mock()

        # RUNNING
        self.log._get_logfile_old('proid.app#123', 'running', 'service', 'foo')
        _get_file_mock.assert_called_once_with(
            '.../running/proid.app#123/services/foo/log/current',
            arch_fname='.../archives/proid.app-123-running.service.tar.gz',
            arch_extract=False,
            arch_extract_fname='services/foo/log/current')


class HelperFuncTests(unittest.TestCase):
    """treadmill.api.local top level function tests."""

    @mock.patch('threading.get_ident', mock.Mock(return_value='123'))
    def test_temp_file_name(self):
        """Dummy test of _temp_file_name()."""
        self.assertEqual(local._temp_file_name(), '/tmp/local-123.temp')

    def test_get_file(self):
        """Test the _get_file() func."""
        self.assertEqual(local._get_file(__file__), __file__)

        with self.assertRaises(LocalFileNotFoundError):
            local._get_file('no_such_file', arch_extract=False)

        with self.assertRaises(LocalFileNotFoundError):
            local._get_file(fname='no_such_file',
                            arch_fname='no_such_archive',
                            arch_extract=True)

    def test_fragment_file(self):
        """Test the _fragment() func."""
        self.assertEqual(list(local._fragment(iter(six.moves.range(10)),
                                              limit=-1)),
                         list(six.moves.range(10)))

        self.assertEqual(
            list(local._fragment(iter(six.moves.range(10)), limit=2)),
            list(six.moves.range(2)))

        self.assertEqual(
            list(local._fragment(iter(six.moves.range(10)), start=0, limit=3)),
            list(six.moves.range(3)))

        self.assertEqual(
            list(local._fragment(iter(six.moves.range(10)), start=1, limit=4)),
            list(six.moves.range(1, 5)))

        self.assertEqual(
            list(local._fragment(iter(six.moves.range(10)), start=5,
                                 limit=-1)),
            list(six.moves.range(5, 10)))

        self.assertEqual(
            list(local._fragment(iter(six.moves.range(10)), start=8, limit=8)),
            [8, 9])

        self.assertEqual(
            list(local._fragment(iter(six.moves.range(10)), start=8,
                                 limit=40)),
            [8, 9])

        with self.assertRaises(InvalidInputError):
            list(local._fragment(iter(six.moves.range(10)), start=99,
                                 limit=-1))

        with self.assertRaises(InvalidInputError):
            list(local._fragment(iter(six.moves.range(10)), 99, limit=5))

    def test_fragment_in_reverse(self):
        """Test the _fragment_in_reverse() func."""
        self.assertEqual(
            list(local._fragment_in_reverse(iter(six.moves.range(10)),
                                            limit=-1)),
            list(reversed(six.moves.range(10))))

        self.assertEqual(
            list(local._fragment_in_reverse(iter(six.moves.range(10)),
                                            limit=2)),
            [9, 8])

        self.assertEqual(
            list(local._fragment_in_reverse(iter(six.moves.range(10)), 0,
                                            limit=3)),
            [9, 8, 7])

        self.assertEqual(
            list(local._fragment_in_reverse(iter(six.moves.range(10)), 1, 4)),
            list(six.moves.range(8, 4, -1)))

        self.assertEqual(
            list(local._fragment_in_reverse(iter(six.moves.range(10)),
                                            start=5, limit=-1)),
            [4, 3, 2, 1, 0])

        self.assertEqual(
            list(local._fragment_in_reverse(iter(six.moves.range(10)), 8,
                                            limit=8)),
            [1, 0])

        self.assertEqual(
            list(local._fragment_in_reverse(iter(six.moves.range(10)), 8,
                                            limit=40)),
            [1, 0])

        self.assertEqual(
            list(local._fragment_in_reverse(iter(six.moves.range(10)), 8, 1)),
            [1])

        with self.assertRaises(InvalidInputError):
            list(local._fragment_in_reverse(iter(six.moves.range(10)),
                                            start=99))

        with self.assertRaises(InvalidInputError):
            list(local._fragment_in_reverse(iter(six.moves.range(10)), 99,
                                            limit=9))

    def test_archive_path(self):
        """Test the _archive_paths() func."""
        tm_env = mock.Mock()
        tm_env.archives_dir = ARCHIVES_DIR

        self.assertEqual(
            local._archive_path(tm_env, 'app', 'app#123', 'uniq'),
            '{}/app-123-uniq.app.tar.gz'.format(ARCHIVES_DIR))


class APITest(unittest.TestCase):
    """Basic API tests."""

    def setUp(self):
        """Test the _get_file() func."""
        self.api = local.API()
        os.environ['TREADMILL_APPROOT'] = os.getcwd()

    def test_archive(self):
        """Test ArvhiveApi's get() method."""
        with self.assertRaises(LocalFileNotFoundError):
            self.api.archive.get('no/such/archive')

    # W0613: unused argument 'dont_care'
    # pylint: disable=W0613
    @mock.patch('glob.glob',
                return_value=['.../archives/proid.app-foo-bar#123.sys.tar.gz',
                              '.../archives/proid.app-123-uniq.sys.tar.gz',
                              '.../archives/proid.app#123.sys.tar.gz'])
    @mock.patch('os.stat')
    def test_list_finished(self, _, dont_care):
        """Test _list_finished()."""
        res = self.api.list('finished')
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['_id'], 'proid.app#123/uniq')


if __name__ == '__main__':
    unittest.main()
