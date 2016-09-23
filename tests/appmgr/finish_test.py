"""
Unit test for treadmill.appmgr.finish.
"""

import datetime
import os
import shutil
import tempfile
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import kazoo
import mock
import yaml

import treadmill
from treadmill import appmgr
from treadmill import firewall
from treadmill import fs
from treadmill import utils
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

    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
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
    @mock.patch('treadmill.subproc.call', mock.Mock(return_value=0))
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.subproc.invoke', mock.Mock())
    @mock.patch('treadmill.zkutils.connect', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.get',
                mock.Mock(return_value={
                    'server': 'nonexist',
                    'auth': 'nonexist',
                }))
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.rrdutils.flush_noexc', mock.Mock())
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
                    'real_port': 5000
                },
                {
                    'port': 54321,
                    'type': 'infra',
                    'name': 'ssh',
                    'real_port': 54321
                }
            ],
            'ephemeral_ports': [
                45024,
                62422
            ],
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
            f.write(yaml.dump({'service': 'web_server', 'rc': 0, 'sig': 0}))
        kazoo.client.KazooClient.exists.return_value = True
        kazoo.client.KazooClient.get_children.return_value = []

        zkclient = kazoo.client.KazooClient()
        app_finish.finish(self.app_env, zkclient, app_dir)

        self.app_env.watchdogs.create.assert_called_with(
            'treadmill.appmgr.finish:' + app_unique_name,
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
        self.app_env.svc_cgroup.make_client.assert_called_with(
            os.path.join(app_dir, 'cgroups')
        )
        self.app_env.svc_localdisk.make_client.assert_called_with(
            os.path.join(app_dir, 'localdisk')
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
            zkclient,
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
        self.app_env.rules.unlink_rule.assert_has_calls([
            mock.call(rule=firewall.DNATRule('172.31.81.67', 5000,
                                             '192.168.0.2', 8000),
                      owner=app_unique_name),
            mock.call(rule=firewall.DNATRule('172.31.81.67', 54321,
                                             '192.168.0.2', 54321),
                      owner=app_unique_name),
            mock.call(rule=firewall.DNATRule('172.31.81.67', 45024,
                                             '192.168.0.2', 45024),
                      owner=app_unique_name),
            mock.call(rule=firewall.DNATRule('172.31.81.67', 62422,
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
                          '192.168.0.2,tcp:62422'),
            ]
        )
        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            'proid.myapp#001', 'finished', '0.0',
            {'sig': 0,
             'service':
             'web_server',
             'rc': 0}
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

    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
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
    @mock.patch('treadmill.zkutils.connect', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
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
                    'real_port': 5000
                }
            ],
            'services': [
                {
                    'command': '/bin/false',
                    'restart_count': 3,
                    'name': 'web_server'
                }
            ],
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
        kazoo.client.KazooClient.exists.return_value = True
        kazoo.client.KazooClient.get_children.return_value = []

        app_finish.finish(
            self.app_env, kazoo.client.KazooClient(), app_dir
        )
        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            'proid.myapp#001', 'finished', '1.3',
            {'sig': 3,
             'service': 'web_server',
             'rc': 1}
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

    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
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
    @mock.patch('treadmill.zkutils.connect', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
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
                    'real_port': 5000
                }
            ],
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
        kazoo.client.KazooClient.exists.return_value = True
        kazoo.client.KazooClient.get_children.return_value = []

        app_finish.finish(
            self.app_env, kazoo.client.KazooClient(), app_dir
        )

        treadmill.appevents.post(
            mock.ANY,
            'proid.myapp#001', 'aborted',
            {'why': 'something went wrong',
             'node': 'hostname'})
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
        app_env = appmgr.AppEnvironment(root=self.root)
        app_finish.finish(app_env, None, self.root)

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


if __name__ == '__main__':
    unittest.main()
