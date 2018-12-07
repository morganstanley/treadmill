"""Unit test for treadmill.runtime.linux._finish.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import io
import os
import shutil
import tempfile
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows   # pylint: disable=W0611

import treadmill
import treadmill.rulefile

from treadmill import firewall
from treadmill import fs
from treadmill import iptables
from treadmill import utils

from treadmill.trace.app import events
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
    @mock.patch('treadmill.trace.post', mock.Mock())
    @mock.patch('treadmill.postmortem._datetime_utcnow', mock.Mock(
        return_value=datetime.datetime(2015, 1, 22, 14, 14, 36, 537918)))
    @mock.patch('treadmill.appcfg.manifest.read', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='xxx.xx.com'))
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.iptables.flush_cnt_conntrack_table', mock.Mock())
    @mock.patch('treadmill.rrdutils.flush_noexc', mock.Mock())
    @mock.patch('treadmill.runtime.archive_logs', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.zkutils.get',
                mock.Mock(return_value={
                    'server': 'nonexist',
                    'auth': 'nonexist',
                }))
    def test_finish(self):
        """Tests container finish procedure and freeing of the resources.
        """
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
                '/var/lib/treadmill'
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
            'passthrough': [
                '8.8.8.8',
                '9.9.9.9',
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
        with io.open(os.path.join(data_dir, 'exitinfo'), 'w') as f:
            f.writelines(
                utils.json_genencode(
                    {'service': 'web_server', 'return_code': 0, 'signal': 0},
                )
            )

        app_finish.finish(self.tm_env, app_dir)

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
                mock.call(chain=iptables.PREROUTING_PASSTHROUGH,
                          rule=firewall.PassThroughRule(
                              src_ip='8.8.8.8',
                              dst_ip='192.168.0.2',
                          ),
                          owner=app_unique_name),
                mock.call(chain=iptables.PREROUTING_PASSTHROUGH,
                          rule=firewall.PassThroughRule(
                              src_ip='9.9.9.9',
                              dst_ip='192.168.0.2',
                          ),
                          owner=app_unique_name),
            ],
            any_order=True
        )
        self.assertEqual(self.tm_env.rules.unlink_rule.call_count, 8)
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
        treadmill.iptables.flush_cnt_conntrack_table.assert_called_with(
            '192.168.0.2'
        )
        treadmill.trace.post.assert_called_with(
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

        treadmill.runtime.archive_logs.assert_called()

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.trace.post', mock.Mock())
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.appcfg.manifest.read', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='myhostname'))
    @mock.patch('treadmill.cgroups.delete', mock.Mock())
    @mock.patch('treadmill.cgutils.reset_memory_limit_in_bytes',
                mock.Mock(return_value=[]))
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.supervisor.control_service', mock.Mock())
    @mock.patch('treadmill.zkutils.get', mock.Mock(return_value=None))
    @mock.patch('treadmill.rrdutils.flush_noexc', mock.Mock())
    @mock.patch('treadmill.runtime.archive_logs', mock.Mock())
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
                '/var/lib/treadmill'
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
        with io.open(os.path.join(data_dir, 'exitinfo'), 'w') as f:
            f.writelines(
                utils.json_genencode(
                    {'service': 'web_server', 'return_code': 1, 'signal': 3},
                )
            )
        app_finish.finish(self.tm_env, app_dir)

        treadmill.trace.post.assert_called_with(
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

        treadmill.runtime.archive_logs.assert_called()

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.trace.post', mock.Mock())
    @mock.patch('treadmill.appcfg.manifest.read', mock.Mock())
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='hostname'))
    @mock.patch('treadmill.rulefile.RuleMgr.unlink_rule', mock.Mock())
    @mock.patch('treadmill.runtime.archive_logs', mock.Mock())
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
                '/var/lib/treadmill'
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
        with io.open(os.path.join(data_dir, 'aborted'), 'w') as aborted:
            aborted.write('{"why": "reason", "payload": "test"}')

        app_finish.finish(self.tm_env, app_dir)

        treadmill.trace.post.assert_called_with(
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

        treadmill.trace.post.reset()

        with io.open(os.path.join(data_dir, 'aborted'), 'w') as aborted:
            aborted.write('')

        app_finish.finish(self.tm_env, app_dir)

        treadmill.trace.post.assert_called_with(
            mock.ANY,
            events.AbortedTraceEvent(
                instanceid='proid.myapp#001',
                why='unknown',
                payload=None
            )
        )

        treadmill.runtime.archive_logs.assert_called()

    @mock.patch('treadmill.subproc.check_call', mock.Mock(return_value=0))
    def test_finish_no_manifest(self):
        """Test app finish on directory with no app.json.
        """
        app_finish.finish(self.tm_env, self.root)

    @mock.patch('shutil.copy', mock.Mock())
    @mock.patch('treadmill.trace.post', mock.Mock())
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.postmortem._datetime_utcnow', mock.Mock(
        return_value=datetime.datetime(2015, 1, 22, 14, 14, 36, 537918)))
    @mock.patch('treadmill.appcfg.manifest.read', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='xxx.ms.com'))
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.rrdutils.flush_noexc', mock.Mock())
    @mock.patch('treadmill.runtime.archive_logs', mock.Mock())
    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    @mock.patch('treadmill.zkutils.get',
                mock.Mock(return_value={
                    'server': 'nonexist',
                    'auth': 'nonexist',
                }))
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    def test_finish_no_resources(self):
        """Test app finish on directory when all resources are already freed.
        """
        # Access to a protected member _finish of a client class
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
                '/var/lib/treadmill'
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
        with io.open(os.path.join(data_dir, 'exitinfo'), 'w') as f:
            f.writelines(
                utils.json_genencode(
                    {'service': 'web_server', 'return_code': 0, 'signal': 0},
                )
            )
        treadmill.runtime.linux._finish.finish(self.tm_env, app_dir)

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

        # Cleanup the network resources
        mock_nwrk_client.get.assert_called_with(app_unique_name)
        # Cleanup the block device
        mock_ld_client.delete.assert_called_with(app_unique_name)
        # Cleanup the cgroup resource
        mock_cgroup_client.delete.assert_called_with(app_unique_name)

        treadmill.trace.post.assert_called_with(
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

        treadmill.runtime.archive_logs.assert_called()

    @mock.patch('treadmill.runtime.load_app', mock.Mock())
    @mock.patch('treadmill.runtime.linux._finish._cleanup', mock.Mock())
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.trace.post', mock.Mock())
    def test_finish_exitinfo_event(self):
        """Test posting finished event.
        """
        app_unique_name = 'proid.myapp-001-0000000ID1234'
        app_dir = os.path.join(self.tm_env.apps_dir, app_unique_name)
        data_dir = os.path.join(app_dir, 'data')
        fs.mkdir_safe(data_dir)
        with io.open(os.path.join(data_dir, 'exitinfo'), 'w') as f:
            f.write('{"service": "web_server", "return_code": 0, "signal": 0}')

        app_finish.finish(self.tm_env, app_dir)

        args, _kwargs = treadmill.trace.post.call_args
        _events_dir, event = args
        self.assertIsInstance(event, events.FinishedTraceEvent)

    @mock.patch('treadmill.runtime.load_app', mock.Mock())
    @mock.patch('treadmill.runtime.linux._finish._cleanup', mock.Mock())
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.trace.post', mock.Mock())
    def test_finish_aborted_event(self):
        """Test posting aborted event.
        """
        app_unique_name = 'proid.myapp-001-0000000ID1234'
        app_dir = os.path.join(self.tm_env.apps_dir, app_unique_name)
        data_dir = os.path.join(app_dir, 'data')
        fs.mkdir_safe(data_dir)
        with io.open(os.path.join(data_dir, 'aborted'), 'w') as f:
            f.write('{"why": "reason", "payload": "test"}')

        app_finish.finish(self.tm_env, app_dir)

        args, _kwargs = treadmill.trace.post.call_args
        _events_dir, event = args
        self.assertIsInstance(event, events.AbortedTraceEvent)

    @mock.patch('treadmill.runtime.load_app', mock.Mock())
    @mock.patch('treadmill.runtime.linux._finish._cleanup', mock.Mock())
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.trace.post', mock.Mock())
    def test_finish_oom_event(self):
        """Test posting oom event.
        """
        app_unique_name = 'proid.myapp-001-0000000ID1234'
        app_dir = os.path.join(self.tm_env.apps_dir, app_unique_name)
        data_dir = os.path.join(app_dir, 'data')
        fs.mkdir_safe(data_dir)
        utils.touch(os.path.join(data_dir, 'oom'))

        app_finish.finish(self.tm_env, app_dir)

        args, _kwargs = treadmill.trace.post.call_args
        _events_dir, event = args
        self.assertIsInstance(event, events.KilledTraceEvent)

    @mock.patch('treadmill.runtime.load_app', mock.Mock())
    @mock.patch('treadmill.runtime.linux._finish._cleanup', mock.Mock())
    @mock.patch('treadmill.apphook.cleanup', mock.Mock())
    @mock.patch('treadmill.trace.post', mock.Mock())
    def test_terminated_no_event(self):
        """Test that event won't be posted if container is terminated/evicted.
        """
        app_unique_name = 'proid.myapp-001-0000000ID1234'
        app_dir = os.path.join(self.tm_env.apps_dir, app_unique_name)
        data_dir = os.path.join(app_dir, 'data')
        fs.mkdir_safe(data_dir)
        utils.touch(os.path.join(data_dir, 'terminated'))
        # exitinfo file should be ignored.
        with io.open(os.path.join(data_dir, 'exitinfo'), 'w') as f:
            f.write('{"service": "web_server", "return_code": 0, "signal": 0}')

        app_finish.finish(self.tm_env, app_dir)

        treadmill.trace.post.assert_not_called()

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


if __name__ == '__main__':
    unittest.main()
