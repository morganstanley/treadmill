"""
Unit test for treadmill.appmgr.run
"""

# Disable C0302: Too many lines in module.
# pylint: disable=C0302

import os
import pwd
import shutil
import socket
import stat
import tempfile
import unittest

from collections import namedtuple

import mock

import treadmill
from treadmill import appmgr
from treadmill import firewall
from treadmill import utils
from treadmill import fs

from treadmill.appmgr import run as app_run


class AppMgrRunTest(unittest.TestCase):
    """Tests for teadmill.appmgr."""

    def setUp(self):
        # Access protected module _base_service
        # pylint: disable=W0212
        self.root = tempfile.mkdtemp()
        self.app_env = mock.Mock(
            root=self.root,
            host_ip='172.31.81.67',
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

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.fs.chroot_init', mock.Mock())
    @mock.patch('treadmill.fs.create_filesystem', mock.Mock())
    @mock.patch('treadmill.fs.test_filesystem', mock.Mock(return_value=False))
    @mock.patch('treadmill.fs.make_rootfs', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.fs.configure_plugins', mock.Mock())
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    @mock.patch('treadmill.fs.mount_filesystem', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/test_treadmill'))
    @mock.patch('shutil.copytree', mock.Mock())
    @mock.patch('shutil.copyfile', mock.Mock())
    def test__create_root_dir(self):
        """Test creation on the container root directory."""
        # Access protected module _create_root_dir
        # pylint: disable=W0212
        app = utils.to_obj(
            {
                'proid': 'myproid',
                'name': 'myproid.test#0',
                'uniqueid': 'ID1234',
                'environment': 'dev',
                'disk': '100G',
            }
        )
        app_unique_name = appmgr.app_unique_name(app)
        container_dir = os.path.join(self.root, 'apps', app_unique_name)
        mock_ld_client = self.app_env.svc_localdisk.make_client.return_value
        localdisk = {
            'block_dev': '/dev/foo',
        }
        mock_ld_client.wait.return_value = localdisk
        treadmill.appmgr.run._create_root_dir(self.app_env,
                                              container_dir,
                                              '/some/root_dir',
                                              app)

        treadmill.fs.chroot_init.assert_called_with('/some/root_dir')
        treadmill.fs.create_filesystem.assert_called_with('/dev/foo')
        treadmill.fs.mount_filesystem('/dev/foo', '/some/root_dir')
        treadmill.fs.make_rootfs.assert_called_with('/some/root_dir',
                                                    'myproid')
        treadmill.fs.configure_plugins.assert_called_with(
            self.root,
            '/some/root_dir',
            app
        )
        shutil.copytree.assert_called_with(
            os.path.join(self.app_env.root, 'etc'),
            '/some/root_dir/.etc'
        )
        shutil.copyfile.assert_called_with(
            '/etc/hosts',
            '/some/root_dir/.etc/hosts'
        )
        treadmill.subproc.check_call.assert_has_calls([
            mock.call(
                [
                    'mount', '-n', '--bind',
                    os.path.join(self.app_env.root, 'etc/resolv.conf'),
                    '/etc/resolv.conf'
                ]
            )
        ])

    @mock.patch('treadmill.appmgr.manifest.read', mock.Mock())
    @mock.patch('treadmill.cgroups.join', mock.Mock())
    def test_apply_cgroup_limits(self):
        """Test cgroup creation."""
        manifest = {
            'name': 'myproid.test#0',
            'uniqueid': 'ID1234',
        }
        treadmill.appmgr.manifest.read.return_value = manifest
        mock_cgroup_client = self.app_env.svc_cgroup.make_client.return_value
        cgroups = {
            'cpu': '/some/path',
            'cpuacct': '/some/other/path',
            'memory': '/mem/path',
            'blkio': '/io/path',
        }
        mock_cgroup_client.wait.return_value = cgroups
        app_dir = os.path.join(self.root, 'apps', 'myproid.test#0')
        os.makedirs(app_dir)

        app_run.apply_cgroup_limits(
            self.app_env,
            app_dir,
        )

        self.app_env.svc_cgroup.make_client.assert_called_with(
            os.path.join(app_dir, 'cgroups')
        )
        mock_cgroup_client.wait.assert_called_with(
            'myproid.test-0-0000000ID1234'
        )
        treadmill.cgroups.join.assert_has_calls(
            [
                mock.call(ss, path)
                for ss, path in cgroups.items()
            ],
            any_order=True
        )

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

        treadmill.appmgr.run._share_cgroup_info(app, '/some/root_dir')

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
    def test__create_supervision_tree(self):
        """Test creation of the supervision tree."""
        # pylint: disable=W0212
        treadmill.subproc.EXECUTABLES = {
            'chroot': '/bin/ls',
            'pid1': '/bin/ls',
        }
        # Access protected module _create_supervision_tree
        # pylint: disable=W0212
        app = utils.to_obj(
            {
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
        events_dir = '/some/dir/appevents'

        treadmill.appmgr.run._create_supervision_tree(
            base_dir,
            events_dir,
            app,
        )

        treadmill.fs.mkdir_safe.assert_has_calls([
            mock.call('/some/dir/root/services'),
            mock.call('/some/dir/services'),
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
            mock.call(
                '/some/dir/sys/start_container/run',
                'supervisor.run_sys',
                cmd=('/bin/ls /some/dir/root /bin/ls '
                     '-m -p -i s6-svscan /services')
            ),
            mock.call('/some/dir/sys/start_container/log/run',
                      'logger.run'),
        ])
        treadmill.utils.touch.assert_has_calls([
            mock.call('/some/dir/sys/start_container/down'),
        ])

    @mock.patch('socket.socket', mock.Mock(autospec=True))
    @mock.patch('treadmill.appmgr.run._allocate_sockets', mock.Mock())
    def test__allocate_network_ports(self):
        """Test network port allocation.
        """
        # access protected module _allocate_network_ports
        # pylint: disable=w0212
        treadmill.appmgr.run._allocate_sockets.side_effect = \
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
            'ephemeral_ports': 3,
        }

        treadmill.appmgr.run._allocate_network_ports(
            '1.2.3.4',
            manifest
        )

        # in the updated manifest, make sure that real_port is specificed from
        # the ephemeral range as returnd by getsockname.
        self.assertEquals(8000,
                          manifest['endpoints'][0]['port'])
        self.assertEquals(50001,
                          manifest['endpoints'][0]['real_port'])

        self.assertEquals(60001,
                          manifest['endpoints'][1]['port'])
        self.assertEquals(60001,
                          manifest['endpoints'][1]['real_port'])

        self.assertEquals(5353,
                          manifest['endpoints'][2]['port'])
        self.assertEquals(12345,
                          manifest['endpoints'][2]['real_port'])

        self.assertEquals(54321,
                          manifest['endpoints'][3]['port'])
        self.assertEquals(54321,
                          manifest['endpoints'][3]['real_port'])

        self.assertEquals([10000, 10001, 10002],
                          manifest['ephemeral_ports'])

    @mock.patch('treadmill.iptables.add_ip_set', mock.Mock())
    @mock.patch('treadmill.newnet.create_newnet', mock.Mock())
    def test__unshare_network_simple(self):
        """Tests unshare network sequence.
        """
        # Access protected module _create_supervision_tree
        # pylint: disable=W0212
        app = utils.to_obj(
            {
                'name': 'proid.test#0',
                'uniqueid': 'ID1234',
                'environment': 'dev',
                'network': {
                    'veth': 'id1234.0',
                    'vip': '192.168.1.1',
                    'gateway': '192.168.254.254',
                },
                'host_ip': '172.31.81.67',
                'shared_ip': True,
                'ephemeral_ports': [],
                'endpoints': [
                    {
                        'real_port': '5007',
                        'proto': 'tcp',
                        'port': '22',
                        'type': 'infra'
                    },
                    {
                        'real_port': '5013',
                        'proto': 'udp',
                        'port': '12345'
                    }
                ],
            }
        )
        app_unique_name = appmgr.app_unique_name(app)

        appmgr.run._unshare_network(self.app_env, app)

        treadmill.iptables.add_ip_set.assert_has_calls([
            mock.call(treadmill.iptables.SET_INFRA_SVC,
                      '192.168.1.1,tcp:22'),
        ])

        self.app_env.rules.create_rule.assert_has_calls(
            [
                mock.call(rule=firewall.DNATRule('tcp',
                                                 '172.31.81.67', '5007',
                                                 '192.168.1.1', '22'),
                          owner=app_unique_name),
                mock.call(rule=firewall.DNATRule('udp',
                                                 '172.31.81.67', '5013',
                                                 '192.168.1.1', '12345'),
                          owner=app_unique_name)
            ],
            any_order=True
        )
        treadmill.newnet.create_newnet.assert_called_with(
            'id1234.0',
            '192.168.1.1',
            '192.168.254.254',
            '172.31.81.67',
        )

    @mock.patch('socket.gethostbyname', mock.Mock())
    @mock.patch('treadmill.iptables.add_ip_set', mock.Mock())
    @mock.patch('treadmill.newnet.create_newnet', mock.Mock())
    def test__unshare_network_complex(self):
        """Test unshare network advanced sequence (ephemeral/passthrough)."""
        # Access protected module _create_supervision_tree
        # pylint: disable=W0212
        app = utils.to_obj(
            {
                'name': 'myproid.test#0',
                'environment': 'dev',
                'uniqueid': 'ID1234',
                'network': {
                    'veth': 'id1234.0',
                    'vip': '192.168.0.2',
                    'gateway': '192.168.254.254'
                },
                'shared_ip': False,
                'endpoints': [
                    {
                        'name': 'ssh',
                        'port': 54321,
                        'real_port': 54321,
                        'type': 'infra',
                        'proto': 'tcp',
                    },
                    {
                        'name': 'test2',
                        'port': 54322,
                        'real_port': 54322,
                        'proto': 'udp',
                    }
                ],
                'ephemeral_ports': [
                    10000,
                    10001,
                    10002,
                ],
                'passthrough': [
                    'xxx',
                    'yyy',
                    'zzz',
                ],
            }
        )
        app_unique_name = appmgr.app_unique_name(app)
        hosts_to_ip = {
            'xxx': '4.4.4.4',
            'yyy': '5.5.5.5',
            'zzz': '5.5.5.5',
        }
        socket.gethostbyname.side_effect = lambda h: hosts_to_ip[h]
        self.app_env.rules.get_rules.return_value = set()

        treadmill.appmgr.run._unshare_network(
            self.app_env,
            app
        )

        self.app_env.rules.create_rule.assert_has_calls(
            [
                mock.call(rule=firewall.DNATRule('tcp',
                                                 '172.31.81.67', 54321,
                                                 '192.168.0.2', 54321),
                          owner=app_unique_name),
                mock.call(rule=firewall.DNATRule('udp',
                                                 '172.31.81.67', 54322,
                                                 '192.168.0.2', 54322),
                          owner=app_unique_name),
                mock.call(rule=firewall.DNATRule('tcp',
                                                 '172.31.81.67', 10000,
                                                 '192.168.0.2', 10000),
                          owner=app_unique_name),
                mock.call(rule=firewall.DNATRule('tcp',
                                                 '172.31.81.67', 10001,
                                                 '192.168.0.2', 10001),
                          owner=app_unique_name),
                mock.call(rule=firewall.DNATRule('tcp',
                                                 '172.31.81.67', 10002,
                                                 '192.168.0.2', 10002),
                          owner=app_unique_name),
                mock.call(rule=firewall.PassThroughRule('4.4.4.4',
                                                        '192.168.0.2'),
                          owner=app_unique_name),
                mock.call(rule=firewall.PassThroughRule('5.5.5.5',
                                                        '192.168.0.2'),
                          owner=app_unique_name),
            ],
            any_order=True
        )

        # Check that infra services + ephemeral ports are in the same set.
        treadmill.iptables.add_ip_set.assert_has_calls([
            mock.call(treadmill.iptables.SET_INFRA_SVC,
                      '192.168.0.2,tcp:54321'),
            mock.call(treadmill.iptables.SET_INFRA_SVC,
                      '192.168.0.2,tcp:10000'),
            mock.call(treadmill.iptables.SET_INFRA_SVC,
                      '192.168.0.2,tcp:10001'),
            mock.call(treadmill.iptables.SET_INFRA_SVC,
                      '192.168.0.2,tcp:10002'),
        ])

        treadmill.newnet.create_newnet.assert_called_with(
            'id1234.0',
            '192.168.0.2',
            '192.168.254.254',
            None,
        )

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appmgr.manifest.read', mock.Mock())
    @mock.patch('treadmill.appmgr.run._allocate_network_ports', mock.Mock())
    @mock.patch('treadmill.appmgr.run._create_environ_dir', mock.Mock())
    @mock.patch('treadmill.appmgr.run._create_root_dir', mock.Mock())
    @mock.patch('treadmill.appmgr.run._create_supervision_tree', mock.Mock())
    @mock.patch('treadmill.appmgr.run._prepare_ldpreload', mock.Mock())
    @mock.patch('treadmill.appmgr.run._share_cgroup_info', mock.Mock())
    @mock.patch('treadmill.appmgr.run._unshare_network', mock.Mock())
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    @mock.patch('treadmill.supervisor.exec_root_supervisor', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/treadmill'))
    def test_run(self):
        """Tests appmgr.run sequence, which will result in supervisor exec.
        """
        # access protected module _allocate_network_ports
        # pylint: disable=w0212
        manifest = {
            'shared_network': False,
            'ephemeral_ports': 3,
            'passthrough': [
                'xxx',
                'yyy',
                'zzz'
            ],
            'memory': '100M',
            'host_ip': '172.31.81.67',
            'uniqueid': 'ID1234',
            'services': [
                {
                    'name': 'web_server',
                    'command': '/bin/true',
                    'restart': {
                        'limit': 3,
                        'interval': 60,
                    },
                }
            ],
            'disk': '100G',
            'tickets': True,
            'name': 'proid.myapp#0',
            'system_services': [],
            'environment': 'dev',
            'proid': 'foo',
            'endpoints': [
                {
                    'name': 'http',
                    'port': 8000
                },
                {
                    'name': 'port0',
                    'port': 0
                },
                {
                    'type': 'infra',
                    'name': 'ssh',
                    'port': 0
                }
            ],
            'cpu': '100%'
        }
        treadmill.appmgr.manifest.read.return_value = manifest
        app_unique_name = 'proid.myapp-0-0000000ID1234'
        app_dir = os.path.join(self.root, 'apps', app_unique_name)
        os.makedirs(app_dir)
        mock_nwrk_client = self.app_env.svc_network.make_client.return_value
        network = {
            'vip': '2.2.2.2',
            'gateway': '1.1.1.1',
            'veth': 'testveth.0',
        }
        mock_nwrk_client.wait.return_value = network

        def _fake_allocate_network_ports(_ip, manifest):
            """Mimick inplace manifest modification in _allocate_network_ports.
            """
            manifest['ephemeral_ports'] = ['1', '2', '3']
            return mock.DEFAULT
        treadmill.appmgr.run._allocate_network_ports.side_effect = \
            _fake_allocate_network_ports
        mock_watchdog = mock.Mock()

        treadmill.subproc.EXECUTABLES['treadmill_bind_preload.so'] = (
            '/some/$LIB/treadmill_bind_preload.so')

        app_run.run(
            self.app_env, app_dir, mock_watchdog, terminated=()
        )

        # Check that port allocation is correctly called.
        # XXX(boysson): potential mock bug: assert_call expects the vip since
        #               manifest is modified in place even though the vip are
        #               allocated *after*.
        manifest['vip'] = {
            'ip0': '1.1.1.1',
            'ip1': '2.2.2.2',
        }
        manifest['network'] = network
        manifest['ephemeral_ports'] = ['1', '2', '3']
        treadmill.appmgr.run._allocate_network_ports.assert_called_with(
            '172.31.81.67', manifest,
        )
        # Make sure, post modification, that the manifest is readable by other.
        st = os.stat(os.path.join(app_dir, 'state.yml'))
        self.assertTrue(st.st_mode & stat.S_IRUSR)
        self.assertTrue(st.st_mode & stat.S_IRGRP)
        self.assertTrue(st.st_mode & stat.S_IROTH)
        self.assertTrue(st.st_mode & stat.S_IWUSR)
        self.assertFalse(st.st_mode & stat.S_IWGRP)
        self.assertFalse(st.st_mode & stat.S_IWOTH)
        # State yml is what is copied in the container
        shutil.copy.assert_called_with(
            os.path.join(app_dir, 'state.yml'),
            os.path.join(app_dir, 'root', 'app.yml'),
        )

        # Network unshare
        app = utils.to_obj(manifest)
        treadmill.appmgr.run._unshare_network.assert_called_with(
            self.app_env, app
        )
        # Create root dir
        treadmill.appmgr.run._create_root_dir.assert_called_with(
            self.app_env,
            app_dir,
            os.path.join(app_dir, 'root'),
            app,
        )
        # XXX(boysson): Missing environ_dir/manifest_dir tests
        # Create supervision tree
        treadmill.appmgr.run._create_supervision_tree.assert_called_with(
            app_dir,
            self.app_env.app_events_dir,
            app
        )
        treadmill.appmgr.run._share_cgroup_info.assert_called_with(
            app,
            os.path.join(app_dir, 'root'),
        )
        # Ephemeral LDPRELOAD
        treadmill.appmgr.run._prepare_ldpreload.assert_called_with(
            os.path.join(app_dir, 'root'),
            ['/some/$LIB/treadmill_bind_preload.so']
        )
        # Misc bind mounts
        treadmill.fs.mount_bind.assert_has_calls([
            mock.call(
                os.path.join(app_dir, 'root'),
                '/etc/resolv.conf',
                bind_opt='--bind',
                target=os.path.join(app_dir, 'root/.etc/resolv.conf')
            ),
            mock.call(
                os.path.join(app_dir, 'root'),
                '/etc/hosts',
                bind_opt='--bind',
                target=os.path.join(app_dir, 'root/.etc/hosts')
            ),
            mock.call(
                os.path.join(app_dir, 'root'),
                '/etc/ld.so.preload',
                bind_opt='--bind',
                target=os.path.join(app_dir, 'root/.etc/ld.so.preload')
            ),
            # mock.call(
            #     os.path.join(app_dir, 'root'),
            #     '/etc/pam.d/sshd',
            #     bind_opt='--bind',
            #     target=os.path.join(app_dir, 'root/.etc/pam.d/sshd')
            # ),
        ])

        self.assertTrue(mock_watchdog.remove.called)

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appmgr.manifest.read', mock.Mock())
    @mock.patch('treadmill.appmgr.run._allocate_network_ports', mock.Mock())
    @mock.patch('treadmill.appmgr.run._create_environ_dir', mock.Mock())
    @mock.patch('treadmill.appmgr.run._create_root_dir', mock.Mock())
    @mock.patch('treadmill.appmgr.run._create_supervision_tree', mock.Mock())
    @mock.patch('treadmill.appmgr.run._prepare_ldpreload', mock.Mock())
    @mock.patch('treadmill.appmgr.run._share_cgroup_info', mock.Mock())
    @mock.patch('treadmill.appmgr.run._unshare_network', mock.Mock())
    @mock.patch('treadmill.fs.configure_plugins', mock.Mock())
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    @mock.patch('treadmill.supervisor.exec_root_supervisor', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/treadmill'))
    def test_run_no_ephemeral(self):
        """Tests appmgr.run without ephemeral ports in manifest."""
        # Modify app manifest so that it does not contain ephemeral ports,
        # make sure that .etc/ld.so.preload is not created.
        # access protected module _allocate_network_ports
        # pylint: disable=w0212
        manifest = {
            'shared_network': False,
            'disk': '100G',
            'name': 'proid.myapp#0',
            'passthrough': [
                'xxx',
                'yyy',
                'zzz'
            ],
            'memory': '100M',
            'host_ip': '172.31.81.67',
            'system_services': [],
            'environment': 'dev',
            'uniqueid': 'ID1234',
            'proid': 'foo',
            'services': [
                {
                    'name': 'web_server',
                    'command': '/bin/true',
                    'restart': {
                        'limit': 3,
                        'interval': 60,
                    },
                }
            ],
            'endpoints': [
                {
                    'name': 'http',
                    'port': 8000
                },
                {
                    'name': 'port0',
                    'port': 0
                },
                {
                    'type': 'infra',
                    'name': 'ssh',
                    'port': 0
                }
            ],
            'cpu': '100%'
        }
        treadmill.appmgr.manifest.read.return_value = manifest
        app_dir = os.path.join(self.root, 'apps', 'proid.myapp#0')
        os.makedirs(app_dir)
        mock_nwrk_client = self.app_env.svc_network.make_client.return_value
        network = {
            'vip': '2.2.2.2',
            'gateway': '1.1.1.1',
            'veth': 'testveth.0',
        }
        mock_nwrk_client.wait.return_value = network
        rootdir = os.path.join(app_dir, 'root')

        def _fake_allocate_network_ports(_ip, manifest):
            """Mimick inplace manifest modification in _allocate_network_ports.
            """
            manifest['ephemeral_ports'] = []
            return mock.DEFAULT
        treadmill.appmgr.run._allocate_network_ports.side_effect = \
            _fake_allocate_network_ports
        mock_watchdog = mock.Mock()

        app_run.run(
            self.app_env, app_dir, mock_watchdog, terminated=()
        )

        self.assertFalse(
            os.path.exists(
                os.path.join(rootdir, '.etc/ld.so.preload')
            )
        )
        self.assertTrue(mock_watchdog.remove.called)

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appmgr.manifest.read', mock.Mock())
    @mock.patch('treadmill.appmgr.run._allocate_network_ports', mock.Mock())
    @mock.patch('treadmill.appmgr.run._create_environ_dir', mock.Mock())
    @mock.patch('treadmill.appmgr.run._create_root_dir', mock.Mock())
    @mock.patch('treadmill.appmgr.run._create_supervision_tree', mock.Mock())
    @mock.patch('treadmill.appmgr.run._prepare_ldpreload', mock.Mock())
    @mock.patch('treadmill.appmgr.run._share_cgroup_info', mock.Mock())
    @mock.patch('treadmill.appmgr.run._unshare_network', mock.Mock())
    @mock.patch('treadmill.fs.configure_plugins', mock.Mock())
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    @mock.patch('treadmill.supervisor.exec_root_supervisor', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/treadmill'))
    def test_run_ticket_failure(self):
        """Tests appmgr.run sequence, which will result in supervisor exec.
        """
        # access protected module _allocate_network_ports
        # pylint: disable=w0212
        manifest = {
            'shared_network': False,
            'disk': '100G',
            'name': 'proid.myapp#0',
            'memory': '100M',
            'environment': 'dev',
            'uniqueid': 'ID1234',
            'proid': 'foo',
            'services': [
                {
                    'name': 'web_server',
                    'command': '/bin/true',
                    'restart': {
                        'limit': 3,
                        'interval': 60,
                    },
                }
            ],
            'endpoints': [
                {
                    'name': 'http',
                    'port': 8000
                },
                {
                    'name': 'port0',
                    'port': 0
                }
            ],
            'cpu': '100%'
        }
        treadmill.appmgr.manifest.read.return_value = manifest
        app_dir = os.path.join(self.root, 'apps', 'proid.myapp#0')
        os.makedirs(app_dir)
        mock_nwrk_client = self.app_env.svc_network.make_client.return_value
        network = {
            'vip': '2.2.2.2',
            'gateway': '1.1.1.1',
            'veth': 'testveth.0',
        }
        mock_nwrk_client.wait.return_value = network

        def _fake_allocate_network_ports(_ip, manifest):
            """Mimick inplace manifest modification in _allocate_network_ports.
            """
            manifest['ephemeral_ports'] = []
            return mock.DEFAULT
        treadmill.appmgr.run._allocate_network_ports.side_effect = \
            _fake_allocate_network_ports
        # Make sure that despite ticket absence there is no throw.
        mock_watchdog = mock.Mock()

        app_run.run(
            self.app_env, app_dir, mock_watchdog, terminated=()
        )

        self.assertTrue(mock_watchdog.remove.called)

    def test__prepare_ldpreload(self):
        """Test generation of the etc/ldpreload file."""
        # access protected module _prepare_ldpreload
        # pylint: disable=w0212
        appmgr.run._prepare_ldpreload(self.root, ['/foo/1.so', '/foo/2.so'])
        newfile = open(os.path.join(self.root,
                                    '.etc', 'ld.so.preload')).readlines()
        self.assertEquals('/foo/2.so\n', newfile[-1])
        self.assertEquals('/foo/1.so\n', newfile[-2])

    @mock.patch('pwd.getpwnam', mock.Mock(
        return_value=namedtuple(
            'pwnam',
            ['pw_uid', 'pw_dir', 'pw_shell']
        )(3, '/', '/bin/sh')))
    @mock.patch('treadmill.fs.mount_bind', mock.Mock())
    @mock.patch('treadmill.utils.rootdir', mock.Mock(return_value='/some/dir'))
    @mock.patch('treadmill.subproc.resolve', mock.Mock(return_value=''))
    def test_sysdir_cleanslate(self):
        """Verifies that sys directories are always clean slate."""
        # Disable access to protected member warning.
        #
        # pylint: disable=W0212

        base_dir = os.path.join(self.root, 'some/dir')
        events_dir = os.path.join(base_dir, 'appevents')
        fs.mkdir_safe(base_dir)
        app = utils.to_obj(
            {
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

        treadmill.appmgr.run._create_supervision_tree(
            base_dir,
            events_dir,
            app,
        )

        self.assertTrue(os.path.exists(os.path.join(base_dir, 'sys')))
        with open(os.path.join(base_dir, 'sys', 'toberemoved'), 'w+'):
            pass

        self.assertTrue(
            os.path.exists(os.path.join(base_dir, 'sys', 'toberemoved')))

        treadmill.appmgr.run._create_supervision_tree(
            base_dir,
            events_dir,
            app,
        )
        self.assertTrue(os.path.exists(os.path.join(base_dir, 'sys')))
        self.assertFalse(
            os.path.exists(os.path.join(base_dir, 'sys', 'toberemoved')))


if __name__ == '__main__':
    unittest.main()
