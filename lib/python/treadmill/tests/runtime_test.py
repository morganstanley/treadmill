"""Unit test for treadmill.runtime.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import io
import os
import shutil
import socket
import tarfile
import tempfile
import time
import unittest

import mock

import treadmill
import treadmill.rulefile
import treadmill.runtime

from treadmill import exc
from treadmill import fs


class RuntimeTest(unittest.TestCase):
    """Tests for treadmill.runtime."""

    def setUp(self):
        # Access protected module _base_service
        # pylint: disable=W0212
        self.root = tempfile.mkdtemp()
        self.tm_env = mock.Mock(
            root=self.root,
            # nfs_dir=os.path.join(self.root, 'mnt', 'nfs'),
            apps_dir=os.path.join(self.root, 'apps'),
            archives_dir=os.path.join(self.root, 'archives'),
            metrics_dir=os.path.join(self.root, 'metrics'),
            rules=mock.Mock(
                spec_set=treadmill.rulefile.RuleMgr,
            )
        )

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('socket.socket.bind', mock.Mock())
    @mock.patch('socket.socket.listen', mock.Mock())
    def test__allocate_sockets(self):
        """Test allocating sockets.
        """
        # access protected module _allocate_sockets
        # pylint: disable=w0212

        socket.socket.bind.side_effect = [
            socket.error(errno.EADDRINUSE, 'In use'),
            mock.DEFAULT,
            mock.DEFAULT,
            mock.DEFAULT
        ]

        sockets = treadmill.runtime._allocate_sockets(
            'prod', '0.0.0.0', socket.SOCK_STREAM, 3
        )

        self.assertEqual(3, len(sockets))

    @mock.patch('socket.socket.bind', mock.Mock())
    def test__allocate_sockets_fail(self):
        """Test allocating sockets when all are taken.
        """
        # access protected module _allocate_sockets
        # pylint: disable=w0212

        socket.socket.bind.side_effect = socket.error(errno.EADDRINUSE,
                                                      'In use')

        with self.assertRaises(exc.ContainerSetupError):
            treadmill.runtime._allocate_sockets(
                'prod', '0.0.0.0', socket.SOCK_STREAM, 3
            )

    @mock.patch('socket.socket', mock.Mock(autospec=True))
    @mock.patch('treadmill.runtime._allocate_sockets', mock.Mock())
    def test_allocate_network_ports(self):
        """Test network port allocation.
        """
        # access protected module _allocate_network_ports
        # pylint: disable=w0212
        treadmill.runtime._allocate_sockets.side_effect = \
            lambda _x, _y, _z, count: [socket.socket()] * count
        mock_socket = socket.socket.return_value
        mock_socket.getsockname.side_effect = [
            ('unused', 50001),
            ('unused', 60001),
            ('unused', 10000),
            ('unused', 10001),
            ('unused', 10002),
            ('unused', 12345),
            ('unused', 54321),
        ]
        manifest = {
            'type': 'native',
            'environment': 'dev',
            'endpoints': [
                {
                    'name': 'http',
                    'port': 8000,
                    'proto': 'tcp',
                }, {
                    'name': 'ssh',
                    'port': 0,
                    'proto': 'tcp',
                }, {
                    'name': 'dns',
                    'port': 5353,
                    'proto': 'udp',
                }, {
                    'name': 'port0',
                    'port': 0,
                    'proto': 'udp',
                }
            ],
            'ephemeral_ports': {'tcp': 3, 'udp': 0},
        }

        treadmill.runtime.allocate_network_ports(
            '1.2.3.4',
            manifest
        )

        # in the updated manifest, make sure that real_port is specificed from
        # the ephemeral range as returnd by getsockname.
        self.assertEqual(
            8000,
            manifest['endpoints'][0]['port']
        )
        self.assertEqual(
            50001,
            manifest['endpoints'][0]['real_port']
        )
        self.assertEqual(
            60001,
            manifest['endpoints'][1]['port']
        )
        self.assertEqual(
            60001,
            manifest['endpoints'][1]['real_port']
        )
        self.assertEqual(
            5353,
            manifest['endpoints'][2]['port']
        )
        self.assertEqual(
            12345,
            manifest['endpoints'][2]['real_port']
        )
        self.assertEqual(
            54321,
            manifest['endpoints'][3]['port']
        )
        self.assertEqual(
            54321,
            manifest['endpoints'][3]['real_port']
        )
        self.assertEqual(
            [10000, 10001, 10002],
            manifest['ephemeral_ports']['tcp']
        )

    def test__archive_logs(self):
        """Tests archiving local logs."""
        # Access protected module _archive_logs
        #
        # pylint: disable=W0212,too-many-statements
        data_dir = os.path.join(self.root, 'xxx.yyy-1234-qwerty', 'data')
        fs.mkdir_safe(data_dir)
        archives_dir = os.path.join(self.root, 'archives')
        fs.mkdir_safe(archives_dir)
        sys_archive = os.path.join(archives_dir,
                                   'xxx.yyy-1234-qwerty.sys.tar.gz')
        app_archive = os.path.join(archives_dir,
                                   'xxx.yyy-1234-qwerty.app.tar.gz')
        treadmill.runtime.archive_logs(self.tm_env, 'xxx.yyy-1234-qwerty',
                                       data_dir)

        self.assertTrue(os.path.exists(sys_archive))
        self.assertTrue(os.path.exists(app_archive))
        os.unlink(sys_archive)
        os.unlink(app_archive)

        def _touch_file(path):
            """Touch file, appending path to container_dir."""
            fpath = os.path.join(data_dir, path)
            fs.mkdir_safe(os.path.dirname(fpath))
            io.open(fpath, 'w').close()

        _touch_file('sys/foo/data/log/current')
        _touch_file('sys/bla/data/log/current')
        _touch_file('sys/bla/data/log/xxx')
        _touch_file('services/xxx/data/log/current')
        _touch_file('services/xxx/data/log/whatever')
        _touch_file('services/xxx/data/log/@1.s')
        _touch_file('services/xxx/data/log/@2.u')
        _touch_file('services/yyy/data/log/current')
        _touch_file('services/yyy/data/log/@3.s')
        _touch_file('services/yyy/data/log/@4.s')
        _touch_file('services/zzz/data/log/current')
        fs.mkdir_safe(os.path.join(data_dir, 'services/empty/data/log'))
        _touch_file('a.json')
        _touch_file('a.rrd')
        _touch_file('log/current')
        _touch_file('whatever')

        treadmill.runtime.archive_logs(self.tm_env, 'xxx.yyy-1234-qwerty',
                                       data_dir)

        tar = tarfile.open(sys_archive)
        files = sorted([member.name for member in tar.getmembers()])
        self.assertEqual(
            files,
            ['a.json', 'a.rrd', 'log/current',
             'sys/bla/data/log/current', 'sys/foo/data/log/current']
        )
        tar.close()

        with tarfile.open(app_archive) as tar:
            files = sorted([member.name for member in tar.getmembers()])
            self.assertEqual(
                files,
                sorted([
                    'services/xxx/data/log/@2.u',
                    'services/xxx/data/log/current',
                    'services/yyy/data/log/current',
                    'services/yyy/data/log/@4.s',
                    'services/zzz/data/log/current'
                ])
            )

        os.unlink(sys_archive)
        os.unlink(app_archive)
        shutil.rmtree(data_dir)

        # empty log dir, no rotated file
        _touch_file('services/xxx/data/log/current')
        fs.mkdir_safe(os.path.join(data_dir, 'services/empty/data/log'))

        treadmill.runtime.archive_logs(
            self.tm_env, 'xxx.yyy-1234-qwerty', data_dir
        )
        with tarfile.open(app_archive) as tar:
            self.assertEqual([member.name for member in tar.getmembers()],
                             ['services/xxx/data/log/current'])

        os.unlink(sys_archive)
        os.unlink(app_archive)
        shutil.rmtree(data_dir)

        # empty log dir, no "current" file
        _touch_file('services/xxx/data/log/@1.s')
        fs.mkdir_safe(os.path.join(data_dir, 'services/empty/data/log'))

        treadmill.runtime.archive_logs(
            self.tm_env, 'xxx.yyy-1234-qwerty', data_dir
        )
        with tarfile.open(app_archive) as tar:
            self.assertEqual([member.name for member in tar.getmembers()],
                             ['services/xxx/data/log/@1.s'])

    def test__archive_cleanup(self):
        """Tests cleanup of local logs."""
        # Access protected module _ARCHIVE_LIMIT, _cleanup_archive_dir
        #
        # pylint: disable=W0212
        fs.mkdir_safe(self.tm_env.archives_dir)

        # Cleanup does not care about file extensions, it will cleanup
        # oldest file if threshold is exceeded.
        treadmill.runtime._ARCHIVE_LIMIT = 20
        file1 = os.path.join(self.tm_env.archives_dir, '1')
        with io.open(file1, 'w') as f:
            f.write('x' * 10)

        treadmill.runtime._cleanup_archive_dir(self.tm_env)
        self.assertTrue(os.path.exists(file1))

        os.utime(file1, (time.time() - 1, time.time() - 1))
        file2 = os.path.join(self.tm_env.archives_dir, '2')
        with io.open(file2, 'w') as f:
            f.write('x' * 10)

        treadmill.runtime._cleanup_archive_dir(self.tm_env)
        self.assertTrue(os.path.exists(file1))

        with io.open(os.path.join(self.tm_env.archives_dir, '2'), 'w') as f:
            f.write('x' * 15)
        treadmill.runtime._cleanup_archive_dir(self.tm_env)
        self.assertFalse(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))

    def test_load_app_safe(self):
        """Test loading corrupted or invalid app manifest."""
        data_dir = os.path.join(self.root, 'xxx.yyy-1234-qwerty', 'data')
        fs.mkdir_safe(data_dir)
        io.open(os.path.join(data_dir, 'state.json'), 'w').close()

        app = treadmill.runtime.load_app_safe('xxx.yyy-1234-qwerty', data_dir)

        self.assertEqual(app.name, 'xxx.yyy#1234')
        self.assertEqual(app.app, 'xxx.yyy')
        self.assertEqual(app.task, '1234')
        self.assertEqual(app.uniqueid, 'qwerty')


if __name__ == '__main__':
    unittest.main()
