"""Tests for treadmill.runtime.linux.image.native.
"""

import os
import pwd
import shutil
import stat
import tempfile
import unittest

import collections
from collections import namedtuple

import mock

import treadmill
import treadmill.services
import treadmill.subproc
import treadmill.rulefile

from treadmill import fs
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

    @mock.patch('pwd.getpwnam', mock.Mock(
        return_value=collections.namedtuple('pwnam', 'pw_uid pw_gid')(42, 42)
    ))
    @mock.patch('os.chown', mock.Mock())
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    @mock.patch('treadmill.fs.mount_tmpfs', mock.Mock())
    def test_make_fsroot(self):
        """Validates directory layout in chrooted environment."""
        native.make_fsroot(self.root, 'myproid')

        def isdir(path):
            """Checks directory presence in chrooted environment."""
            return os.path.isdir(os.path.join(self.root, path))

        def issticky(path):
            """Checks directory mode in chrooted environment."""
            statinfo = os.stat(os.path.join(self.root, path))
            return statinfo.st_mode & stat.S_ISVTX

        self.assertTrue(isdir('tmp'))
        self.assertTrue(isdir('opt'))
        # self.assertTrue(isdir('u'))
        # self.assertTrue(isdir('var/hostlinks'))
        # self.assertTrue(isdir('var/account'))
        # self.assertTrue(isdir('var/empty'))
        # self.assertTrue(isdir('var/lock'))
        # self.assertTrue(isdir('var/lock/subsys'))
        # self.assertTrue(isdir('var/run'))
        self.assertTrue(isdir('var/spool/keytabs'))
        self.assertTrue(isdir('var/spool/tickets'))
        self.assertTrue(isdir('var/spool/tokens'))
        self.assertTrue(isdir('var/tmp'))
        self.assertTrue(isdir('var/tmp/cores'))
        self.assertTrue(isdir('home'))

        self.assertTrue(issticky('tmp'))
        self.assertTrue(issticky('opt'))
        # self.assertTrue(issticky('u'))
        # self.assertTrue(issticky('var/hostlinks'))
        self.assertTrue(issticky('var/tmp'))
        self.assertTrue(issticky('var/tmp/cores'))
        self.assertTrue(issticky('var/spool/tickets'))

        treadmill.fs.mount_tmpfs.assert_has_calls([
            mock.call(mock.ANY, '/var/spool/tickets', mock.ANY),
            mock.call(mock.ANY, '/var/spool/keytabs', mock.ANY)
        ])

        treadmill.fs.mount_bind.assert_has_calls([
            mock.call(mock.ANY, '/bin')
        ])

    @mock.patch('treadmill.cgroups.makepath',
                mock.Mock(return_value='/test/cgroup/path'))
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    def test__share_cgroup_info(self):
        """Test sharing of cgroup information with the container."""
        # Access protected module _share_cgroup_info
        # pylint: disable=W0212
        app = utils.to_obj(
            {
                'name': 'myproid.test#0',
                'uniqueid': 'ID1234',
            }
        )

        native.share_cgroup_info(app, '/some/root_dir')

        # Check that cgroup mountpoint exists inside the container.
        treadmill.fs.mkdir_safe.assert_has_calls([
            mock.call('/some/root_dir/cgroup/memory')
        ])
        treadmill.fs.mount_bind.assert_has_calls([
            mock.call('/some/root_dir', '/cgroup/memory', '/test/cgroup/path')
        ])

    @mock.patch('pwd.getpwnam', mock.Mock(
        return_value=namedtuple(
            'pwnam',
            ['pw_uid', 'pw_dir', 'pw_shell']
        )(3, '/', '/bin/sh')))
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    @mock.patch('treadmill.supervisor.create_service', mock.Mock())
    @mock.patch('treadmill.utils.create_script', mock.Mock())
    @mock.patch('treadmill.utils.touch', mock.Mock())
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/test_treadmill'))
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
                        'command': '/path/to/command',
                        'restart': {
                            'limit': 3,
                            'interval': 60,
                        },
                    }, {
                        'name': 'command2',
                        'command': '/path/to/other/command',
                        'restart': {
                            'limit': 3,
                            'interval': 60,
                        },
                    }
                ],
                'system_services': [
                    {
                        'name': 'command3',
                        'command': '/path/to/sbin/command',
                        'restart': {
                            'limit': 5,
                            'interval': 60,
                        },
                    }, {
                        'name': 'command4',
                        'command': '/path/to/other/sbin/command',
                        'restart': {
                            'limit': 5,
                            'interval': 60,
                        },
                    }
                ],
                'vring': {
                    'cells': ['a', 'b']
                },
            }
        )
        base_dir = '/some/dir'

        native.create_supervision_tree(
            base_dir,
            app
        )

        treadmill.fs.mkdir_safe.assert_has_calls([
            mock.call('/some/dir/root/services'),
            mock.call('/some/dir/services'),
            mock.call('/some/dir/sys/.s6-svscan'),
            mock.call('/some/dir/services/.s6-svscan'),
            mock.call('/some/dir/services/command1/log'),
            mock.call('/some/dir/services/command2/log'),
            mock.call('/some/dir/services/command3/log'),
            mock.call('/some/dir/services/command4/log'),
            mock.call('/some/dir/sys/vring.a'),
            mock.call('/some/dir/sys/vring.a/log'),
            mock.call('/some/dir/sys/vring.b'),
            mock.call('/some/dir/sys/vring.b/log'),
            mock.call('/some/dir/sys/monitor'),
            mock.call('/some/dir/sys/monitor/log'),
            mock.call('/some/dir/sys/register'),
            mock.call('/some/dir/sys/register/log'),
            mock.call('/some/dir/sys/hostaliases'),
            mock.call('/some/dir/sys/hostaliases/log'),
            mock.call('/some/dir/sys/start_container'),
            mock.call('/some/dir/sys/start_container/log'),
        ])
        treadmill.fs.mount_bind.assert_called_with(
            '/some/dir/root', '/services', '/some/dir/services',
        )

        pwd.getpwnam.assert_has_calls(
            [
                mock.call('myproid'),
                mock.call('root')
            ],
            any_order=True
        )

        treadmill.supervisor.create_service.assert_has_calls([
            # user services
            mock.call('/some/dir/services',
                      'myproid',
                      mock.ANY, mock.ANY,
                      'command1',
                      '/path/to/command',
                      as_root=True,
                      down=True,
                      envdirs=['/environ/app', '/environ/sys'],
                      env='prod'),
            mock.call('/some/dir/services',
                      'myproid',
                      mock.ANY, mock.ANY,
                      'command2',
                      '/path/to/other/command',
                      as_root=True,
                      down=True,
                      envdirs=['/environ/app', '/environ/sys'],
                      env='prod'),
            # system services
            mock.call('/some/dir/services',
                      'root',
                      mock.ANY, mock.ANY,
                      'command3',
                      '/path/to/sbin/command',
                      as_root=True,
                      down=False,
                      envdirs=['/environ/sys'],
                      env='prod'),
            mock.call('/some/dir/services',
                      'root',
                      mock.ANY, mock.ANY,
                      'command4',
                      '/path/to/other/sbin/command',
                      as_root=True,
                      down=False,
                      envdirs=['/environ/sys'],
                      env='prod')
        ])

        treadmill.utils.create_script.assert_has_calls([
            mock.call('/some/dir/sys/.s6-svscan/finish',
                      'svscan.finish',
                      timeout=mock.ANY),
            mock.call('/some/dir/services/.s6-svscan/finish',
                      'svscan.finish',
                      timeout=mock.ANY),
            mock.call('/some/dir/services/command1/log/run', 'logger.run'),
            mock.call('/some/dir/services/command2/log/run', 'logger.run'),
            mock.call('/some/dir/services/command3/log/run', 'logger.run'),
            mock.call('/some/dir/services/command4/log/run', 'logger.run'),
            mock.call('/some/dir/sys/vring.a/run',
                      'supervisor.run_sys',
                      cmd=mock.ANY),
            mock.call('/some/dir/sys/vring.a/log/run',
                      'logger.run'),
            mock.call('/some/dir/sys/vring.b/run',
                      'supervisor.run_sys',
                      cmd=mock.ANY),
            mock.call('/some/dir/sys/vring.b/log/run',
                      'logger.run'),
            mock.call('/some/dir/sys/monitor/run',
                      'supervisor.run_sys',
                      cmd=mock.ANY),
            mock.call('/some/dir/sys/monitor/log/run',
                      'logger.run'),
            mock.call('/some/dir/sys/register/run',
                      'supervisor.run_sys',
                      cmd=mock.ANY),
            mock.call('/some/dir/sys/register/log/run',
                      'logger.run'),
            mock.call('/some/dir/sys/hostaliases/run',
                      'supervisor.run_sys',
                      cmd=mock.ANY),
            mock.call('/some/dir/sys/hostaliases/log/run',
                      'logger.run'),
            mock.call(
                '/some/dir/sys/start_container/run',
                'supervisor.run_sys',
                cmd=('/bin/chroot /some/dir/root /path/to/pid1 '
                     '-m -p -i /path/to/s6-svscan /services')
            ),
            mock.call('/some/dir/sys/start_container/log/run',
                      'logger.run'),
        ])
        treadmill.utils.touch.assert_has_calls([
            mock.call('/some/dir/sys/start_container/down'),
        ])

    @mock.patch('treadmill.subproc.resolve', mock.Mock())
    def test__prepare_ldpreload(self):
        """Test preparing ldpreload."""
        # access protected module _prepare_ldpreload
        # pylint: disable=w0212
        treadmill.subproc.resolve.side_effect = [
            '/foo/1.so'
        ]

        native._prepare_ldpreload(self.container_dir, self.app)

        newfile = open(os.path.join(self.container_dir, 'overlay', 'etc',
                                    'ld.so.preload')).readlines()
        self.assertEqual('/foo/1.so\n', newfile[-1])

    @mock.patch('shutil.copyfile', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    def test__prepare_hosts(self):
        """Test preparing hosts."""
        # access protected module _prepare_hosts
        # pylint: disable=w0212
        native._prepare_hosts(self.container_dir)

        etc_dir = os.path.join(self.container_dir, 'overlay', 'etc')

        shutil.copyfile.assert_has_calls([
            mock.call('/etc/hosts', os.path.join(etc_dir, 'hosts')),
            mock.call('/etc/hosts', os.path.join(etc_dir, 'hosts.original')),
        ])

        treadmill.fs.mkdir_safe.assert_called_with(
            os.path.join(etc_dir, 'host-aliases')
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

        shutil.copyfile.assert_has_calls([
            mock.call('/etc/resolv.conf',
                      os.path.join(etc_dir, 'resolv.conf'))
        ])

    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    def test__bind_etc_overlay(self):
        """Test binding etc overlay."""
        # access protected module _bind_etc_overlay
        # pylint: disable=w0212
        native._bind_etc_overlay(self.container_dir, self.root)

        overlay_dir = os.path.join(self.container_dir, 'overlay')

        treadmill.fs.mount_bind.assert_has_calls([
            mock.call(self.root, '/etc/hosts',
                      target=os.path.join(overlay_dir, 'etc/hosts'),
                      bind_opt='--bind'),
            mock.call(self.root, '/etc/ld.so.preload',
                      target=os.path.join(overlay_dir, 'etc/ld.so.preload'),
                      bind_opt='--bind'),
            mock.call(self.root, '/etc/pam.d/sshd',
                      target=os.path.join(overlay_dir, 'etc/pam.d/sshd'),
                      bind_opt='--bind'),
            mock.call(self.root, '/etc/resolv.conf',
                      target=os.path.join(overlay_dir, 'etc/resolv.conf'),
                      bind_opt='--bind'),
            mock.call('/', '/etc/resolv.conf',
                      target=os.path.join(overlay_dir, 'etc/resolv.conf'),
                      bind_opt='--bind')
        ])

    @mock.patch('pwd.getpwnam', mock.Mock(
        return_value=namedtuple(
            'pwnam',
            ['pw_uid', 'pw_dir', 'pw_shell']
        )(3, '/', '/bin/sh')))
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    @mock.patch('treadmill.utils.rootdir', mock.Mock(return_value='/some/dir'))
    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value=''))
    @mock.patch('treadmill.subproc.get_aliases', mock.Mock(return_value={}))
    def test_sysdir_cleanslate(self):
        """Verifies that sys directories are always clean slate."""
        # Disable access to protected member warning.
        #
        # pylint: disable=W0212

        base_dir = os.path.join(self.root, 'some/dir')
        fs.mkdir_safe(base_dir)
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
                        'command': '/path/to/command',
                        'restart': {
                            'limit': 3,
                            'interval': 60,
                        },
                    }, {
                        'name': 'command2',
                        'command': '/path/to/other/command',
                        'restart': {
                            'limit': 3,
                            'interval': 60,
                        },
                    }
                ],
                'system_services': [
                    {
                        'name': 'command3',
                        'command': '/path/to/sbin/command',
                        'restart': {
                            'limit': 3,
                            'interval': 60,
                        },
                    }, {
                        'name': 'command4',
                        'command': '/path/to/other/sbin/command',
                        'restart': {
                            'limit': 3,
                            'interval': 60,
                        },
                    }
                ],
                'vring': {
                    'cells': [],
                },
            }
        )

        treadmill.runtime.linux.image.native.create_supervision_tree(
            base_dir,
            app
        )

        self.assertTrue(os.path.exists(os.path.join(base_dir, 'sys')))
        with open(os.path.join(base_dir, 'sys', 'toberemoved'), 'w+'):
            pass

        self.assertTrue(
            os.path.exists(os.path.join(base_dir, 'sys', 'toberemoved')))

        treadmill.runtime.linux.image.native.create_supervision_tree(
            base_dir,
            app
        )
        self.assertTrue(os.path.exists(os.path.join(base_dir, 'sys')))
        self.assertFalse(
            os.path.exists(os.path.join(base_dir, 'sys', 'toberemoved')))


if __name__ == '__main__':
    unittest.main()
