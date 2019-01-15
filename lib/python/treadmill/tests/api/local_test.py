"""Local API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import functools
import io
import json
import os
import shutil
import tarfile
import tempfile
import unittest

import mock
import six
from six.moves import _thread

from treadmill import appenv
from treadmill import fs
from treadmill.api import local
# pylint: disable=W0622
from treadmill.exc import (LocalFileNotFoundError, InvalidInputError)

APPS_DIR = os.path.join('...', 'apps')
ARCHIVES_DIR = os.path.join('...', 'archives')
METRICS_DIR = os.path.join('...', 'metrics')
RUNNING_DIR = os.path.join('...', 'running')

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

    def test_abs_met_path(self):
        """Test the path for application and service rrd metrics"""
        self.assertEqual(
            self.met._abs_met_path(app='proid.app#00123',
                                   uniq='asdf'),
            os.path.join(METRICS_DIR, 'apps', 'proid.app-00123-asdf.rrd')
        )
        self.assertEqual(
            self.met._abs_met_path(service='test'),
            os.path.join(METRICS_DIR, 'core', 'test.rrd')
        )

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
            os.path.join(METRICS_DIR, 'apps', 'proid.app-00123-asdf.rrd')
        )

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

    def test_get(self):
        """Test the _LogAPI.get() method."""
        with mock.patch('treadmill.api.local._get_file'):
            with mock.patch('io.open', mock.mock_open()):
                with self.assertRaises(InvalidInputError):
                    self.log.get('no/such/log/exists', start=-1)
                with mock.patch('treadmill.api.local._fragment',
                                mock.Mock(spec_set=True,
                                          return_value='invoked')):
                    self.assertEqual(
                        self.log.get('no/such/log/exists', start=0, limit=3),
                        'invoked'
                    )

        # make sure that things don't break if the log file contains some
        # binary data with ord num > 128 (eg. \xc5 below) ie. not ascii
        # decodeable

        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp:
            temp.write(b'\x00\x01\xc5\x0a')
            temp.seek(0)

        with mock.patch('treadmill.api.local._get_file',
                        return_value=temp.name):
            self.assertTrue(''.join(self.log.get('no/such/log/exists')))

    @mock.patch('treadmill.api.local._get_file')
    def test_get_logfile_new(self, _get_file_mock):
        """Test _LogAPI._get_logfile_new()."""
        # ARCHIVED
        self.log._get_logfile_new('proid.app#123', 'uniq', 'service', 'foo')
        _get_file_mock.assert_called_once_with(
            os.path.join('...', 'apps', 'proid.app-123-uniq', 'data',
                         'services', 'foo', 'data', 'log', 'current'),
            arch=os.path.join('...', 'archives',
                              'proid.app-123-uniq.service.tar.gz'),
            arch_extract=True,
            arch_extract_filter=mock.ANY)

        _get_file_mock.reset_mock()

        # RUNNING
        self.log._get_logfile_new('proid.app#123', 'running', 'service', 'foo')
        _get_file_mock.assert_called_once_with(
            os.path.join('...', 'running', 'proid.app#123', 'data',
                         'services', 'foo', 'data', 'log', 'current'),
            arch=os.path.join('...', 'archives',
                              'proid.app-123-running.service.tar.gz'),
            arch_extract=False,
            arch_extract_filter=mock.ANY)

    @mock.patch('treadmill.api.local._get_file')
    def test_get_logfile_old(self, _get_file_mock):
        """Test _LogAPI._get_logfile_old()."""
        # ARCHIVED
        self.log._get_logfile_old('app#123', 'uniq', 'service', 'foo')
        _get_file_mock.assert_called_once_with(
            os.path.join('...', 'apps', 'app-123-uniq', 'services', 'foo',
                         'log', 'current'),
            arch=os.path.join('...', 'archives',
                              'app-123-uniq.service.tar.gz'),
            arch_extract=True,
            arch_extract_filter=mock.ANY)

        _get_file_mock.reset_mock()

        # RUNNING
        self.log._get_logfile_old('proid.app#123', 'running', 'service', 'foo')
        _get_file_mock.assert_called_once_with(
            os.path.join('...', 'running', 'proid.app#123', 'services', 'foo',
                         'log', 'current'),
            arch=os.path.join('...', 'archives',
                              'proid.app-123-running.service.tar.gz'),
            arch_extract=False,
            arch_extract_filter=mock.ANY)


class HelperFuncTests(unittest.TestCase):
    """treadmill.api.local top level function tests."""

    def setUp(self):
        self.tm_env = mock.Mock()
        self.tm_env.apps_dir = APPS_DIR
        self.tm_env.archives_dir = ARCHIVES_DIR
        self.tm_env.running_dir = RUNNING_DIR

        self.tm_env_func = mock.Mock()
        self.tm_env_func.return_value = self.tm_env

    @mock.patch('_thread.get_ident', mock.Mock(return_value='123'))
    def test_temp_dir(self):
        """Dummy test of _temp_dir()."""
        self.assertEqual(local._temp_dir(),
                         os.path.join(tempfile.gettempdir(), 'local-123.temp'))
        shutil.copy(__file__,
                    os.path.join(tempfile.gettempdir(), 'local-123.temp'))
        self.assertEqual(len(os.listdir(
            os.path.join(tempfile.gettempdir(), 'local-123.temp'))), 1)
        # subsequent invocations should delete the temp dir content
        self.assertEqual(os.listdir(local._temp_dir()), [])

    def test_extract_archive(self):
        """Test the _extract_archive() func."""
        with self.assertRaises(LocalFileNotFoundError):
            local._extract_archive('no_such_file')

        temp_dir = os.path.join(tempfile.gettempdir(), 'tm-unittest')
        temp_subdir = os.path.join(temp_dir, 'foo')

        shutil.rmtree(temp_dir, True)
        os.mkdir(temp_dir)
        os.mkdir(temp_subdir)
        shutil.copy(__file__, os.path.join(temp_subdir, 'current'))
        shutil.copy(__file__, os.path.join(temp_subdir, '@4000zzzz.s'))

        with tarfile.open(os.path.join(temp_dir, 'f.tar'), mode='w') as tar:
            orig_cwd = os.getcwd()
            os.chdir(temp_dir)
            # this creates 3 entries because the subdir is separate entry...
            tar.add('foo')
            os.chdir(orig_cwd)

        self.assertEqual(
            len(local._extract_archive(os.path.join(temp_dir, 'f.tar'))),
            3)
        self.assertEqual(
            len(local._extract_archive(os.path.join(temp_dir, 'f.tar'),
                                       extract_filter=functools.partial(
                                           local._arch_log_filter,
                                           rel_log_dir='foo'))),
            2)
        shutil.rmtree(temp_dir)

    def test_concat_files(self):
        """Test the _concat_files() func."""
        ident = _thread.get_ident()
        file_lst = []
        for i in six.moves.range(3):
            file_lst.append(os.path.join(tempfile.gettempdir(),
                                         '{}.{}'.format(ident, i)))
            with io.open(file_lst[-1], 'wb') as logs:
                logs.write(bytearray('{}\n'.format(i), 'ascii'))

        result = local._concat_files(file_lst)
        self.assertTrue(isinstance(result, io.TextIOWrapper))
        self.assertEqual(result.read(), u'0\n1\n2\n')

        # check that _concat_files() catches IOError for non existing file
        file_lst.append('no_such_file')
        local._concat_files(file_lst)

        for f in file_lst[:-1]:
            os.remove(f)

        # make sure that things don't break if the log file contains some
        # binary data with ord num > 128 (eg. \xc5 below) ie. not ascii
        # decodeable
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp:
            temp.write(b'\x42\x00\x01\xc5\x45\x0a')
            temp.seek(0)

        self.assertTrue(''.join(local._concat_files([temp.name])))

    def test_rel_log_dir_path(self):
        """Test the rel_log_dir_path() func."""
        self.assertEqual(local._rel_log_dir_path('sys', 'foo'),
                         os.path.join('sys', 'foo', 'data', 'log'))
        self.assertEqual(local._rel_log_dir_path('app', 'foo'),
                         os.path.join('services', 'foo', 'data', 'log'))

    def test_abs_log_dir_path(self):
        """Test the abs_log_dir_path() func."""
        self.assertEqual(
            local._abs_log_dir_path(self.tm_env_func, 'proid.app-123',
                                    'running', '...'),
            os.path.join('...', 'running', 'proid.app-123', 'data', '...'))
        self.assertEqual(
            local._abs_log_dir_path(self.tm_env_func, 'proid.app-123',
                                    'xyz', '...'),
            os.path.join('...', 'apps', 'proid.app-123-xyz', 'data', '...'))

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
        self.assertEqual(
            local._archive_path(self.tm_env_func, 'app', 'app#123', 'uniq'),
            os.path.join(ARCHIVES_DIR, 'app-123-uniq.app.tar.gz')
        )


class APITest(unittest.TestCase):
    """Basic API tests.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.environ['TREADMILL_APPROOT'] = self.root
        self.tm_env = appenv.AppEnvironment(root=self.root)

        fs.mkdir_safe(self.tm_env.apps_dir)
        fs.mkdir_safe(self.tm_env.archives_dir)

        full_names = (
            ('proid.simplehttp', '0001025686', 'ymweWiRm86C7A'),
            ('proid.myapi.test', '0001027473', 'kJoV4j0DU6dtJ'),
        )
        for app, instance, uniq in full_names:
            link = '#'.join([app, instance])
            fs.mkfile_safe(os.path.join(self.tm_env.running_dir, link))

            target = '-'.join([app, instance, uniq])
            fs.mkdir_safe(os.path.join(self.tm_env.apps_dir, target, 'data'))

            fs.symlink_safe(
                os.path.join(self.tm_env.running_dir, link),
                os.path.join(self.tm_env.apps_dir, target),
            )

        files = (
            # incorrect file
            'proid.app-foo-bar#123.sys.tar.gz',
            'proid.app#123.sys.tar.gz',
            # correct file
            'proid.app-123-uniq.sys.tar.gz',
            'proid.test.sleep-901-uniq.sys.tar.gz',
        )
        for f in files:
            fs.mkfile_safe(os.path.join(self.tm_env.archives_dir, f))

        self.api = local.API()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_archive(self):
        """Test ArvhiveApi's get() method.
        """
        with self.assertRaises(LocalFileNotFoundError):
            self.api.archive.get('no/such/archive')

    def test_list_running(self):
        """Test _list_running().
        """
        res = self.api.list(state='running')
        self.assertEqual(len(res), 2)
        self.assertSetEqual(
            set(ins['_id'] for ins in res),
            set([
                'proid.simplehttp#0001025686/ymweWiRm86C7A',
                'proid.myapi.test#0001027473/kJoV4j0DU6dtJ',
            ])
        )

        res = self.api.list(
            state='running',
            app_name='proid.simplehttp#0001025686',
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(
            res[0]['_id'], 'proid.simplehttp#0001025686/ymweWiRm86C7A'
        )

    def test_list_finished(self):
        """Test _list_finished().
        """
        res = self.api.list(state='finished')
        self.assertEqual(len(res), 2)
        self.assertSetEqual(
            set(ins['_id'] for ins in res),
            set([
                'proid.app#123/uniq',
                'proid.test.sleep#901/uniq',
            ])
        )

        cases = [
            ('proid.app#123', 1),
            ('proid.test.sleep#901', 1),
            ('proid.unknown#1', 0),
        ]
        for app_name, expected in cases:
            res = self.api.list(state='finished', app_name=app_name)
            self.assertEqual(len(res), expected)

    def test_get(self):
        """Test _get(uniqid).
        """
        state = {'foo': 'bar'}

        path_to_state_file = os.path.join(
            self.tm_env.apps_dir,
            'proid.simplehttp-0001025686-ymweWiRm86C7A',
            'data',
            'state.json',
        )
        with io.open(path_to_state_file, 'w') as f:
            json.dump(state, f)

        # check that state.json can be read back successfully
        self.assertEqual(
            self.api.get('proid.simplehttp-0001025686/ymweWiRm86C7A'),
            state,
        )

        # add state.json to an archive
        path_to_archive = os.path.join(
            self.tm_env.archives_dir,
            'proid.app-123-uniq.sys.tar.gz'
        )
        with tarfile.open(path_to_archive, mode='w') as out:
            out.add(path_to_state_file, arcname='state.json')

        # check that state.json can be read back from an archive
        self.assertEqual(self.api.get('proid.app-123/uniq'), state)


if __name__ == '__main__':
    unittest.main()
