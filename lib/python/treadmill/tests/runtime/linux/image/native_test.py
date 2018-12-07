"""Tests for treadmill.runtime.linux.image.native.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
from collections import namedtuple
import io
import os
import shutil
import stat  # pylint: disable=wrong-import-order
import tempfile
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows   # pylint: disable=W0611

import treadmill
import treadmill.services
import treadmill.subproc
import treadmill.rulefile

from treadmill import supervisor
from treadmill import utils

from treadmill.runtime.linux.image import native


class NativeImageTest(unittest.TestCase):
    """Tests for treadmill.runtime.linux.image.native."""

    def setUp(self):
        # Access protected module _base_service
        # pylint: disable=W0212
        self.container_dir = tempfile.mkdtemp()
        self.root = tempfile.mkdtemp(dir=self.container_dir)
        self.services_tombstone_dir = os.path.join(self.root, 'tombstone')
        self.tm_env = mock.Mock(
            root=self.root,
            services_tombstone_dir=self.services_tombstone_dir,
            ctl_dir=os.path.join(self.root, 'ctl'),
            svc_cgroup=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
            svc_localdisk=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
            svc_network=mock.Mock(
                spec_set=treadmill.services._base_service.ResourceService,
            ),
            rules=mock.Mock(
                spec_set=treadmill.rulefile.RuleMgr,
            ),
        )
        self.app = utils.to_obj(
            {
                'type': 'native',
                'proid': 'myproid',
                'name': 'myproid.test#0',
                'uniqueid': 'ID1234',
                'environment': 'dev',
                'disk': '100G',
                'endpoints': [
                    {
                        'name': 'ssh',
                        'port': 47299,
                        'proto': 'tcp',
                        'real_port': 47299,
                        'type': 'infra'
                    }
                ],
                'shared_network': False,
                'ephemeral_ports': {
                    'tcp': 1,
                    'udp': 0
                },
                'docker': False
            }
        )

    def tearDown(self):
        if self.container_dir and os.path.isdir(self.container_dir):
            shutil.rmtree(self.container_dir)

    @mock.patch('os.chown', mock.Mock(spec_set=True))
    @mock.patch('os.mknod', mock.Mock(spec_set=True))
    @mock.patch('os.makedev', mock.Mock(spec_set=True))
    @mock.patch('treadmill.fs.symlink_safe', mock.Mock(spec_set=True))
    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock(spec_set=True))
    @mock.patch('treadmill.fs.linux.mount_devpts', mock.Mock(spec_set=True))
    @mock.patch('treadmill.fs.linux.mount_mqueue', mock.Mock(spec_set=True))
    @mock.patch('treadmill.fs.linux.mount_sysfs', mock.Mock(spec_set=True))
    @mock.patch('treadmill.fs.linux.mount_tmpfs', mock.Mock(spec_set=True))
    def test_make_fsroot(self):
        """Validates directory layout in chrooted environment."""
        native.make_fsroot(self.root, self.app)

        def isdir(path):
            """Checks directory presence in chrooted environment."""
            return os.path.isdir(os.path.join(self.root, path))

        def issticky(path):
            """Checks directory mode in chrooted environment."""
            statinfo = os.stat(os.path.join(self.root, path))
            return statinfo.st_mode & stat.S_ISVTX

        self.assertTrue(isdir('dev'))
        self.assertTrue(isdir('dev/shm'))
        self.assertTrue(isdir('dev/pts'))
        self.assertTrue(isdir('dev/mqueue'))
        self.assertTrue(isdir('home'))
        self.assertTrue(isdir('opt'))
        self.assertTrue(isdir('run'))
        self.assertTrue(isdir('tmp'))
        self.assertTrue(isdir('var/spool'))
        self.assertTrue(isdir('var/tmp'))
        self.assertTrue(isdir('var/empty'))

        self.assertTrue(issticky('opt'))
        self.assertTrue(issticky('run'))
        self.assertTrue(issticky('tmp'))
        self.assertTrue(issticky('var/tmp'))

        self.assertEqual(
            os.mknod.call_args_list,
            [
                mock.call(self.root + '/dev/null', 0o20666, mock.ANY),
                mock.call(self.root + '/dev/zero', 0o20666, mock.ANY),
                mock.call(self.root + '/dev/full', 0o20666, mock.ANY),
                mock.call(self.root + '/dev/tty', 0o20666, mock.ANY),
                mock.call(self.root + '/dev/random', 0o20444, mock.ANY),
                mock.call(self.root + '/dev/urandom', 0o20444, mock.ANY),
            ]
        )
        self.assertEqual(
            os.makedev.call_args_list,
            [
                mock.call(1, 3),
                mock.call(1, 5),
                mock.call(1, 7),
                mock.call(5, 0),
                mock.call(1, 8),
                mock.call(1, 9),
            ]
        )
        os.chown.assert_called_once_with(
            self.root + '/dev/tty',
            os.stat('/dev/tty').st_uid,
            os.stat('/dev/tty').st_gid
        )

        self.assertEqual(
            treadmill.fs.symlink_safe.call_args_list,
            [
                mock.call(self.root + '/dev/fd', '/proc/self/fd'),
                mock.call(self.root + '/dev/stdin', '/proc/self/fd/0'),
                mock.call(self.root + '/dev/stdout', '/proc/self/fd/1'),
                mock.call(self.root + '/dev/stderr', '/proc/self/fd/2'),
                mock.call(self.root + '/dev/core', '/proc/kcore'),
                mock.call(self.root + '/dev/ptmx', 'pts/ptmx'),
                mock.call(self.root + '/var/run', '/run')
            ]
        )

        treadmill.fs.linux.mount_sysfs.assert_called_once_with(self.root)
        self.assertEqual(
            treadmill.fs.linux.mount_tmpfs.call_args_list,
            [
                mock.call(
                    self.root, '/dev',
                    nodev=False, noexec=False, nosuid=True, relatime=False,
                    mode='0755'
                ),
                mock.call(
                    self.root, '/dev/shm',
                    nodev=True, noexec=False, nosuid=True, relatime=False
                ),
                mock.call(self.root, '/run'),
            ],
        )
        treadmill.fs.linux.mount_devpts.assert_called_once_with(
            self.root, '/dev/pts',
            gid=os.stat('/dev/tty').st_gid, mode='0620', ptmxmode='0666'
        )
        treadmill.fs.linux.mount_mqueue.assert_called_once_with(
            self.root, '/dev/mqueue'
        )
        treadmill.fs.linux.mount_bind.assert_has_calls(
            [
                mock.call(self.root, '/dev/log',
                          read_only=False),
                mock.call(self.root, '/bin',
                          read_only=True, recursive=True),
                mock.call(self.root, '/sys/fs',
                          read_only=False, recursive=True),
            ],
            any_order=True
        )

    @mock.patch('pwd.getpwnam', mock.Mock(
        return_value=namedtuple(
            'pwnam',
            ['pw_uid', 'pw_dir', 'pw_shell']
        )(3, '/', '/bin/sh')))
    @mock.patch('os.listdir', mock.Mock(
        side_effect=lambda path: {
            '/some/dir/sys': ['command0', 'command3', 'command4', '.s6-svscan']
        }[path]
    ))
    @mock.patch('os.path.isdir', mock.Mock(
        side_effect=lambda path: {
            '/some/dir/sys/command0': True,
            '/some/dir/sys/command3': True,
            '/some/dir/sys/command4': True,
        }[path]
    ))
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.fs.rmtree_safe', mock.Mock())
    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock())
    @mock.patch('treadmill.supervisor.create_service', mock.Mock())
    @mock.patch('treadmill.supervisor.create_scan_dir', mock.Mock())
    @mock.patch('treadmill.templates.create_script', mock.Mock())
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={
        's6_svscan': '/path/to/s6-svscan',
        'chroot': '/bin/chroot',
        'pid1': '/path/to/pid1'}))
    @mock.patch('treadmill.subproc._check', mock.Mock(return_value=True))
    def test__create_supervision_tree(self):
        """Test creation of the supervision tree."""
        # Access protected module _create_supervision_tree
        # pylint: disable=W0212
        app = utils.to_obj(
            {
                'type': 'native',
                'proid': 'myproid',
                'name': 'myproid.test#0',
                'uniqueid': 'ID1234',
                'environment': 'prod',
                'services': [
                    {
                        'name': 'command1',
                        'proid': 'test',
                        'command': '/path/to/command',
                        'restart': {
                            'limit': 3,
                            'interval': 60,
                        },
                        'environ': {},
                        'config': None,
                        'downed': False,
                        'trace': True,
                    },
                    {
                        'name': 'command2',
                        'proid': 'test',
                        'command': '/path/to/other/command',
                        'restart': {
                            'limit': 3,
                            'interval': 60,
                        },
                        'environ': {},
                        'config': None,
                        'downed': False,
                        'trace': True,
                    }
                ],
                'system_services': [
                    {
                        'name': 'command3',
                        'proid': 'root',
                        'command': '/path/to/sbin/command',
                        'restart': {
                            'limit': 5,
                            'interval': 60,
                        },
                        'environ': {},
                        'config': None,
                        'downed': True,
                        'trace': False,
                    },
                    {
                        'name': 'command4',
                        'proid': 'root',
                        'command': '/path/to/other/sbin/command',
                        'restart': None,  # not monitored
                        'environ': {},
                        'config': None,
                        'downed': False,
                        'trace': False,
                    }
                ],
                'vring': {
                    'cells': ['a', 'b']
                },
            }
        )
        base_dir = '/some/dir'

        mock_service_dir = mock.create_autospec(supervisor.ScanDir)
        treadmill.supervisor.create_scan_dir.return_value =\
            mock_service_dir

        native.create_supervision_tree(
            self.tm_env,
            base_dir,
            os.path.join(base_dir, 'root'),
            app,
            '/test/cgroup/path'
        )

        treadmill.supervisor.create_scan_dir.assert_has_calls([
            mock.call(
                os.path.join(base_dir, 'sys'),
                finish_timeout=6000,
                wait_cgroups='/test/cgroup/path'
            ),
            mock.call().write(),
            mock.call(
                os.path.join(base_dir, 'services'),
                finish_timeout=5000,
            ),
            mock.call().write(),
        ])

        treadmill.supervisor.create_service.assert_has_calls([
            # system services
            mock.call(mock_service_dir,
                      name='command3',
                      app_run_script='/path/to/sbin/command',
                      userid='root',
                      environ_dir='/some/dir/env',
                      environ={},
                      environment='prod',
                      downed=True,
                      monitor_policy={
                          'limit': 5,
                          'interval': 60,
                          'tombstone': {
                              'uds': False,
                              'path': self.services_tombstone_dir,
                              'id': 'myproid.test-0-0000000ID1234,command3'
                          }
                      },
                      trace=None),
            mock.call(mock_service_dir,
                      name='command4',
                      app_run_script='/path/to/other/sbin/command',
                      userid='root',
                      environ_dir='/some/dir/env',
                      environ={},
                      environment='prod',
                      downed=False,
                      monitor_policy=None,
                      trace=None),
            # user services
            mock.call(mock_service_dir,
                      name='command1',
                      app_run_script='/path/to/command',
                      userid='test',
                      environ_dir='/env',
                      environ={},
                      environment='prod',
                      downed=False,
                      monitor_policy={
                          'limit': 3,
                          'interval': 60,
                          'tombstone': {
                              'uds': True,
                              'path': '/run/tm_ctl/tombstone',
                              'id': 'myproid.test-0-0000000ID1234,command1'
                          }
                      },
                      log_run_script='s6.app-logger.run',
                      trace={
                          'instanceid': 'myproid.test#0',
                          'uniqueid': 'ID1234',
                          'service': 'command1',
                          'path': '/run/tm_ctl/appevents'
                      }),
            mock.call(mock_service_dir,
                      name='command2',
                      app_run_script='/path/to/other/command',
                      userid='test',
                      environ_dir='/env',
                      environ={},
                      environment='prod',
                      downed=False,
                      monitor_policy={
                          'limit': 3,
                          'interval': 60,
                          'tombstone': {
                              'uds': True,
                              'path': '/run/tm_ctl/tombstone',
                              'id': 'myproid.test-0-0000000ID1234,command2'
                          }
                      },
                      log_run_script='s6.app-logger.run',
                      trace={
                          'instanceid': 'myproid.test#0',
                          'uniqueid': 'ID1234',
                          'service': 'command2',
                          'path': '/run/tm_ctl/appevents'
                      })
        ])

        self.assertEqual(2, mock_service_dir.write.call_count)

        treadmill.fs.linux.mount_bind.assert_has_calls([
            mock.call('/some/dir/root', '/services',
                      source='/some/dir/services',
                      read_only=False, recursive=False),
            mock.call('/some/dir/root', '/run/tm_ctl',
                      source=os.path.join(self.root, 'ctl'),
                      read_only=False, recursive=False),
        ])

        treadmill.fs.rmtree_safe.assert_called_once_with(
            '/some/dir/sys/command0'
        )

    @mock.patch('treadmill.subproc.resolve', mock.Mock())
    def test__prepare_ldpreload(self):
        """Test preparing ldpreload."""
        # access protected module _prepare_ldpreload
        # pylint: disable=w0212
        treadmill.subproc.resolve.side_effect = [
            '/foo/1.so'
        ]

        native._prepare_ldpreload(self.container_dir, self.app)

        with io.open(os.path.join(self.container_dir,
                                  'overlay', 'etc', 'ld.so.preload')) as f:
            newfile = f.readlines()
        self.assertEqual('/foo/1.so\n', newfile[-1])

    @mock.patch('pwd.getpwnam', mock.Mock(
        return_value=collections.namedtuple('pwnam', 'pw_uid pw_gid')(42, 42)
    ))
    @mock.patch('shutil.copyfile', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('os.chown', mock.Mock())
    def test__prepare_hosts(self):
        """Test preparing hosts."""
        # access protected module _prepare_hosts
        # pylint: disable=w0212
        native._prepare_hosts(self.container_dir, self.app)

        etc_dir = os.path.join(self.container_dir, 'overlay', 'etc')
        run_dir = os.path.join(self.container_dir, 'overlay', 'run')

        shutil.copyfile.assert_has_calls(
            [
                mock.call('/etc/hosts', os.path.join(etc_dir, 'hosts')),
            ]
        )

        treadmill.fs.mkdir_safe.assert_called_with(
            os.path.join(run_dir, 'host-aliases')
        )

        os.chown.assert_called_with(
            os.path.join(run_dir, 'host-aliases'),
            42, 42
        )

    @mock.patch('os.path.exists', mock.Mock(return_value=False))
    @mock.patch('shutil.copyfile', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    def test__prepare_pam_sshd(self):
        """Test preparing pam sshd non-shared."""
        # access protected module _prepare_pam_sshd
        # pylint: disable=w0212
        native._prepare_pam_sshd(self.tm_env, self.container_dir, self.app)

        etc_dir = os.path.join(self.container_dir, 'overlay', 'etc')

        os.path.exists.assert_called_once_with(
            os.path.join(self.tm_env.root, 'etc', 'pam.d', 'sshd')
        )
        shutil.copyfile.assert_has_calls([
            mock.call('/etc/pam.d/sshd',
                      os.path.join(etc_dir, 'pam.d', 'sshd'))
        ])

    @mock.patch('os.path.exists', mock.Mock(return_value=True))
    @mock.patch('shutil.copyfile', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    def test__prepare_resolv_conf(self):
        """Test preparing resolv conf."""
        # access protected module _prepare_resolv_conf
        # pylint: disable=w0212
        native._prepare_resolv_conf(self.tm_env, self.container_dir)

        etc_dir = os.path.join(self.container_dir, 'overlay', 'etc')

        os.path.exists.assert_called_once_with(
            os.path.join(self.tm_env.root, 'etc', 'resolv.conf')
        )
        shutil.copyfile.assert_has_calls([
            mock.call(os.path.join(self.tm_env.root, 'etc', 'resolv.conf'),
                      os.path.join(etc_dir, 'resolv.conf'))
        ])

    @mock.patch('os.walk', mock.MagicMock(spec_set=True))
    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock(spec_set=True))
    def test__bind_overlay(self):
        """Test binding overlay."""
        # access protected module _bind_overlay
        # pylint: disable=w0212
        overlay_dir = os.path.join(self.container_dir, 'overlay')
        # Mock walking the etc overlay directory.
        os.walk.return_value = [
            (overlay_dir + '/etc', ['foo'], ['hosts', 'resolv.conf', 'baz']),
            (overlay_dir + '/etc/foo', [], ['bar']),
        ]

        native._bind_overlay(self.container_dir, self.root)

        treadmill.fs.linux.mount_bind.assert_has_calls(
            [
                mock.call(self.root, '/etc/hosts',
                          source=os.path.join(overlay_dir, 'etc', 'hosts'),
                          read_only=True, recursive=False),
                mock.call(self.root, '/etc/resolv.conf',
                          source=os.path.join(overlay_dir, 'etc/resolv.conf'),
                          read_only=True, recursive=False),
                mock.call(self.root, '/etc/baz',
                          source=os.path.join(overlay_dir, 'etc/baz'),
                          read_only=True, recursive=False),
                mock.call(self.root, '/etc/foo/bar',
                          source=os.path.join(overlay_dir, 'etc/foo/bar'),
                          read_only=True, recursive=False),
                mock.call(self.root, '/run/host-aliases',
                          source=os.path.join(
                              overlay_dir, 'run', 'host-aliases'
                          ),
                          read_only=False, recursive=False),
                mock.call('/', '/etc/resolv.conf',
                          source=os.path.join(overlay_dir, 'etc/resolv.conf'),
                          read_only=True, recursive=False)
            ],
            any_order=True
        )


if __name__ == '__main__':
    unittest.main()
