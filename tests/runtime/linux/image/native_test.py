"""Tests for treadmill.runtime.linux.image.native.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import stat
import tempfile
import unittest

import collections
from collections import namedtuple

# Disable W0611: Unused import
import tests.treadmill_test_skip_windows   # pylint: disable=W0611

import mock

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
        self.tm_env = mock.Mock(
            root=self.root,
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
                }
            }
        )

    def tearDown(self):
        if self.container_dir and os.path.isdir(self.container_dir):
            shutil.rmtree(self.container_dir)

    @mock.patch('os.chown', mock.Mock(spec_set=True))
    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock(spec_set=True))
    @mock.patch('treadmill.fs.linux.mount_tmpfs', mock.Mock(spec_set=True))
    @mock.patch('treadmill.fs.linux.mount_proc', mock.Mock(spec_set=True))
    @mock.patch('treadmill.fs.linux.mount_sysfs', mock.Mock(spec_set=True))
    def test_make_fsroot(self):
        """Validates directory layout in chrooted environment."""
        native.make_fsroot(self.root)

        def isdir(path):
            """Checks directory presence in chrooted environment."""
            return os.path.isdir(os.path.join(self.root, path))

        def issticky(path):
            """Checks directory mode in chrooted environment."""
            statinfo = os.stat(os.path.join(self.root, path))
            return statinfo.st_mode & stat.S_ISVTX

        self.assertTrue(isdir('home'))
        self.assertTrue(isdir('opt'))
        self.assertTrue(isdir('run'))
        self.assertTrue(isdir('tmp'))
        self.assertTrue(isdir('var/spool'))
        self.assertTrue(isdir('var/tmp'))

        self.assertTrue(issticky('opt'))
        self.assertTrue(issticky('run'))
        self.assertTrue(issticky('tmp'))
        self.assertTrue(issticky('var/tmp'))

        treadmill.fs.linux.mount_tmpfs.assert_called_once_with(
            mock.ANY, '/run'
        )

        treadmill.fs.linux.mount_bind.assert_has_calls([
            mock.call(mock.ANY, '/bin', read_only=True, recursive=True)
        ])

    @mock.patch('treadmill.cgroups.makepath',
                mock.Mock(return_value='/test/cgroup/path'))
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock())
    def test__share_cgroup_info(self):
        """Test sharing of cgroup information with the container."""
        # Access protected module _share_cgroup_info
        # pylint: disable=W0212
        native.share_cgroup_info('/some/root_dir', '/test/cgroup/path')

        # Check that cgroup mountpoint exists inside the container.
        treadmill.fs.mkdir_safe.assert_has_calls([
            mock.call('/some/root_dir/cgroup/memory')
        ])
        treadmill.fs.linux.mount_bind.assert_has_calls([
            mock.call('/some/root_dir', '/cgroup/memory',
                      source='/test/cgroup/path',
                      read_only=False, recursive=True)
        ])

    @mock.patch('pwd.getpwnam', mock.Mock(
        return_value=namedtuple(
            'pwnam',
            ['pw_uid', 'pw_dir', 'pw_shell']
        )(3, '/', '/bin/sh')))
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock())
    @mock.patch('treadmill.supervisor.create_service', mock.Mock())
    @mock.patch('treadmill.supervisor.create_scan_dir', mock.Mock())
    @mock.patch('treadmill.utils.create_script', mock.Mock())
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
            base_dir,
            '/test_treadmill',
            app,
            '/test/cgroup/path'
        )

        treadmill.supervisor.create_scan_dir.assert_has_calls([
            mock.call(
                os.path.join(base_dir, 'sys'),
                finish_timeout=6000,
                monitor_service='monitor',
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
                      },
                      log_run_script='s6.app-logger.run',
                      trace={
                          'instanceid': 'myproid.test#0',
                          'uniqueid': 'ID1234',
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
                      },
                      log_run_script='s6.app-logger.run',
                      trace={
                          'instanceid': 'myproid.test#0',
                          'uniqueid': 'ID1234',
                      })
        ])

        self.assertEqual(2, mock_service_dir.write.call_count)

        treadmill.fs.linux.mount_bind.assert_called_with(
            '/test_treadmill', '/services',
            source='/some/dir/services',
            read_only=False, recursive=False
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

    @mock.patch('os.path.exists', mock.Mock(return_value=False))
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
            mock.call('/etc/resolv.conf',
                      os.path.join(etc_dir, 'resolv.conf'))
        ])

    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock())
    def test__bind_overlay(self):
        """Test binding overlay."""
        # access protected module _bind_overlay
        # pylint: disable=w0212
        native._bind_overlay(self.container_dir, self.root)

        overlay_dir = os.path.join(self.container_dir, 'overlay')

        treadmill.fs.linux.mount_bind.assert_has_calls(
            [
                mock.call(self.root, '/etc/hosts',
                          source=os.path.join(overlay_dir, 'etc', 'hosts'),
                          read_only=True, recursive=False),
                mock.call(self.root, '/run/host-aliases',
                          source=os.path.join(
                              overlay_dir, 'run', 'host-aliases'
                          ),
                          read_only=False, recursive=False),
                mock.call(self.root, '/etc/ld.so.preload',
                          source=os.path.join(
                              overlay_dir, 'etc/ld.so.preload'
                          ),
                          read_only=True, recursive=False),
                mock.call(self.root, '/etc/pam.d/sshd',
                          source=os.path.join(overlay_dir, 'etc/pam.d/sshd'),
                          read_only=True, recursive=False),
                mock.call(self.root, '/etc/resolv.conf',
                          source=os.path.join(overlay_dir, 'etc/resolv.conf'),
                          read_only=True, recursive=False),
                mock.call(self.root, '/etc/krb5.keytab',
                          source=os.path.join(overlay_dir, 'etc/krb5.keytab'),
                          read_only=True, recursive=False),
                mock.call('/', '/etc/resolv.conf',
                          source=os.path.join(overlay_dir, 'etc/resolv.conf'),
                          read_only=True, recursive=False)
            ],
            any_order=True
        )


if __name__ == '__main__':
    unittest.main()
