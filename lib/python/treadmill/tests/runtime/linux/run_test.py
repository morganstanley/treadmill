"""Unit test for treadmill.runtime.linux._run.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# Disable C0302: Too many lines in module.
# pylint: disable=C0302

import os
import shutil
import socket
import stat   # pylint: disable=wrong-import-order
import tempfile
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows   # pylint: disable=W0611

import treadmill
import treadmill.rulefile

from treadmill import appcfg
from treadmill import firewall
from treadmill import iptables
from treadmill import utils

from treadmill.syscall import unshare

from treadmill.runtime.linux import _run as app_run

_PATH_EXISTS = os.path.exists


class LinuxRuntimeRunTest(unittest.TestCase):
    """Tests for treadmill.runtime.linux._run."""

    def setUp(self):
        # Access protected module _base_service
        # pylint: disable=W0212
        self.root = tempfile.mkdtemp()
        self.tm_env = mock.Mock(
            root=self.root,
            apps_dir=os.path.join(self.root, 'apps'),
            endpoints_dir=os.path.join(self.root, 'endpoints'),
            rules_dir=os.path.join(self.root, 'rules'),
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

    @mock.patch('pwd.getpwnam', mock.Mock())
    @mock.patch('os.chown', mock.Mock())
    @mock.patch('treadmill.fs.linux.blk_fs_create', mock.Mock())
    @mock.patch('treadmill.fs.linux.blk_fs_test',
                mock.Mock(return_value=False))
    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock())
    @mock.patch('treadmill.fs.linux.mount_filesystem', mock.Mock())
    @mock.patch('treadmill.fs.mkdir_safe', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/test_treadmill'))
    @mock.patch('treadmill.syscall.unshare.unshare', mock.Mock())
    def test__create_root_dir(self):
        """Test creation on the container root directory."""
        # Access protected module _create_root_dir
        # pylint: disable=W0212
        app = utils.to_obj(
            {
                'type': 'native',
                'proid': 'myproid',
                'name': 'myproid.test#0',
                'uniqueid': 'ID1234',
                'environment': 'dev',
                'disk': '100G',
            }
        )
        app_unique_name = appcfg.app_unique_name(app)
        container_dir = '/some/dir'
        localdisk = {
            'block_dev': '/dev/foo',
        }

        treadmill.runtime.linux._run._create_root_dir(container_dir,
                                                      localdisk)

        treadmill.fs.linux.blk_fs_create.assert_called_with('/dev/foo')
        unshare.unshare.assert_called_with(unshare.CLONE_NEWNS)
        treadmill.fs.linux.mount_filesystem.assert_called_with(
            '/dev/foo',
            os.path.join(container_dir, 'root'),
            fs_type='ext4'
        )

    @mock.patch('treadmill.cgroups.join', mock.Mock())
    def test_apply_cgroup_limits(self):
        """Test cgroup creation."""
        # Disable W0212: Access to a protected member
        # pylint: disable=W0212
        cgroups = {
            'cpu': '/some/path',
            'cpuacct': '/some/other/path',
            'memory': '/mem/path',
            'blkio': '/io/path',
        }

        app_run._apply_cgroup_limits(
            cgroups,
        )

        treadmill.cgroups.join.assert_has_calls(
            [
                mock.call(ss, path)
                for ss, path in cgroups.items()
            ],
            any_order=True
        )

    @mock.patch('treadmill.iptables.add_ip_set', mock.Mock(set_spec=True))
    @mock.patch('treadmill.newnet.create_newnet', mock.Mock(set_spec=True))
    @mock.patch('treadmill.plugin_manager.load', mock.Mock(set_spec=True))
    def test__unshare_network_simple(self):
        """Tests unshare network sequence.
        """
        # Disable W0212: Access to a protected member
        # pylint: disable=W0212
        app = utils.to_obj(
            {
                'type': 'native',
                'name': 'proid.test#0',
                'uniqueid': 'ID1234',
                'environment': 'dev',
                'network': {
                    'veth': 'id1234.0',
                    'vip': '192.168.1.1',
                    'gateway': '192.168.254.254',
                    'external_ip': '172.31.81.67',
                },
                'shared_ip': True,
                'ephemeral_ports': {
                    'tcp': [],
                    'udp': [],
                },
                'endpoints': [
                    {
                        'name': 'foo',
                        'real_port': '5007',
                        'proto': 'tcp',
                        'port': '22',
                        'type': 'infra'
                    },
                    {
                        'name': 'bla',
                        'real_port': '5013',
                        'proto': 'udp',
                        'port': '12345'
                    }
                ],
                'vring': {
                    'some': 'data'
                }
            }
        )
        app_unique_name = appcfg.app_unique_name(app)

        treadmill.runtime.linux._run._unshare_network(
            self.tm_env, 'test_container_dir', app
        )

        treadmill.iptables.add_ip_set.assert_has_calls(
            [
                mock.call(treadmill.iptables.SET_VRING_CONTAINERS,
                          '192.168.1.1'),
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.1.1,tcp:22'),
            ],
            any_order=True
        )

        self.tm_env.rules.create_rule.assert_has_calls(
            [
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='tcp',
                              dst_ip='172.31.81.67', dst_port='5007',
                              new_ip='192.168.1.1', new_port='22'
                          ),
                          owner=app_unique_name),
                mock.call(chain=iptables.POSTROUTING_SNAT,
                          rule=firewall.SNATRule(
                              proto='tcp',
                              src_ip='192.168.1.1', src_port='22',
                              new_ip='172.31.81.67', new_port='5007'
                          ),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='udp',
                              dst_ip='172.31.81.67', dst_port='5013',
                              new_ip='192.168.1.1', new_port='12345'
                          ),
                          owner=app_unique_name),
                mock.call(chain=iptables.POSTROUTING_SNAT,
                          rule=firewall.SNATRule(
                              proto='udp',
                              src_ip='192.168.1.1', src_port='12345',
                              new_ip='172.31.81.67', new_port='5013'
                          ),
                          owner=app_unique_name)
            ],
            any_order=True
        )
        self.assertEqual(self.tm_env.rules.create_rule.call_count, 4)
        treadmill.newnet.create_newnet.assert_called_with(
            'id1234.0',
            '192.168.1.1',
            '192.168.254.254',
            '172.31.81.67',
        )

    @mock.patch('socket.gethostbyname', mock.Mock(set_spec=True))
    @mock.patch('treadmill.iptables.add_ip_set', mock.Mock(set_spec=True))
    @mock.patch('treadmill.newnet.create_newnet', mock.Mock(set_spec=True))
    @mock.patch('treadmill.plugin_manager.load', mock.Mock(set_spec=True))
    def test__unshare_network_complex(self):
        """Test unshare network advanced sequence (ephemeral/passthrough)."""
        # Disable W0212: Access to a protected member
        # pylint: disable=W0212
        app = utils.to_obj(
            {
                'type': 'native',
                'name': 'myproid.test#0',
                'environment': 'dev',
                'uniqueid': 'ID1234',
                'network': {
                    'veth': 'id1234.0',
                    'vip': '192.168.0.2',
                    'gateway': '192.168.254.254',
                    'external_ip': '172.31.81.67',
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
                'ephemeral_ports': {
                    'tcp': [10000, 10001, 10002],
                    'udp': [],
                },
                'passthrough': [
                    'xxx',
                    'yyy',
                    'zzz',
                ],
                'vring': {
                    'some': 'data'
                }
            }
        )
        app_unique_name = appcfg.app_unique_name(app)
        hosts_to_ip = {
            'xxx': '4.4.4.4',
            'yyy': '5.5.5.5',
            'zzz': '5.5.5.5',
        }
        socket.gethostbyname.side_effect = lambda h: hosts_to_ip[h]
        self.tm_env.rules.get_rules.return_value = set()

        treadmill.runtime.linux._run._unshare_network(
            self.tm_env,
            'test_container_dir',
            app
        )

        self.tm_env.rules.create_rule.assert_has_calls(
            [
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='tcp',
                              dst_ip='172.31.81.67', dst_port=54321,
                              new_ip='192.168.0.2', new_port=54321),
                          owner=app_unique_name),
                mock.call(chain=iptables.POSTROUTING_SNAT,
                          rule=firewall.SNATRule(
                              proto='tcp',
                              src_ip='192.168.0.2', src_port=54321,
                              new_ip='172.31.81.67', new_port=54321),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='udp',
                              dst_ip='172.31.81.67', dst_port=54322,
                              new_ip='192.168.0.2', new_port=54322),
                          owner=app_unique_name),
                mock.call(chain=iptables.POSTROUTING_SNAT,
                          rule=firewall.SNATRule(
                              proto='udp',
                              src_ip='192.168.0.2', src_port=54322,
                              new_ip='172.31.81.67', new_port=54322),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='tcp',
                              dst_ip='172.31.81.67', dst_port=10000,
                              new_ip='192.168.0.2', new_port=10000),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='tcp',
                              dst_ip='172.31.81.67', dst_port=10001,
                              new_ip='192.168.0.2', new_port=10001),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='tcp',
                              dst_ip='172.31.81.67', dst_port=10002,
                              new_ip='192.168.0.2', new_port=10002),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_PASSTHROUGH,
                          rule=firewall.PassThroughRule('4.4.4.4',
                                                        '192.168.0.2'),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_PASSTHROUGH,
                          rule=firewall.PassThroughRule('5.5.5.5',
                                                        '192.168.0.2'),
                          owner=app_unique_name),
            ],
            any_order=True
        )
        self.assertEqual(self.tm_env.rules.create_rule.call_count, 9)

        # Check that infra services + ephemeral ports are in the same set.
        treadmill.iptables.add_ip_set.assert_has_calls(
            [
                mock.call(treadmill.iptables.SET_VRING_CONTAINERS,
                          '192.168.0.2'),
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.0.2,tcp:54321'),
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.0.2,tcp:10000'),
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.0.2,tcp:10001'),
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.0.2,tcp:10002'),
            ],
            any_order=True
        )

        treadmill.newnet.create_newnet.assert_called_with(
            'id1234.0',
            '192.168.0.2',
            '192.168.254.254',
            None,
        )

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('shutil.copytree', mock.Mock())
    @mock.patch('treadmill.runtime.allocate_network_ports', mock.Mock())
    @mock.patch('treadmill.runtime.linux._run._create_root_dir',
                mock.Mock(return_value='/foo'))
    @mock.patch('treadmill.runtime.linux._run._unshare_network', mock.Mock())
    @mock.patch('treadmill.runtime.linux._run._apply_cgroup_limits',
                mock.Mock())
    @mock.patch('treadmill.fs.linux.cleanup_mounts', mock.Mock(set_spec=True))
    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock())
    @mock.patch('treadmill.runtime.linux.image.get_image_repo', mock.Mock())
    @mock.patch('treadmill.apphook.configure', mock.Mock())
    @mock.patch('treadmill.subproc.exec_pid1', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/treadmill'))
    @mock.patch('os.path.exists', mock.Mock(
        side_effect=lambda path: True if 'root/.etc' in path else
        _PATH_EXISTS(path)
    ))
    @mock.patch('treadmill.subproc.resolve',
                mock.Mock(return_value='/tmp/treadmill_bind_preload.so'))
    def test_run(self):
        """Tests linux.run sequence, which will result in supervisor exec.
        """
        # Disable W0212: Access to a protected member
        # pylint: disable=W0212
        manifest = {
            'type': 'native',
            'shared_network': False,
            'ephemeral_ports': {
                'tcp': 3,
                'udp': 0,
            },
            'passthrough': [
                'xxx',
                'yyy',
                'zzz'
            ],
            'memory': '100M',
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

        app_unique_name = 'proid.myapp-0-0000000ID1234'
        app_dir = os.path.join(self.root, 'apps', app_unique_name)
        os.makedirs(app_dir)
        mock_cgroup_client = self.tm_env.svc_cgroup.make_client.return_value
        mock_ld_client = self.tm_env.svc_localdisk.make_client.return_value
        mock_nwrk_client = self.tm_env.svc_network.make_client.return_value
        cgroups = {
            'cpu': '/some/path',
            'cpuacct': '/some/other/path',
            'memory': '/mem/path',
            'blkio': '/io/path',
        }
        mock_cgroup_client.wait.return_value = cgroups
        network = {
            'vip': '2.2.2.2',
            'gateway': '1.1.1.1',
            'veth': 'testveth.0',
            'external_ip': '172.31.81.67',
        }
        mock_nwrk_client.wait.return_value = network

        def _fake_allocate_network_ports(_ip, manifest):
            """Mimick inplace manifest modification in allocate_network_ports.
            """
            manifest['ephemeral_ports'] = {'tcp': ['1', '2', '3']}
            return mock.DEFAULT
        treadmill.runtime.allocate_network_ports.side_effect = \
            _fake_allocate_network_ports
        mock_image = mock.Mock()
        treadmill.runtime.linux.image.get_image_repo.return_value = mock_image
        mock_runtime_config = mock.Mock()
        mock_runtime_config.host_mount_whitelist = []

        app_run.run(self.tm_env, mock_runtime_config, app_dir, manifest)

        mock_cgroup_client.put.assert_called_with(
            app_unique_name,
            {
                'memory': '100M',
                'cpu': '100%',
            }
        )
        mock_ld_client.put.assert_called_with(
            app_unique_name,
            {
                'size': '100G',
            }
        )
        mock_nwrk_client.put.assert_called_with(
            app_unique_name,
            {
                'environment': 'dev',
            }
        )
        mock_cgroup_client.wait.assert_called_with(
            app_unique_name
        )
        mock_ld_client.wait.assert_called_with(
            app_unique_name
        )
        mock_nwrk_client.wait.assert_called_with(
            app_unique_name
        )
        # Check that port allocation is correctly called.
        manifest['network'] = network
        manifest['ephemeral_ports'] = {'tcp': ['1', '2', '3']}
        treadmill.runtime.allocate_network_ports\
            .assert_called_with(
                '172.31.81.67', manifest,
            )
        # Make sure, post modification, that the manifest is readable by other.
        st = os.stat(os.path.join(app_dir, 'state.json'))
        self.assertTrue(st.st_mode & stat.S_IRUSR)
        self.assertTrue(st.st_mode & stat.S_IRGRP)
        self.assertTrue(st.st_mode & stat.S_IROTH)
        self.assertTrue(st.st_mode & stat.S_IWUSR)
        self.assertFalse(st.st_mode & stat.S_IWGRP)
        self.assertFalse(st.st_mode & stat.S_IWOTH)

        app = utils.to_obj(manifest)
        treadmill.runtime.linux._run._unshare_network.assert_called_with(
            self.tm_env, app_dir, app
        )
        # Create root dir
        treadmill.runtime.linux._run._create_root_dir.assert_called_with(
            app_dir,
            mock_ld_client.wait.return_value
        )

    @mock.patch('pwd.getpwnam', mock.Mock())
    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.runtime.allocate_network_ports',
                mock.Mock())
    @mock.patch('treadmill.runtime.linux._run._create_root_dir',
                mock.Mock(return_value='/foo'))
    @mock.patch('treadmill.runtime.linux._run._unshare_network', mock.Mock())
    @mock.patch('treadmill.runtime.linux._run._apply_cgroup_limits',
                mock.Mock())
    @mock.patch('treadmill.runtime.linux.image.get_image_repo', mock.Mock())
    @mock.patch('treadmill.fs.linux.cleanup_mounts', mock.Mock(set_spec=True))
    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock())
    @mock.patch('treadmill.apphook.configure', mock.Mock())
    @mock.patch('treadmill.subproc.exec_pid1', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/treadmill'))
    def test_run_no_ephemeral(self):
        """Tests linux.run without ephemeral ports in manifest."""
        # Modify app manifest so that it does not contain ephemeral ports,
        # make sure that .etc/ld.so.preload is not created.
        manifest = {
            'type': 'native',
            'shared_network': False,
            'disk': '100G',
            'name': 'proid.myapp#0',
            'passthrough': [
                'xxx',
                'yyy',
                'zzz'
            ],
            'memory': '100M',
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

        app_dir = os.path.join(self.root, 'apps', 'proid.myapp#0')
        os.makedirs(app_dir)
        mock_nwrk_client = self.tm_env.svc_network.make_client.return_value
        network = {
            'vip': '2.2.2.2',
            'gateway': '1.1.1.1',
            'veth': 'testveth.0',
            'external_ip': '172.31.81.67',
        }
        mock_nwrk_client.wait.return_value = network
        rootdir = os.path.join(app_dir, 'root')

        def _fake_allocate_network_ports(_ip, manifest):
            """Mimick inplace manifest modification in allocate_network_ports.
            """
            manifest['ephemeral_ports'] = {'tcp': 0, 'udp': 0}
            return mock.DEFAULT
        treadmill.runtime.allocate_network_ports.side_effect = \
            _fake_allocate_network_ports
        mock_runtime_config = mock.Mock()
        mock_runtime_config.host_mount_whitelist = []

        app_run.run(self.tm_env, mock_runtime_config, app_dir, manifest)

        self.assertFalse(
            os.path.exists(
                os.path.join(rootdir, '.etc/ld.so.preload')
            )
        )

    @mock.patch('pwd.getpwnam', mock.Mock())
    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.runtime.allocate_network_ports', mock.Mock())
    @mock.patch('treadmill.runtime.linux._run._create_root_dir',
                mock.Mock(return_value='/foo'))
    @mock.patch('treadmill.runtime.linux._run._unshare_network', mock.Mock())
    @mock.patch('treadmill.runtime.linux._run._apply_cgroup_limits',
                mock.Mock())
    @mock.patch('treadmill.runtime.linux.image.get_image_repo', mock.Mock())
    @mock.patch('treadmill.fs.linux.cleanup_mounts', mock.Mock(set_spec=True))
    @mock.patch('treadmill.fs.linux.mount_bind', mock.Mock())
    @mock.patch('treadmill.apphook.configure', mock.Mock())
    @mock.patch('treadmill.subproc.exec_pid1', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.utils.rootdir',
                mock.Mock(return_value='/treadmill'))
    def test_run_ticket_failure(self):
        """Tests linux.run sequence, which will result in supervisor exec.
        """
        manifest = {
            'type': 'native',
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

        app_dir = os.path.join(self.root, 'apps', 'proid.myapp#0')
        os.makedirs(app_dir)
        mock_nwrk_client = self.tm_env.svc_network.make_client.return_value
        network = {
            'vip': '2.2.2.2',
            'gateway': '1.1.1.1',
            'veth': 'testveth.0',
            'external_ip': '172.31.81.67',
        }
        mock_nwrk_client.wait.return_value = network

        def _fake_allocate_network_ports(_ip, manifest):
            """Mimick inplace manifest modification in allocate_network_ports.
            """
            manifest['ephemeral_ports'] = {'tcp': 0, 'udp': 0}
            return mock.DEFAULT
        treadmill.runtime.allocate_network_ports.side_effect = \
            _fake_allocate_network_ports
        mock_runtime_config = mock.Mock()
        mock_runtime_config.host_mount_whitelist = []
        # Make sure that despite ticket absence there is no throw.
        app_run.run(self.tm_env, mock_runtime_config, app_dir, manifest)

    @mock.patch('socket.socket.bind', mock.Mock())
    @mock.patch('socket.socket.listen', mock.Mock())
    def test_allocate_network_ports(self):
        """Test allocate network ports"""
        manifest = {
            'type': 'native',
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
                {'name': 'http', 'port': 8000},
                {'name': 'port0', 'port': 0}
            ],
            'ephemeral_ports': {},
            'cpu': '100%'
        }

        treadmill.runtime.allocate_network_ports('0.0.0.0', manifest)
        socket.socket.bind.assert_called_with(mock.ANY)
        socket.socket.listen.assert_called_with(0)


if __name__ == '__main__':
    unittest.main()
