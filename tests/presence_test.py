"""
Unit test for Treadmill presense module.
"""

import os
import io
import shutil
import tempfile
import time
import unittest

import mock
import kazoo
import kazoo.client
import yaml

import treadmill
from treadmill import exc
from treadmill import presence
from treadmill.apptrace import events
from treadmill.test import mockzk

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

original_open = open


def _open_side_effect(path, *args):
    if path == '/proc/mounts':
        return io.StringIO(PROCMOUNTS)
    elif path == '/proc/cgroups':
        return io.StringIO(PROCCGROUPS)
    else:
        return original_open(path, *args)


class PresenceTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.presence."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.events_dir = os.path.join(self.root, 'appevents')
        os.mkdir(self.events_dir)
        self.zkclient = kazoo.client.KazooClient()
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
            'vip': {
                'ip0': '192.168.0.1',
                'ip1': '192.168.0.2'
            },
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
        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call('/endpoints/foo/test1:tcp:ssh', 'myhostname:5001',
                      ephemeral=True, makepath=True, acl=mock.ANY,
                      sequence=False),
            mock.call('/endpoints/foo/test1:tcp:http', 'myhostname:5000',
                      ephemeral=True, makepath=True, acl=mock.ANY,
                      sequence=False),

        ])

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
        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call('/endpoints/foo/test1:tcp:ssh', 'myhostname:5001',
                      ephemeral=True, makepath=True, acl=mock.ANY,
                      sequence=False),
            mock.call('/endpoints/foo/test1:tcp:http', 'myhostname:5000',
                      ephemeral=True, makepath=True, acl=mock.ANY,
                      sequence=False),

        ])

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
                'myproid.aaa': 'xxx.xx.com',
                'myproid.bbb': 'yyy.xx.com'
            },
            'endpoints': {
                'myproid': {
                    'aaa:tcp:http': 'xxx.xx.com:1234',
                    'bbb:tcp:http': 'yyy.xx.com:1234',
                },
            },
            'servers': {
                'xxx.xx.com': {},
            },
            'server.presence': {
                'xxx.xx.com': {},
            },
            'placement': {
                'xxx.xx.com':  {
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

    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.presence.ServicePresence.report_running',
                mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=0))
    @mock.patch('builtins.open', mock.Mock(side_effect=_open_side_effect))
    def test_start_service(self):
        """Verifies restart/finish file interaction."""
        manifest = {
            'vip': {
                'ip0': '192.168.0.1',
                'ip1': '192.168.0.2'
            },
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
                    'command': 'sshd -D -f /etc/ssh/sshd_config',
                    'name': 'sshd',
                    'restart': {
                        'interval': 60,
                        'limit': 3
                    },
                    'proid': None
                }
            ],
            'endpoints': [
                {
                    'port': 22,
                    'name': 'ssh',
                    'real_port': 5001
                },
                {
                    'port': 8000,
                    'name': 'http',
                    'real_port': 5000
                }
            ]
        }
        app_presence = presence.ServicePresence(
            manifest,
            container_dir=self.root,
            appevents_dir=self.events_dir
        )

        self.assertTrue(app_presence.start_service('web_server'))
        os.mkdir(os.path.join(self.root, 'services'))
        os.mkdir(os.path.join(self.root, 'services', 'web_server'))
        finished_file = os.path.join(self.root, 'services', 'web_server',
                                     'finished')
        # App will be restarted, since it exits outside of its interval.
        time.time.return_value = 1001
        with open(finished_file, 'a+') as f:
            f.write('1000 1 0\n')
        self.assertTrue(app_presence.start_service('web_server'))

        time.time.return_value = 2001
        with open(finished_file, 'a+') as f:
            f.write('2000 1 0\n')
        self.assertTrue(app_presence.start_service('web_server'))

        time.time.return_value = 3001
        with open(finished_file, 'a+') as f:
            f.write('3000 1 0\n')
        self.assertTrue(app_presence.start_service('web_server'))

        time.time.return_value = 4001
        with open(finished_file, 'a+') as f:
            f.write('4000 1 0\n')
        self.assertTrue(app_presence.start_service('web_server'))

    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    def test_report_running(self):
        """Verifies report running sequence."""
        manifest = {
            'vip': {
                'ip0': '192.168.0.1',
                'ip1': '192.168.0.2'
            },
            'task': 't-0001',
            'name': 'foo.test1#0001',
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
                    'command': 'sshd -D -f /etc/ssh/sshd_config',
                    'name': 'sshd',
                    'proid': None
                }
            ],
            'endpoints': [
                {
                    'port': 22,
                    'name': 'ssh',
                    'real_port': 5001
                },
                {
                    'port': 8000,
                    'name': 'http',
                    'real_port': 5000
                }
            ]
        }
        treadmill.sysinfo.hostname.return_value = 'server1.xx.com'
        app_presence = presence.ServicePresence(
            manifest,
            container_dir=self.root,
            appevents_dir=self.events_dir
        )

        kazoo.client.KazooClient.exists.return_value = False
        app_presence.report_running('web_server')
        treadmill.appevents.post.assert_called_with(
            self.events_dir,
            events.ServiceRunningTraceEvent(
                instanceid='foo.test1#0001',
                uniqueid='AAAAAA',
                service='web_server'
            )
        )

        kazoo.client.KazooClient.exists.return_value = True
        app_presence.report_running('web_server')
        treadmill.appevents.post.assert_called_with(
            self.events_dir,
            events.ServiceRunningTraceEvent(
                instanceid='foo.test1#0001',
                uniqueid='AAAAAA',
                service='web_server'
            )
        )

    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname', mock.Mock())
    @mock.patch('treadmill.subproc.call', mock.Mock())
    @mock.patch('builtins.open', mock.Mock(side_effect=_open_side_effect))
    def test_app_exit(self):
        """Verifies app deletion on service exit."""
        manifest = {
            'vip': {
                'ip0': '192.168.0.1',
                'ip1': '192.168.0.2'
            },
            'task': 't-0001',
            'name': 'foo.test1#0001',
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
                    'command': 'sshd -D -f /etc/ssh/sshd_config',
                    'name': 'sshd',
                    'proid': None
                }
            ],
            'endpoints': [
                {
                    'port': 22,
                    'name': 'ssh',
                    'real_port': 5001
                },
                {
                    'port': 8000,
                    'name': 'http',
                    'real_port': 5000
                }
            ]
        }
        services_dir = os.path.join(self.root, 'services')
        os.mkdir(services_dir)

        treadmill.sysinfo.hostname.return_value = 'server1.xx.com'
        app_presence = presence.ServicePresence(
            manifest,
            container_dir=self.root,
            appevents_dir=self.events_dir
        )
        app_presence.services['web_server']['last_exit'] = {
            'rc': 1,
            'sig': 3,
        }
        app_presence.exit_app('web_server')

        self.assertTrue(os.path.exists(os.path.join(self.root, 'exitinfo')))
        self.assertEqual(
            yaml.load(open(os.path.join(self.root, 'exitinfo')).read()),
            {'rc': 1,
             'sig': 3,
             'service': 'web_server',
             'killed': False,
             'oom': False}
        )

        del app_presence.services['web_server']['last_exit']
        app_presence.exit_app('web_server')
        self.assertTrue(os.path.exists(os.path.join(self.root, 'exitinfo')))
        self.assertEqual(
            yaml.load(open(os.path.join(self.root, 'exitinfo')).read()),
            {'service': 'web_server',
             'killed': False,
             'oom': False}
        )

    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=100))
    @mock.patch('builtins.open', mock.Mock(side_effect=_open_side_effect))
    def test_update_exit_status(self):
        """Verifies reading the finished file and updating task status."""
        manifest = {
            'vip': {
                'ip0': '192.168.0.1',
                'ip1': '192.168.0.2'
            },
            'task': 't-0001',
            'name': 'foo.test1#0001',
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
                    'command': 'sshd -D -f /etc/ssh/sshd_config',
                    'name': 'sshd',
                    'proid': None
                }
            ],
            'endpoints': [
                {
                    'port': 22,
                    'name': 'ssh',
                    'real_port': 5001
                },
                {
                    'port': 8000,
                    'name': 'http',
                    'real_port': 5000
                }
            ]
        }
        treadmill.sysinfo.hostname.return_value = 'server1.xx.com'
        app_presence = presence.ServicePresence(manifest,
                                                container_dir=self.root,
                                                appevents_dir=self.events_dir)

        os.mkdir(os.path.join(self.root, 'services'))
        os.mkdir(os.path.join(self.root, 'services', 'web_server'))
        finished_file = os.path.join(self.root, 'services', 'web_server',
                                     'finished')
        with open(finished_file, 'a+') as f:
            f.write('1000 1 0\n')
        app_presence.update_exit_status('web_server')
        treadmill.appevents.post.assert_called_with(
            self.events_dir,
            events.ServiceExitedTraceEvent(
                instanceid='foo.test1#0001',
                uniqueid='AAAAAA',
                service='web_server',
                rc=1,
                signal=0
            )
        )

        kazoo.client.KazooClient.create.reset_mock()
        with open(finished_file, 'a+') as f:
            f.write('2000 9 255\n')
        app_presence.update_exit_status('web_server')
        treadmill.appevents.post.assert_called_with(
            self.events_dir,
            events.ServiceExitedTraceEvent(
                instanceid='foo.test1#0001',
                uniqueid='AAAAAA',
                service='web_server',
                rc=9,
                signal=255
            )
        )

        reported_file = os.path.join(self.root, 'services', 'web_server',
                                     'reported')
        self.assertTrue(os.path.exists(reported_file))

        # Calling update state twice is no-op, as reported file is newer.
        kazoo.client.KazooClient.create.reset_mock()
        app_presence.update_exit_status('web_server')
        self.assertFalse(kazoo.client.KazooClient.create.called)

    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.presence.ServicePresence.report_running',
                mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=None))
    @mock.patch('builtins.open', mock.Mock(side_effect=_open_side_effect))
    def test_restart_rate(self):
        """Verifies reading the finished file and updating task status."""
        manifest = {
            'task': 't-0001',
            'name': 'foo.test1#0001',
            'uniqueid': 'AAAAAA',
            'proid': 'andreik',
            'services': [
                {
                    'command': '/usr/bin/python -m SimpleHTTPServer',
                    'name': 'web_server',
                    'restart': {
                        'interval': 60,
                        'limit': 5
                    }
                },
            ],
        }
        treadmill.sysinfo.hostname.return_value = 'server1.xx.com'
        app_presence = presence.ServicePresence(
            manifest,
            container_dir=self.root,
            appevents_dir=self.events_dir
        )

        os.mkdir(os.path.join(self.root, 'services'))
        os.mkdir(os.path.join(self.root, 'services', 'web_server'))
        finished_file = os.path.join(self.root, 'services', 'web_server',
                                     'finished')

        time.time.return_value = 1059
        # Five restarts in less than 60 sec, service should not be restarted
        with open(finished_file, 'w') as f:
            f.write('1000 1 0\n')
            f.write('1001 1 0\n')
            f.write('1002 1 0\n')
            f.write('1003 1 0\n')
            f.write('1059 1 0\n')

        self.assertFalse(app_presence.start_service('web_server'))

        # Fifth restart is 105 sec away, service should be restarted
        time.time.return_value = 1105
        with open(finished_file, 'w') as f:
            f.write('1000 1 0\n')
            f.write('1101 1 0\n')
            f.write('1102 1 0\n')
            f.write('1103 1 0\n')
            f.write('1104 1 0\n')

        self.assertTrue(app_presence.start_service('web_server'))

        time.time.return_value = 2000
        # Last restart in more than 30 sec, should be restarted
        manifest['services'][0]['restart'] = {'limit': 1, 'interval': 30}
        with open(finished_file, 'w') as f:
            f.write('1000 1 0\n')
            f.write('1950 1 0\n')

        self.assertTrue(app_presence.start_service('web_server'))

        # Last restart in less than 30 sec, should be *not* restarted
        with open(finished_file, 'w') as f:
            f.write('1000 1 0\n')
            f.write('1001 1 0\n')
            f.write('1980 1 0\n')

        self.assertFalse(app_presence.start_service('web_server'))

        # Confirm that limit: 0 does not allow *any* exit
        manifest['services'][0]['restart'] = {'limit': 0, 'interval': 60}
        time.time.return_value = 2000
        with open(finished_file, 'w') as f:
            f.write('1000 1 0\n')
            f.write('1001 1 0\n')
            f.write('1002 1 0\n')
            f.write('1003 1 0\n')
            f.write('1004 1 0\n')

        self.assertFalse(app_presence.start_service('web_server'))

    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('treadmill.cgroups.get_mountpoint',
                mock.Mock(return_value='/cgroups'))
    @mock.patch('treadmill.sysinfo.hostname', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_exit_info(self):
        """Tests collection of exit info."""
        manifest = {
            'vip': {
                'ip0': '192.168.0.1',
                'ip1': '192.168.0.2'
            },
            'task': 't-0001',
            'name': 'foo.test1#0001',
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
                    'command': 'sshd -D -f /etc/ssh/sshd_config',
                    'name': 'sshd',
                    'proid': None
                }
            ],
            'endpoints': [
                {
                    'port': 22,
                    'name': 'ssh',
                    'real_port': 5001
                },
                {
                    'port': 8000,
                    'name': 'http',
                    'real_port': 5000
                }
            ]
        }

        os.mkdir(os.path.join(self.root, 'services'))
        os.mkdir(os.path.join(self.root, 'services', 'web_server'))
        finished_file = os.path.join(self.root, 'services', 'web_server',
                                     'finished')

        with open(finished_file, 'a+') as f:
            f.write('1000 1 0\n')
        app_presence = presence.ServicePresence(
            manifest,
            container_dir=self.root,
            appevents_dir=self.events_dir
        )
        ws_svc_dir = os.path.join(self.root, 'services', 'web_server')
        einfo, count = app_presence.exit_info(ws_svc_dir)
        self.assertEqual(1, count)
        self.assertEqual(1, einfo['rc'])
        self.assertEqual(0, einfo['sig'])
        self.assertFalse(einfo['oom'])

        with open(finished_file, 'a+') as f:
            f.write('1001 255 9\n')
        einfo, count = app_presence.exit_info(ws_svc_dir)
        self.assertEqual(2, count)
        self.assertEqual(255, einfo['rc'])
        self.assertEqual(9, einfo['sig'])
        self.assertFalse(einfo['oom'])

        open_name = 'builtins.open'
        with mock.patch(open_name, mock.mock_open()) as mock_open:
            file_mock = mock.MagicMock(spec=io.IOBase)
            file_mock.__enter__.return_value.read.return_value = '1'
            mock_open.return_value = file_mock
            self.assertTrue(presence.is_oom())


if __name__ == '__main__':
    unittest.main()
