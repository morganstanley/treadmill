"""Unit test for Treadmill linux runtime presence module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import io
import shutil
import tempfile
import time
import unittest

import kazoo
import kazoo.client
import mock

import treadmill
from treadmill import exc
from treadmill import presence

from treadmill.tests.testutils import mockzk


PROCCGROUPS = """#subsys_name	hierarchy	num_cgroups	enabled
cpuset	6	1	1
cpu	7	1	1
cpuacct	7	1	1
memory	4	1	1
devices	3	20	1
freezer	8	1	1
net_cls	2	1	1
blkio	10	1	1
perf_event	11	1	1
hugetlb	9	1	1
pids	5	1	1
net_prio	2	1	1"""

# pylint: disable=C0301
PROCMOUNTS = """rootfs / rootfs rw 0 0
sysfs /sys sysfs rw,seclabel,nosuid,nodev,noexec,relatime 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
devtmpfs /dev devtmpfs rw,seclabel,nosuid,size=239696k,nr_inodes=59924,mode=755 0 0
securityfs /sys/kernel/security securityfs rw,nosuid,nodev,noexec,relatime 0 0
tmpfs /dev/shm tmpfs rw,seclabel,nosuid,nodev 0 0
devpts /dev/pts devpts rw,seclabel,nosuid,noexec,relatime,gid=5,mode=620,ptmxmode=000 0 0
tmpfs /run tmpfs rw,seclabel,nosuid,nodev,mode=755 0 0
tmpfs /sys/fs/cgroup tmpfs ro,seclabel,nosuid,nodev,noexec,mode=755 0 0
cgroup /sys/fs/cgroup/systemd cgroup rw,nosuid,nodev,noexec,relatime,xattr,release_agent=/usr/lib/systemd/systemd-cgroups-agent,name=systemd 0 0
pstore /sys/fs/pstore pstore rw,nosuid,nodev,noexec,relatime 0 0
cgroup /sys/fs/cgroup/net_cls,net_prio cgroup rw,nosuid,nodev,noexec,relatime,net_prio,net_cls 0 0
cgroup /sys/fs/cgroup/devices cgroup rw,nosuid,nodev,noexec,relatime,devices 0 0
cgroup /sys/fs/cgroup/memory cgroup rw,nosuid,nodev,noexec,relatime,memory 0 0
cgroup /sys/fs/cgroup/pids cgroup rw,nosuid,nodev,noexec,relatime,pids 0 0
cgroup /sys/fs/cgroup/cpuset cgroup rw,nosuid,nodev,noexec,relatime,cpuset 0 0
cgroup /sys/fs/cgroup/cpu,cpuacct cgroup rw,nosuid,nodev,noexec,relatime,cpuacct,cpu 0 0
cgroup /sys/fs/cgroup/freezer cgroup rw,nosuid,nodev,noexec,relatime,freezer 0 0
cgroup /sys/fs/cgroup/hugetlb cgroup rw,nosuid,nodev,noexec,relatime,hugetlb 0 0
cgroup /sys/fs/cgroup/blkio cgroup rw,nosuid,nodev,noexec,relatime,blkio 0 0
cgroup /sys/fs/cgroup/perf_event cgroup rw,nosuid,nodev,noexec,relatime,perf_event 0 0
configfs /sys/kernel/config configfs rw,relatime 0 0
/dev/mapper/VolGroup00-LogVol00 / xfs rw,seclabel,relatime,attr2,inode64,noquota 0 0
selinuxfs /sys/fs/selinux selinuxfs rw,relatime 0 0
systemd-1 /proc/sys/fs/binfmt_misc autofs rw,relatime,fd=33,pgrp=1,timeout=300,minproto=5,maxproto=5,direct 0 0
debugfs /sys/kernel/debug debugfs rw,relatime 0 0
mqueue /dev/mqueue mqueue rw,seclabel,relatime 0 0
hugetlbfs /dev/hugepages hugetlbfs rw,seclabel,relatime 0 0
sunrpc /var/lib/nfs/rpc_pipefs rpc_pipefs rw,relatime 0 0
nfsd /proc/fs/nfsd nfsd rw,relatime 0 0
/dev/sda2 /boot xfs rw,seclabel,relatime,attr2,inode64,noquota 0 0
vagrant /vagrant vboxsf rw,nodev,relatime 0 0
home_centos_treadmill /home/centos/treadmill vboxsf rw,nodev,relatime 0 0
home_centos_treadmill-pid1 /home/centos/treadmill-pid1 vboxsf rw,nodev,relatime 0 0
tmpfs /run/user/1000 tmpfs rw,seclabel,nosuid,nodev,relatime,size=50040k,mode=700,uid=1000,gid=1000 0 0"""  # noqa: E501

_ORIGINAL_OPEN = open


def _open_side_effect(path, *args):
    if path == '/proc/mounts':
        return io.StringIO(PROCMOUNTS)
    elif path == '/proc/cgroups':
        return io.StringIO(PROCCGROUPS)
    else:
        return _ORIGINAL_OPEN(path, *args)


class PresenceTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.presence."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.events_dir = os.path.join(self.root, 'appevents')
        os.mkdir(self.events_dir)
        self.zkclient = treadmill.zkutils.ZkClient()
        super(PresenceTest, self).setUp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('time.sleep', mock.Mock)
    def test_registration(self):
        """Verifies presence registration."""
        treadmill.sysinfo.hostname.return_value = 'myhostname'
        manifest = {
            'task': 't-0001',
            'name': 'foo.test1',
            'uniqueid': 'AAAAAA',
            'proid': 'andreik',
            'services': [
                {
                    'command': '/usr/bin/python -m SimpleHTTPServer',
                    'name': 'web_server',
                    'restart': {
                        'interval': 60,
                        'limit': 3
                    }
                },
                {
                    'command': '/usr/bin/python -m SimpleHTTPServer',
                    'name': 'another_server'
                },
                {
                    'command': 'sshd -D -f /etc/ssh/sshd_config',
                    'name': 'sshd',
                    'proid': None
                }
            ],
            'endpoints': [
                {
                    'port': 22,
                    'name': 'ssh',
                    'real_port': 5001,
                },
                {
                    'port': 8000,
                    'name': 'http',
                    'real_port': 5000,
                }
            ]
        }
        app_presence = presence.EndpointPresence(self.zkclient, manifest)
        app_presence.register_endpoints()
        kazoo.client.KazooClient.create.assert_has_calls(
            [
                mock.call(
                    '/endpoints/foo/test1:tcp:ssh',
                    value=b'myhostname:5001',
                    acl=mock.ANY,
                    ephemeral=True, makepath=True, sequence=False
                ),
                mock.call(
                    '/endpoints/foo/test1:tcp:http',
                    value=b'myhostname:5000',
                    acl=mock.ANY,
                    ephemeral=True, makepath=True, sequence=False
                ),
            ]
        )

        retry_happened = []

        def node_exists(*_args, **_kwargs):
            """Simulate existence of ephemeral node."""
            if retry_happened:
                return
            else:
                retry_happened.append(1)
                raise kazoo.client.NodeExistsError()

        kazoo.client.KazooClient.create.reset()
        kazoo.client.KazooClient.create.side_effect = node_exists
        kazoo.client.KazooClient.get.return_value = ('{}', {})
        app_presence.register_endpoints()
        self.assertTrue(retry_happened)
        self.assertTrue(time.sleep.called)
        kazoo.client.KazooClient.create.assert_has_calls(
            [
                mock.call(
                    '/endpoints/foo/test1:tcp:ssh',
                    value=b'myhostname:5001',
                    acl=mock.ANY,
                    ephemeral=True, makepath=True, sequence=False
                ),
                mock.call(
                    '/endpoints/foo/test1:tcp:http',
                    value=b'myhostname:5000',
                    acl=mock.ANY,
                    ephemeral=True, makepath=True, sequence=False
                ),
            ]
        )

        kazoo.client.KazooClient.create.reset()
        kazoo.client.KazooClient.create.side_effect = (
            kazoo.client.NodeExistsError
        )
        self.assertRaises(exc.ContainerSetupError,
                          app_presence.register_endpoints)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_kill(self):
        """Checks removal of the endpoints."""
        zk_content = {
            'running': {
                'myproid.aaa': b'xxx.xx.com',
                'myproid.bbb': b'yyy.xx.com'
            },
            'endpoints': {
                'myproid': {
                    'aaa:tcp:http': b'xxx.xx.com:1234',
                    'bbb:tcp:http': b'yyy.xx.com:1234',
                },
            },
            'servers': {
                'xxx.xx.com': {},
            },
            'server.presence': {
                'xxx.xx.com': {},
            },
            'placement': {
                'xxx.xx.com': {
                    'myproid.aaa': {},
                    'myproid.bbb': {},
                }
            },
            'scheduled': {
                'myproid.aaa': {
                    'endpoints': [{'name': 'http', 'port': 8888}],
                },
                'myproid.bbb': {
                    'endpoints': [{'name': 'http', 'port': 8888}],
                },
            }
        }
        self.make_mock_zk(zk_content)
        presence.kill_node(self.zkclient, 'xxx.xx.com')

        # aaa running node is removed.
        self.assertNotIn('myproid.aaa', zk_content['running'])
        # bbb is not removed, as 'running' node has different hostname.
        self.assertIn('myproid.bbb', zk_content['running'])

        # Same for endpoints - aaa is removed, bbb is not.
        self.assertNotIn('aaa:tcp:http', zk_content['endpoints']['myproid'])
        self.assertIn('bbb:tcp:http', zk_content['endpoints']['myproid'])

        self.assertNotIn('xxx.xx.com', zk_content['server.presence'])

    def test_server_node(self):
        """Test returning server.presence node for hostname and presence_id."""
        self.assertEqual(
            presence.server_node('xxx.xx.com', '-1'),
            'xxx.xx.com'
        )

        self.assertEqual(
            presence.server_node('yyy.yy.com', '12345'),
            'yyy.yy.com#12345'
        )

    def test_parse_server(self):
        """Test returning hostname and presence_id for server.presence node."""
        self.assertEqual(
            presence.parse_server('xxx.xx.com'),
            ('xxx.xx.com', '-1')
        )

        self.assertEqual(
            presence.parse_server('yyy.yy.com#12345'),
            ('yyy.yy.com', '12345')
        )

    def test_server_hostname(self):
        """Test returning hostname for given server.presence node."""
        self.assertEqual(presence.server_hostname('xxx.xx.com'), 'xxx.xx.com')

        self.assertEqual(
            presence.server_hostname('yyy.yy.com#12345'),
            'yyy.yy.com'
        )

    def test_find_server(self):
        """Test finding server."""
        zkclient_mock = mock.Mock()
        zkclient_mock.get_children.return_value = [
            'yyy.yy.com#12345', 'zzz.zz.com'
        ]

        self.assertEqual(
            presence.find_server(zkclient_mock, 'xxx.xx.com'),
            None
        )

        self.assertEqual(
            presence.find_server(zkclient_mock, 'yyy.yy.com'),
            '/server.presence/yyy.yy.com#12345'
        )

        self.assertEqual(
            presence.find_server(zkclient_mock, 'zzz.zz.com'),
            '/server.presence/zzz.zz.com'
        )

    def test_register_server(self):
        """Test registering server."""
        zkclient_mock = mock.Mock()
        zkclient_mock.get.return_value = (b"{parent: 'rack:test123'}\n", None)
        zkclient_mock.create.return_value = '/server.presence/xxx.xx.com#12345'

        server_presence_path = presence.register_server(
            zkclient_mock, 'xxx.xx.com', {'up_since': '123.45'}
        )

        self.assertEqual(
            server_presence_path,
            '/server.presence/xxx.xx.com#12345'
        )
        zkclient_mock.set.assert_called_once_with(
            '/servers/xxx.xx.com',
            b"{parent: 'rack:test123', up_since: '123.45'}\n"
        )
        zkclient_mock.create.assert_called_once_with(
            '/server.presence/xxx.xx.com#',
            b'{seen: false}\n',
            acl=mock.ANY, ephemeral=True, makepath=True, sequence=True
        )

    def test_unregister_server(self):
        """Test unregistering server."""
        zkclient_mock = mock.Mock()
        zkclient_mock.get_children.side_effect = lambda path: {
            '/server.presence': ['yyy.yy.com#12345', 'zzz.zz.com']
        }.get(path, [])

        presence.unregister_server(zkclient_mock, 'xxx.xx.com')
        zkclient_mock.delete.assert_not_called()

        presence.unregister_server(zkclient_mock, 'yyy.yy.com')
        zkclient_mock.delete.assert_called_with(
            '/server.presence/yyy.yy.com#12345'
        )

        presence.unregister_server(zkclient_mock, 'zzz.zz.com')
        zkclient_mock.delete.assert_called_with('/server.presence/zzz.zz.com')


if __name__ == '__main__':
    unittest.main()
