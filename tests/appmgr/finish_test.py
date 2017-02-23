"""
Unit test for treadmill.appmgr.finish.
"""

import datetime
import os
import shutil
import tempfile
import tarfile
import time
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import kazoo
import mock
import yaml

import treadmill
from treadmill import firewall
from treadmill import fs
from treadmill import utils
from treadmill.apptrace import events
from treadmill.appmgr import finish as app_finish


class AppMgrFinishTest(unittest.TestCase):
    """Tests for teadmill.appmgr.finish"""

    def setUp(self):
        # Access protected module _base_service
        # pylint: disable=W0212
        self.root = tempfile.mkdtemp()
        self.app_env = mock.Mock(
            root=self.root,
            host_ip='172.31.81.67',
            # nfs_dir=os.path.join(self.root, 'mnt', 'nfs'),
            apps_dir=os.path.join(self.root, 'apps'),
            archives_dir=os.path.join(self.root, 'archives'),
            metrics_dir=os.path.join(self.root, 'metrics'),
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
            watchdogs=mock.Mock(
                spec_set=treadmill.watchdog.Watchdog,
            ),
        )

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('kazoo.client.KazooClient', mock.Mock(set_spec=True))
    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    @mock.patch('treadmill.utils.datetime_utcnow', mock.Mock(
        return_value=datetime.datetime(2015, 1, 22, 14, 14, 36, 537918)))
    @mock.patch('treadmill.appmgr.manifest.read', mock.Mock())
    @mock.patch('treadmill.appmgr.finish._kill_apps_by_root', mock.Mock())
    @mock.patch('treadmill.appmgr.finish._send_container_archive', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='xxx.xx.com'))
    @mock.patch('treadmill.fs.archive_filesystem',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.rrdutils.flush_noexc', mock.Mock())
    @mock.patch('treadmill.subproc.call', mock.Mock(return_value=0))
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.subproc.invoke', mock.Mock())
    @mock.patch('treadmill.zkutils.get',
                mock.Mock(return_value={
                    'server': 'nonexist',
                    'auth': 'nonexist',
                }))
    def test_finish(self):
        """Tests container finish procedure and freeing of the resources.
        """
        # Access protected module _kill_apps_by_root
        # pylint: disable=W0212
        manifest = {
            'app': 'proid.myapp',
            'cell': 'test',
            'cpu': '100%',
            'disk': '100G',
            'environment': 'dev',
            'host_ip': '172.31.81.67',
            'memory': '100M',
            'name': 'proid.myapp#001',
            'proid': 'foo',
            'shared_network': False,
            'task': '001',
            'uniqueid': '0000000ID1234',
            'archive': [
                '/var/tmp/treadmill'
            ],
            'endpoints': [
                {
                    'port': 8000,
                    'name': 'http',
                    'real_port': 5000,
                    'proto': 'tcp',
                },
                {
                    'port': 54321,
                    'type': 'infra',
                    'name': 'ssh',
                    'real_port': 54321,
                    'proto': 'tcp',
                }
            ],
            'ephemeral_ports': {
                'tcp': [45024],
                'udp': [62422],
            },
            'services': [
                {
                    'name': 'web_server',
                    'command': '/bin/false',
                    'restart': {
                        'limit': 3,
                        'interval': 60,
                    },
                }
            ],
        }
        treadmill.appmgr.manifest.read.return_value = manifest
        app_unique_name = 'proid.myapp-001-0000000ID1234'
        mock_cgroup_client = self.app_env.svc_cgroup.make_client.return_value
        mock_ld_client = self.app_env.svc_localdisk.make_client.return_value
        mock_nwrk_client = self.app_env.svc_network.make_client.return_value
        localdisk = {
            'block_dev': '/dev/foo',
        }
        mock_ld_client.get.return_value = localdisk
        network = {
            'vip': '192.168.0.2',
            'gateway': '192.168.254.254',
            'veth': 'testveth.0',
        }
        mock_nwrk_client.get.return_value = network
        app_dir = os.path.join(self.app_env.apps_dir, app_unique_name)
        # Create content in app root directory, verify that it is archived.
        fs.mkdir_safe(os.path.join(app_dir, 'root', 'xxx'))
        fs.mkdir_safe(os.path.join(app_dir, 'services'))
        # Simulate daemontools finish script, marking the app is done.
        with open(os.path.join(app_dir, 'exitinfo'), 'w') as f:
            f.write(yaml.dump({'service': 'web_server', 'rc': 0, 'sig': 0}))
        mock_zkclient = kazoo.client.KazooClient()

        app_finish.finish(self.app_env, mock_zkclient, app_dir)

        self.app_env.watchdogs.create.assert_called_with(
            'treadmill.appmgr.finish-' + app_unique_name,
            '5m',
            mock.ANY
        )
        treadmill.subproc.check_call.assert_has_calls(
            [
                mock.call(
                    [
                        's6-svc',
                        '-d',
                        app_dir,
                    ]
                ),
                mock.call(
                    [
                        's6-svwait',
                        '-d',
                        app_dir,
                    ]
                ),
            ]
        )
        # All resource service clients are properly created
        self.app_env.svc_cgroup.make_client.assert_called_with(
            os.path.join(app_dir, 'cgroups')
        )
        self.app_env.svc_localdisk.make_client.assert_called_with(
            os.path.join(app_dir, 'localdisk')
        )
        self.app_env.svc_network.make_client.assert_called_with(
            os.path.join(app_dir, 'network')
        )

        treadmill.appmgr.finish._kill_apps_by_root.assert_called_with(
            os.path.join(app_dir, 'root')
        )

        # Verify that we tested the archiving for the app root volume
        treadmill.fs.archive_filesystem.assert_called_with(
            '/dev/foo',
            os.path.join(app_dir, 'root'),
            os.path.join(app_dir,
                         '001_xxx.xx.com_20150122_141436537918.tar'),
            mock.ANY
        )
        # Verify that the file is uploaded by Uploader
        app = utils.to_obj(manifest)
        treadmill.appmgr.finish._send_container_archive.assert_called_with(
            mock_zkclient,
            app,
            os.path.join(app_dir,
                         '001_xxx.xx.com_20150122_141436537918.tar.gz'),
        )
        # Verify that the app folder was deleted
        self.assertFalse(os.path.exists(app_dir))
        # Cleanup the block device
        mock_ld_client.delete.assert_called_with(app_unique_name)
        # Cleanup the cgroup resource
        mock_cgroup_client.delete.assert_called_with(app_unique_name)
        # Cleanup network resources
        mock_nwrk_client.get.assert_called_with(app_unique_name)
        self.app_env.rules.unlink_rule.assert_has_calls([
            mock.call(rule=firewall.DNATRule('tcp',
                                             '172.31.81.67', 5000,
                                             '192.168.0.2', 8000),
                      owner=app_unique_name),
            mock.call(rule=firewall.DNATRule('tcp',
                                             '172.31.81.67', 54321,
                                             '192.168.0.2', 54321),
                      owner=app_unique_name),
            mock.call(rule=firewall.DNATRule('tcp',
                                             '172.31.81.67', 45024,
                                             '192.168.0.2', 45024),
                      owner=app_unique_name),
            mock.call(rule=firewall.DNATRule('udp',
                                             '172.31.81.67', 62422,
                                             '192.168.0.2', 62422),
                      owner=app_unique_name),
        ])
        treadmill.iptables.rm_ip_set.assert_has_calls(
            [
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.0.2,tcp:54321'),
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.0.2,tcp:45024'),
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.0.2,udp:62422'),
            ]
        )
        mock_nwrk_client.delete.assert_called_with(app_unique_name)
        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            events.FinishedTraceEvent(
                instanceid='proid.myapp#001',
                rc=0,
                signal=0,
                payload={
                    'service': 'web_server',
                    'sig': 0,
                    'rc': 0
                }
            )
        )
        treadmill.rrdutils.flush_noexc.assert_called_with(
            os.path.join(self.root, 'metrics', 'apps',
                         app_unique_name + '.rrd')
        )
        shutil.copy.assert_called_with(
            os.path.join(self.root, 'metrics', 'apps',
                         app_unique_name + '.rrd'),
            os.path.join(app_dir, 'metrics.rrd')
        )

    @mock.patch('kazoo.client.KazooClient', mock.Mock(set_spec=True))
    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    @mock.patch('treadmill.appmgr.finish._kill_apps_by_root', mock.Mock())
    @mock.patch('treadmill.appmgr.manifest.read', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='myhostname'))
    @mock.patch('treadmill.cgroups.delete', mock.Mock())
    @mock.patch('treadmill.cgutils.reset_memory_limit_in_bytes',
                mock.Mock(return_value=[]))
    @mock.patch('treadmill.fs.archive_filesystem',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.subproc.call', mock.Mock(return_value=0))
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.subproc.invoke', mock.Mock())
    @mock.patch('treadmill.zkutils.get', mock.Mock(return_value=None))
    @mock.patch('treadmill.rrdutils.flush_noexc', mock.Mock())
    def test_finish_error(self):
        """Tests container finish procedure when app is improperly finished."""
        manifest = {
            'app': 'proid.myapp',
            'cell': 'test',
            'cpu': '100%',
            'disk': '100G',
            'environment': 'dev',
            'host_ip': '172.31.81.67',
            'memory': '100M',
            'name': 'proid.myapp#001',
            'proid': 'foo',
            'shared_network': False,
            'task': '001',
            'uniqueid': '0000000001234',
            'archive': [
                '/var/tmp/treadmill'
            ],
            'endpoints': [
                {
                    'port': 8000,
                    'name': 'http',
                    'real_port': 5000,
                    'proto': 'tcp',
                }
            ],
            'services': [
                {
                    'name': 'web_server',
                    'command': '/bin/false',
                    'restart': {
                        'limit': 3,
                        'interval': 60,
                    },
                }
            ],
            'ephemeral_ports': {
                'tcp': [],
                'udp': [],
            }
        }
        treadmill.appmgr.manifest.read.return_value = manifest
        app_unique_name = 'proid.myapp-001-0000000001234'
        mock_ld_client = self.app_env.svc_localdisk.make_client.return_value
        localdisk = {
            'block_dev': '/dev/foo',
        }
        mock_ld_client.get.return_value = localdisk
        mock_nwrk_client = self.app_env.svc_network.make_client.return_value
        network = {
            'vip': '192.168.0.2',
            'gateway': '192.168.254.254',
            'veth': 'testveth.0',
        }
        mock_nwrk_client.get.return_value = network
        app_dir = os.path.join(self.app_env.apps_dir, app_unique_name)
        # Create content in app root directory, verify that it is archived.
        fs.mkdir_safe(os.path.join(app_dir, 'root', 'xxx'))
        fs.mkdir_safe(os.path.join(app_dir, 'services'))
        # Simulate daemontools finish script, marking the app is done.
        with open(os.path.join(app_dir, 'exitinfo'), 'w') as f:
            f.write(yaml.dump({'service': 'web_server', 'rc': 1, 'sig': 3}))
        mock_zkclient = kazoo.client.KazooClient()

        app_finish.finish(
            self.app_env, mock_zkclient, app_dir
        )

        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            events.FinishedTraceEvent(
                instanceid='proid.myapp#001',
                rc=1,
                signal=3,
                payload={
                    'service': 'web_server',
                    'sig': 3,
                    'rc': 1,
                }
            )
        )
        treadmill.rrdutils.flush_noexc.assert_called_with(
            os.path.join(self.root, 'metrics', 'apps',
                         app_unique_name + '.rrd')
        )
        shutil.copy.assert_called_with(
            os.path.join(self.app_env.metrics_dir, 'apps',
                         app_unique_name + '.rrd'),
            os.path.join(app_dir, 'metrics.rrd')
        )

    @mock.patch('kazoo.client.KazooClient', mock.Mock(set_spec=True))
    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    @mock.patch('treadmill.appmgr.manifest.read', mock.Mock())
    @mock.patch('treadmill.appmgr.finish._kill_apps_by_root', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='hostname'))
    @mock.patch('treadmill.fs.archive_filesystem',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.rulefile.RuleMgr.unlink_rule', mock.Mock())
    @mock.patch('treadmill.subproc.call', mock.Mock(return_value=0))
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.subproc.invoke', mock.Mock())
    @mock.patch('treadmill.zkutils.get', mock.Mock(return_value=None))
    @mock.patch('treadmill.rrdutils.flush_noexc', mock.Mock())
    def test_finish_aborted(self):
        """Tests container finish procedure when node is aborted.
        """
        manifest = {
            'app': 'proid.myapp',
            'cell': 'test',
            'cpu': '100%',
            'disk': '100G',
            'environment': 'dev',
            'host_ip': '172.31.81.67',
            'memory': '100M',
            'name': 'proid.myapp#001',
            'proid': 'foo',
            'shared_network': False,
            'task': '001',
            'uniqueid': '0000000ID1234',
            'archive': [
                '/var/tmp/treadmill'
            ],
            'endpoints': [
                {
                    'port': 8000,
                    'name': 'http',
                    'real_port': 5000,
                    'proto': 'tcp',
                }
            ],
            'services': [
                {
                    'name': 'web_server',
                    'command': '/bin/false',
                    'restart': {
                        'limit': 3,
                        'interval': 60,
                    },
                }
            ],
            'ephemeral_ports': {
                'tcp': [],
                'udp': [],
            }
        }
        treadmill.appmgr.manifest.read.return_value = manifest
        app_unique_name = 'proid.myapp-001-0000000ID1234'
        mock_ld_client = self.app_env.svc_localdisk.make_client.return_value
        localdisk = {
            'block_dev': '/dev/foo',
        }
        mock_ld_client.get.return_value = localdisk
        mock_nwrk_client = self.app_env.svc_network.make_client.return_value
        network = {
            'vip': '192.168.0.2',
            'gateway': '192.168.254.254',
            'veth': 'testveth.0',
        }
        mock_nwrk_client.get.return_value = network
        app_dir = os.path.join(self.root, 'apps', app_unique_name)
        # Create content in app root directory, verify that it is archived.
        fs.mkdir_safe(os.path.join(app_dir, 'root', 'xxx'))
        fs.mkdir_safe(os.path.join(app_dir, 'services'))
        # Simulate daemontools finish script, marking the app is done.
        with open(os.path.join(app_dir, 'aborted'), 'w') as aborted:
            aborted.write('something went wrong')
        mock_zkclient = kazoo.client.KazooClient()

        app_finish.finish(
            self.app_env, mock_zkclient, app_dir
        )

        treadmill.appevents.post(
            mock.ANY,
            events.AbortedTraceEvent(
                instanceid='proid.myapp#001',
                why=None,
                payload={
                    'why': 'something went wrong',
                    'node': 'hostname',
                }
            )
        )
        treadmill.rrdutils.flush_noexc.assert_called_with(
            os.path.join(self.root, 'metrics', 'apps',
                         app_unique_name + '.rrd')
        )
        shutil.copy.assert_called_with(
            os.path.join(self.root, 'metrics', 'apps',
                         app_unique_name + '.rrd'),
            os.path.join(app_dir, 'metrics.rrd')
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(return_value=0))
    def test_finish_no_manifest(self):
        """Test app finish on directory with no app.yml.
        """
        app_finish.finish(self.app_env, None, self.root)

    @mock.patch('kazoo.client.KazooClient', mock.Mock(set_spec=True))
    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    @mock.patch('treadmill.utils.datetime_utcnow', mock.Mock(
        return_value=datetime.datetime(2015, 1, 22, 14, 14, 36, 537918)))
    @mock.patch('treadmill.appmgr.manifest.read', mock.Mock())
    @mock.patch('treadmill.appmgr.finish._kill_apps_by_root', mock.Mock())
    @mock.patch('treadmill.appmgr.finish._send_container_archive', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='xxx.ms.com'))
    @mock.patch('treadmill.fs.archive_filesystem',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.rrdutils.flush_noexc', mock.Mock())
    @mock.patch('treadmill.subproc.call', mock.Mock(return_value=0))
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.subproc.invoke', mock.Mock())
    @mock.patch('treadmill.zkutils.get',
                mock.Mock(return_value={
                    'server': 'nonexist',
                    'auth': 'nonexist',
                }))
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    def test_finish_no_resources(self):
        """Test app finish on directory when all resources are already freed.
        """
        # Access protected module _kill_apps_by_root
        # pylint: disable=W0212
        manifest = {
            'app': 'proid.myapp',
            'cell': 'test',
            'cpu': '100%',
            'disk': '100G',
            'environment': 'dev',
            'host_ip': '172.31.81.67',
            'memory': '100M',
            'name': 'proid.myapp#001',
            'proid': 'foo',
            'shared_network': False,
            'task': '001',
            'uniqueid': '0000000ID1234',
            'archive': [
                '/var/tmp/treadmill'
            ],
            'endpoints': [
                {
                    'port': 8000,
                    'name': 'http',
                    'real_port': 5000
                },
                {
                    'port': 54321,
                    'type': 'infra',
                    'name': 'ssh',
                    'real_port': 54321
                }
            ],
            'ephemeral_ports': {
                'tcp': [45024],
                'udp': [62422],
            },
            'services': [
                {
                    'command': '/bin/false',
                    'restart_count': 3,
                    'name': 'web_server'
                }
            ],
        }
        treadmill.appmgr.manifest.read.return_value = manifest
        app_unique_name = 'proid.myapp-001-0000000ID1234'
        mock_cgroup_client = self.app_env.svc_cgroup.make_client.return_value
        mock_ld_client = self.app_env.svc_localdisk.make_client.return_value
        mock_nwrk_client = self.app_env.svc_network.make_client.return_value
        # All resource managers return None
        mock_cgroup_client.get.return_value = None
        mock_ld_client.get.return_value = None
        mock_nwrk_client.get.return_value = None
        app_dir = os.path.join(self.app_env.apps_dir, app_unique_name)
        # Create content in app root directory, verify that it is archived.
        fs.mkdir_safe(os.path.join(app_dir, 'root', 'xxx'))
        fs.mkdir_safe(os.path.join(app_dir, 'services'))
        # Simulate daemontools finish script, marking the app is done.
        with open(os.path.join(app_dir, 'exitinfo'), 'w') as f:
            f.write(yaml.dump({'service': 'web_server', 'rc': 0, 'sig': 0}))
        mock_zkclient = kazoo.client.KazooClient()

        app_finish.finish(
            self.app_env, mock_zkclient, app_dir
        )

        self.app_env.watchdogs.create.assert_called_with(
            'treadmill.appmgr.finish-' + app_unique_name,
            '5m',
            mock.ANY
        )
        treadmill.subproc.check_call.assert_has_calls(
            [
                mock.call(
                    [
                        's6-svc',
                        '-d',
                        app_dir,
                    ],
                ),
                mock.call(
                    [
                        's6-svwait',
                        '-d',
                        app_dir,
                    ],
                ),
            ]
        )
        self.app_env.svc_cgroup.make_client.assert_called_with(
            os.path.join(app_dir, 'cgroups')
        )
        self.app_env.svc_localdisk.make_client.assert_called_with(
            os.path.join(app_dir, 'localdisk')
        )
        self.app_env.svc_network.make_client.assert_called_with(
            os.path.join(app_dir, 'network')
        )

        treadmill.appmgr.finish._kill_apps_by_root.assert_called_with(
            os.path.join(app_dir, 'root')
        )

        # Verify that the app folder was deleted
        self.assertFalse(os.path.exists(app_dir))
        # Cleanup the network resources
        mock_nwrk_client.get.assert_called_with(app_unique_name)
        # Cleanup the block device
        mock_ld_client.delete.assert_called_with(app_unique_name)
        # Cleanup the cgroup resource
        mock_cgroup_client.delete.assert_called_with(app_unique_name)

        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            events.FinishedTraceEvent(
                instanceid='proid.myapp#001',
                rc=0,
                signal=0,
                payload={
                    'service': 'web_server',
                    'sig': 0,
                    'rc': 0
                }
            )
        )
        treadmill.rrdutils.flush_noexc.assert_called_with(
            os.path.join(self.root, 'metrics', 'apps',
                         app_unique_name + '.rrd')
        )
        shutil.copy.assert_called_with(
            os.path.join(self.root, 'metrics', 'apps',
                         app_unique_name + '.rrd'),
            os.path.join(app_dir, 'metrics.rrd')
        )

    def test__copy_metrics(self):
        """Test that metrics are copied safely.
        """
        # Access protected module _copy_metrics
        # pylint: disable=W0212
        with open(os.path.join(self.root, 'in.rrd'), 'w+'):
            pass

        app_finish._copy_metrics(os.path.join(self.root, 'in.rrd'),
                                 self.root)
        self.assertTrue(os.path.exists(os.path.join(self.root, 'metrics.rrd')))
        os.unlink(os.path.join(self.root, 'metrics.rrd'))

        app_finish._copy_metrics(os.path.join(self.root, 'nosuchthing.rrd'),
                                 self.root)
        self.assertFalse(
            os.path.exists(os.path.join(self.root, 'metrics.rrd')))

    def test__archive_logs(self):
        """Tests archiving local logs."""
        # Access protected module _archive_logs
        #
        # pylint: disable=W0212
        container_dir = os.path.join(self.root, 'xxx.yyy-1234-qwerty')
        fs.mkdir_safe(container_dir)
        archives_dir = os.path.join(self.root, 'archives')
        fs.mkdir_safe(archives_dir)
        sys_archive = os.path.join(archives_dir,
                                   'xxx.yyy-1234-qwerty.sys.tar.gz')
        app_archive = os.path.join(archives_dir,
                                   'xxx.yyy-1234-qwerty.app.tar.gz')
        app_finish._archive_logs(self.app_env, container_dir)

        self.assertTrue(os.path.exists(sys_archive))
        self.assertTrue(os.path.exists(app_archive))
        os.unlink(sys_archive)
        os.unlink(app_archive)

        def _touch_file(path):
            """Touch file, appending path to container_dir."""
            fpath = os.path.join(container_dir, path)
            fs.mkdir_safe(os.path.dirname(fpath))
            open(fpath, 'w+').close()

        _touch_file('sys/foo/log/current')
        _touch_file('sys/bla/log/current')
        _touch_file('sys/bla/log/xxx')
        _touch_file('services/xxx/log/current')
        _touch_file('services/xxx/log/whatever')
        _touch_file('a.yml')
        _touch_file('a.rrd')
        _touch_file('log/current')
        _touch_file('whatever')

        app_finish._archive_logs(self.app_env, container_dir)

        tar = tarfile.open(sys_archive)
        files = sorted([member.name for member in tar.getmembers()])
        self.assertEquals(
            files,
            ['a.rrd', 'a.yml', 'log/current',
             'sys/bla/log/current', 'sys/foo/log/current']
        )
        tar.close()

        tar = tarfile.open(app_archive)
        files = sorted([member.name for member in tar.getmembers()])
        self.assertEquals(
            files,
            ['services/xxx/log/current']
        )
        tar.close()

    def test__archive_cleanup(self):
        """Tests cleanup of local logs."""
        # Access protected module _ARCHIVE_LIMIT, _cleanup_archive_dir
        #
        # pylint: disable=W0212
        fs.mkdir_safe(self.app_env.archives_dir)

        # Cleanup does not care about file extensions, it will cleanup
        # oldest file if threshold is exceeded.
        app_finish._ARCHIVE_LIMIT = 20
        file1 = os.path.join(self.app_env.archives_dir, '1')
        with open(file1, 'w+') as f:
            f.write('x' * 10)

        app_finish._cleanup_archive_dir(self.app_env)
        self.assertTrue(os.path.exists(file1))

        os.utime(file1, (time.time() - 1, time.time() - 1))
        file2 = os.path.join(self.app_env.archives_dir, '2')
        with open(file2, 'w+') as f:
            f.write('x' * 10)

        app_finish._cleanup_archive_dir(self.app_env)
        self.assertTrue(os.path.exists(file1))

        with open(os.path.join(self.app_env.archives_dir, '2'), 'w+') as f:
            f.write('x' * 15)
        app_finish._cleanup_archive_dir(self.app_env)
        self.assertFalse(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))


if __name__ == '__main__':
    unittest.main()
