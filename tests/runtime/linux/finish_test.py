"""Unit test for treadmill.runtime.linux._finish.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import io
import json
import os
import shutil
import tarfile
import tempfile
import time
import unittest

import mock

import treadmill
import treadmill.rulefile

from treadmill import firewall
from treadmill import fs
from treadmill import iptables
from treadmill import supervisor

from treadmill.apptrace import events
from treadmill.runtime.linux import _finish as app_finish


class LinuxRuntimeFinishTest(unittest.TestCase):
    """Tests for treadmill.runtime.linux._finish"""

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
            )
        )

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    @mock.patch('treadmill.utils.datetime_utcnow', mock.Mock(
        return_value=datetime.datetime(2015, 1, 22, 14, 14, 36, 537918)))
    @mock.patch('treadmill.appcfg.manifest.read', mock.Mock())
    @mock.patch('treadmill.runtime.linux._finish._kill_apps_by_root',
                mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='xxx.xx.com'))
    @mock.patch('treadmill.fs.archive_filesystem',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.rrdutils.flush_noexc', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.supervisor.control_service', mock.Mock())
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
            'vring': {
                'some': 'settings'
            }
        }
        treadmill.appcfg.manifest.read.return_value = manifest
        app_unique_name = 'proid.myapp-001-0000000ID1234'
        mock_cgroup_client = self.tm_env.svc_cgroup.make_client.return_value
        mock_ld_client = self.tm_env.svc_localdisk.make_client.return_value
        mock_nwrk_client = self.tm_env.svc_network.make_client.return_value
        localdisk = {
            'block_dev': '/dev/foo',
        }
        mock_ld_client.get.return_value = localdisk
        network = {
            'vip': '192.168.0.2',
            'gateway': '192.168.254.254',
            'veth': 'testveth.0',
            'external_ip': '172.31.81.67',
        }
        mock_nwrk_client.get.return_value = network
        app_dir = os.path.join(self.tm_env.apps_dir, app_unique_name)
        data_dir = os.path.join(app_dir, 'data')
        # Create content in app root directory, verify that it is archived.
        fs.mkdir_safe(os.path.join(data_dir, 'root', 'xxx'))
        fs.mkdir_safe(os.path.join(data_dir, 'services'))
        # Simulate daemontools finish script, marking the app is done.
        with io.open(os.path.join(data_dir, 'exitinfo'), 'wb') as f:
            json.dump(
                {'service': 'web_server', 'return_code': 0, 'signal': 0},
                f
            )

        app_finish.finish(self.tm_env, app_dir)

        treadmill.supervisor.control_service.assert_called_with(
            app_dir, supervisor.ServiceControlAction.down,
            wait=supervisor.ServiceWaitAction.down
        )

        # All resource service clients are properly created
        self.tm_env.svc_cgroup.make_client.assert_called_with(
            os.path.join(data_dir, 'resources', 'cgroups')
        )
        self.tm_env.svc_localdisk.make_client.assert_called_with(
            os.path.join(data_dir, 'resources', 'localdisk')
        )
        self.tm_env.svc_network.make_client.assert_called_with(
            os.path.join(data_dir, 'resources', 'network')
        )

        treadmill.runtime.linux._finish._kill_apps_by_root.assert_called_with(
            os.path.join(data_dir, 'root')
        )

        # Verify that we tested the archiving for the app root volume
        treadmill.fs.archive_filesystem.assert_called_with(
            '/dev/foo',
            os.path.join(data_dir, 'root'),
            os.path.join(data_dir,
                         '001_xxx.xx.com_20150122_141436537918.tar'),
            mock.ANY
        )
        # Cleanup the block device
        mock_ld_client.delete.assert_called_with(app_unique_name)
        # Cleanup the cgroup resource
        mock_cgroup_client.delete.assert_called_with(app_unique_name)
        # Cleanup network resources
        mock_nwrk_client.get.assert_called_with(app_unique_name)
        self.tm_env.rules.unlink_rule.assert_has_calls(
            [
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='tcp',
                              dst_ip='172.31.81.67', dst_port=5000,
                              new_ip='192.168.0.2', new_port=8000
                          ),
                          owner=app_unique_name),
                mock.call(chain=iptables.POSTROUTING_SNAT,
                          rule=firewall.SNATRule(
                              proto='tcp',
                              src_ip='192.168.0.2', src_port=8000,
                              new_ip='172.31.81.67', new_port=5000
                          ),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='tcp',
                              dst_ip='172.31.81.67', dst_port=54321,
                              new_ip='192.168.0.2', new_port=54321
                          ),
                          owner=app_unique_name),
                mock.call(chain=iptables.POSTROUTING_SNAT,
                          rule=firewall.SNATRule(
                              proto='tcp',
                              src_ip='192.168.0.2', src_port=54321,
                              new_ip='172.31.81.67', new_port=54321
                          ),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='tcp',
                              dst_ip='172.31.81.67', dst_port=45024,
                              new_ip='192.168.0.2', new_port=45024
                          ),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_DNAT,
                          rule=firewall.DNATRule(
                              proto='udp',
                              dst_ip='172.31.81.67', dst_port=62422,
                              new_ip='192.168.0.2', new_port=62422
                          ),
                          owner=app_unique_name),

            ],
            any_order=True
        )
        self.assertEqual(self.tm_env.rules.unlink_rule.call_count, 6)
        treadmill.iptables.rm_ip_set.assert_has_calls(
            [
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.0.2,tcp:54321'),
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.0.2,tcp:45024'),
                mock.call(treadmill.iptables.SET_INFRA_SVC,
                          '192.168.0.2,udp:62422'),
                mock.call(treadmill.iptables.SET_VRING_CONTAINERS,
                          '192.168.0.2'),
            ],
            any_order=True
        )
        self.assertEqual(treadmill.iptables.rm_ip_set.call_count, 4)
        mock_nwrk_client.delete.assert_called_with(app_unique_name)
        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            events.FinishedTraceEvent(
                instanceid='proid.myapp#001',
                rc=0,
                signal=0,
                payload={
                    'service': 'web_server',
                    'signal': 0,
                    'return_code': 0
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
            os.path.join(data_dir, 'metrics.rrd')
        )

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.runtime.linux._finish._kill_apps_by_root',
                mock.Mock())
    @mock.patch('treadmill.appcfg.manifest.read', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='myhostname'))
    @mock.patch('treadmill.cgroups.delete', mock.Mock())
    @mock.patch('treadmill.cgutils.reset_memory_limit_in_bytes',
                mock.Mock(return_value=[]))
    @mock.patch('treadmill.fs.archive_filesystem',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.supervisor.control_service', mock.Mock())
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
            },
            'vring': {
                'some': 'settings'
            }
        }
        treadmill.appcfg.manifest.read.return_value = manifest
        app_unique_name = 'proid.myapp-001-0000000001234'
        mock_ld_client = self.tm_env.svc_localdisk.make_client.return_value
        localdisk = {
            'block_dev': '/dev/foo',
        }
        mock_ld_client.get.return_value = localdisk
        mock_nwrk_client = self.tm_env.svc_network.make_client.return_value
        network = {
            'vip': '192.168.0.2',
            'gateway': '192.168.254.254',
            'veth': 'testveth.0',
            'external_ip': '172.31.81.67',
        }
        mock_nwrk_client.get.return_value = network
        app_dir = os.path.join(self.tm_env.apps_dir, app_unique_name)
        data_dir = os.path.join(app_dir, 'data')
        # Create content in app root directory, verify that it is archived.
        fs.mkdir_safe(os.path.join(data_dir, 'root', 'xxx'))
        fs.mkdir_safe(os.path.join(data_dir, 'services'))
        # Simulate daemontools finish script, marking the app is done.
        with io.open(os.path.join(data_dir, 'exitinfo'), 'wb') as f:
            json.dump(
                {'service': 'web_server', 'return_code': 1, 'signal': 3},
                fp=f
            )
        app_finish.finish(self.tm_env, app_dir)

        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            events.FinishedTraceEvent(
                instanceid='proid.myapp#001',
                rc=1,
                signal=3,
                payload={
                    'service': 'web_server',
                    'signal': 3,
                    'return_code': 1,
                }
            )
        )
        treadmill.rrdutils.flush_noexc.assert_called_with(
            os.path.join(self.root, 'metrics', 'apps',
                         app_unique_name + '.rrd')
        )
        shutil.copy.assert_called_with(
            os.path.join(self.tm_env.metrics_dir, 'apps',
                         app_unique_name + '.rrd'),
            os.path.join(data_dir, 'metrics.rrd')
        )

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    @mock.patch('treadmill.appcfg.manifest.read', mock.Mock())
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.runtime.linux._finish._kill_apps_by_root',
                mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='hostname'))
    @mock.patch('treadmill.fs.archive_filesystem',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.rulefile.RuleMgr.unlink_rule', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
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
            },
            'vring': {
                'some': 'settings'
            }
        }
        treadmill.appcfg.manifest.read.return_value = manifest
        app_unique_name = 'proid.myapp-001-0000000ID1234'
        mock_ld_client = self.tm_env.svc_localdisk.make_client.return_value
        localdisk = {
            'block_dev': '/dev/foo',
        }
        mock_ld_client.get.return_value = localdisk
        mock_nwrk_client = self.tm_env.svc_network.make_client.return_value
        network = {
            'vip': '192.168.0.2',
            'gateway': '192.168.254.254',
            'veth': 'testveth.0',
            'external_ip': '172.31.81.67',
        }
        mock_nwrk_client.get.return_value = network
        app_dir = os.path.join(self.root, 'apps', app_unique_name)
        data_dir = os.path.join(app_dir, 'data')
        # Create content in app root directory, verify that it is archived.
        fs.mkdir_safe(os.path.join(data_dir, 'root', 'xxx'))
        fs.mkdir_safe(os.path.join(data_dir, 'services'))
        # Simulate daemontools finish script, marking the app is done.
        with io.open(os.path.join(data_dir, 'aborted'), 'wb') as aborted:
            aborted.write('{"why": "reason", "payload": "test"}')

        app_finish.finish(self.tm_env, app_dir)

        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            events.AbortedTraceEvent(
                instanceid='proid.myapp#001',
                why='reason',
                payload='test'
            )
        )
        treadmill.rrdutils.flush_noexc.assert_called_with(
            os.path.join(self.root, 'metrics', 'apps',
                         app_unique_name + '.rrd')
        )
        shutil.copy.assert_called_with(
            os.path.join(self.root, 'metrics', 'apps',
                         app_unique_name + '.rrd'),
            os.path.join(data_dir, 'metrics.rrd')
        )

        treadmill.appevents.post.reset()

        with io.open(os.path.join(data_dir, 'aborted'), 'w') as aborted:
            aborted.write('')

        app_finish.finish(self.tm_env, app_dir)

        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            events.AbortedTraceEvent(
                instanceid='proid.myapp#001',
                why='unknown',
                payload=None
            )
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(return_value=0))
    def test_finish_no_manifest(self):
        """Test app finish on directory with no app.json.
        """
        app_finish.finish(self.tm_env, self.root)

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.utils.datetime_utcnow', mock.Mock(
        return_value=datetime.datetime(2015, 1, 22, 14, 14, 36, 537918)))
    @mock.patch('treadmill.appcfg.manifest.read', mock.Mock())
    @mock.patch('treadmill.runtime.linux._finish._kill_apps_by_root',
                mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='xxx.ms.com'))
    @mock.patch('treadmill.fs.archive_filesystem',
                mock.Mock(return_value=True))
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.rrdutils.flush_noexc', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.supervisor.control_service', mock.Mock())
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
            'vring': {
                'some': 'settings'
            }
        }
        treadmill.appcfg.manifest.read.return_value = manifest
        app_unique_name = 'proid.myapp-001-0000000ID1234'
        mock_cgroup_client = self.tm_env.svc_cgroup.make_client.return_value
        mock_ld_client = self.tm_env.svc_localdisk.make_client.return_value
        mock_nwrk_client = self.tm_env.svc_network.make_client.return_value
        # All resource managers return None
        mock_cgroup_client.get.return_value = None
        mock_ld_client.get.return_value = None
        mock_nwrk_client.get.return_value = None
        app_dir = os.path.join(self.tm_env.apps_dir, app_unique_name)
        data_dir = os.path.join(app_dir, 'data')
        # Create content in app root directory, verify that it is archived.
        fs.mkdir_safe(os.path.join(data_dir, 'root', 'xxx'))
        fs.mkdir_safe(os.path.join(data_dir, 'services'))
        # Simulate daemontools finish script, marking the app is done.
        with io.open(os.path.join(data_dir, 'exitinfo'), 'wb') as f:
            json.dump(
                {'service': 'web_server', 'return_code': 0, 'signal': 0},
                f
            )
        treadmill.runtime.linux._finish.finish(self.tm_env, app_dir)

        treadmill.supervisor.control_service.assert_called_with(
            app_dir, supervisor.ServiceControlAction.down,
            wait=supervisor.ServiceWaitAction.down
        )

        # All resource service clients are properly created
        self.tm_env.svc_cgroup.make_client.assert_called_with(
            os.path.join(data_dir, 'resources', 'cgroups')
        )
        self.tm_env.svc_localdisk.make_client.assert_called_with(
            os.path.join(data_dir, 'resources', 'localdisk')
        )
        self.tm_env.svc_network.make_client.assert_called_with(
            os.path.join(data_dir, 'resources', 'network')
        )

        treadmill.runtime.linux._finish._kill_apps_by_root.assert_called_with(
            os.path.join(data_dir, 'root')
        )

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
                    'signal': 0,
                    'return_code': 0
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
            os.path.join(data_dir, 'metrics.rrd')
        )

    def test__copy_metrics(self):
        """Test that metrics are copied safely.
        """
        # Access protected module _copy_metrics
        # pylint: disable=W0212
        with io.open(os.path.join(self.root, 'in.rrd'), 'w'):
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
        data_dir = os.path.join(self.root, 'xxx.yyy-1234-qwerty', 'data')
        fs.mkdir_safe(data_dir)
        archives_dir = os.path.join(self.root, 'archives')
        fs.mkdir_safe(archives_dir)
        sys_archive = os.path.join(archives_dir,
                                   'xxx.yyy-1234-qwerty.sys.tar.gz')
        app_archive = os.path.join(archives_dir,
                                   'xxx.yyy-1234-qwerty.app.tar.gz')
        app_finish._archive_logs(self.tm_env, 'xxx.yyy-1234-qwerty', data_dir)

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
        _touch_file('a.json')
        _touch_file('a.rrd')
        _touch_file('log/current')
        _touch_file('whatever')

        app_finish._archive_logs(self.tm_env, 'xxx.yyy-1234-qwerty', data_dir)

        tar = tarfile.open(sys_archive)
        files = sorted([member.name for member in tar.getmembers()])
        self.assertEqual(
            files,
            ['a.json', 'a.rrd', 'log/current',
             'sys/bla/data/log/current', 'sys/foo/data/log/current']
        )
        tar.close()

        tar = tarfile.open(app_archive)
        files = sorted([member.name for member in tar.getmembers()])
        self.assertEqual(
            files,
            ['services/xxx/data/log/current']
        )
        tar.close()

    def test__archive_cleanup(self):
        """Tests cleanup of local logs."""
        # Access protected module _ARCHIVE_LIMIT, _cleanup_archive_dir
        #
        # pylint: disable=W0212
        fs.mkdir_safe(self.tm_env.archives_dir)

        # Cleanup does not care about file extensions, it will cleanup
        # oldest file if threshold is exceeded.
        app_finish._ARCHIVE_LIMIT = 20
        file1 = os.path.join(self.tm_env.archives_dir, '1')
        with io.open(file1, 'w') as f:
            f.write('x' * 10)

        app_finish._cleanup_archive_dir(self.tm_env)
        self.assertTrue(os.path.exists(file1))

        os.utime(file1, (time.time() - 1, time.time() - 1))
        file2 = os.path.join(self.tm_env.archives_dir, '2')
        with io.open(file2, 'w') as f:
            f.write('x' * 10)

        app_finish._cleanup_archive_dir(self.tm_env)
        self.assertTrue(os.path.exists(file1))

        with io.open(os.path.join(self.tm_env.archives_dir, '2'), 'w') as f:
            f.write('x' * 15)
        app_finish._cleanup_archive_dir(self.tm_env)
        self.assertFalse(os.path.exists(file1))
        self.assertTrue(os.path.exists(file2))


if __name__ == '__main__':
    unittest.main()
