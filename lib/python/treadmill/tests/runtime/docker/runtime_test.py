"""Unit test for treadmill.runtime.docker.runtime
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import tempfile
import unittest

import docker
import mock

import treadmill
from treadmill import exc
from treadmill import fs
from treadmill import rulefile
from treadmill import utils
from treadmill.appcfg import abort as app_abort
from treadmill.trace.app import events
from treadmill.runtime.docker import runtime


class DockerRuntimeTest(unittest.TestCase):
    """Tests for treadmill.runtime.docker.runtime."""

    def setUp(self):
        # Access protected module _base_service
        # pylint: disable=W0212
        self.root = tempfile.mkdtemp()
        self.container_dir = os.path.join(self.root, 'apps', 'test')
        self.data_dir = os.path.join(self.container_dir, 'data')
        fs.mkdir_safe(self.data_dir)
        with io.open(os.path.join(self.container_dir, 'type'), 'w') as f:
            f.write('longrun')
        self.events_dir = os.path.join(self.root, 'appevents')
        os.mkdir(self.events_dir)
        self.configs_dir = os.path.join(self.root, 'configs')
        os.mkdir(self.configs_dir)
        self.tm_env = mock.Mock(
            root=self.root,
            app_events_dir=self.events_dir,
            configs_dir=self.configs_dir,
            rules=mock.Mock(
                spec_set=rulefile.RuleMgr,
            ),
        )
        self.manifest = {
            'cpu': 50,
            'disk': '20G',
            'memory': '512M',
            'cell': 'test',
            'app': 'proid.app',
            'task': '001',
            'name': 'proid.app#001',
            'uniqueid': 'abcdefghijklm',
            'identity': None,
            'identity_group': None,
            'proid': 'proid',
            'environment': 'dev',
            'endpoints': [
                {
                    'name': 'ep1',
                    'port': '80',
                    'real_port': '12345',
                    'proto': 'tcp'
                },
            ],
            'ephemeral_ports': {
                'tcp': [54321],
                'udp': []
            },
            'environ': [
                {
                    'name': 'key1',
                    'value': 'value1'
                },
                {
                    'name': 'TREADMILL_MEMORY',
                    'value': 'should not be here'
                },
            ],
            'image': 'docker://test',
            'command': 'cmd',
            'args': []
        }
        self.app = utils.to_obj(self.manifest)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test__create_environ(self):
        """Tests creating the environment variable dict for docker."""
        # Access to a protected member
        # pylint: disable=W0212
        environ = runtime._create_environ(self.app)

        self.assertEqual('512M', environ['TREADMILL_MEMORY'])
        self.assertEqual('value1', environ['key1'])
        self.assertEqual('proid.app', environ['TREADMILL_APP'])
        self.assertEqual('54321', environ['TREADMILL_EPHEMERAL_TCP_PORTS'])
        self.assertEqual('12345', environ['TREADMILL_ENDPOINT_EP1'])

    @mock.patch('docker.DockerClient', autospec=True)
    @mock.patch('multiprocessing.cpu_count', mock.Mock(return_value=4))
    @mock.patch('treadmill.runtime.docker.runtime._get_gmsa', mock.Mock())
    @mock.patch('treadmill.runtime.docker.runtime._create_docker_log_symlink',
                mock.Mock())
    def test__create_container(self, client):
        """Tests creating a docker container using the api."""

        volume_mapping = {
            'app\\data\\container_data': {
                'bind': 'c:\\container_data',
                'mode': 'ro'
            }
        }

        # Access to a protected member
        # pylint: disable=W0212
        runtime._create_container(self.tm_env, {'network': 'nat2'}, client,
                                  self.app, volume_mapping)

        client.images.pull.assert_called_with(
            'test'
        )
        client.containers.create.assert_called_with(
            image='test',
            name='proid.app-001-abcdefghijklm',
            environment=mock.ANY,
            entrypoint='cmd',
            command=[],
            detach=True,
            tty=True,
            ports={'80/tcp': None},
            network='nat2',
            cpu_shares=128,
            mem_limit='512M',
            storage_opt={
                'size': '20G'
            },
            volumes=volume_mapping
        )

    @mock.patch('treadmill.runtime.docker.runtime._log_port_mapping_config',
                mock.Mock())
    # pylint: disable=C0103
    def test__update_network_info_in_manifest(self):
        """Tests _update_network_info_in_manifest"""
        # mock container
        container = mock.Mock()
        type(container).status = mock.PropertyMock(
            side_effect=['running', 'running', 'exited']
        )
        type(container).attrs = mock.PropertyMock(
            side_effect=[
                {'State': {'Running': False}},
                {'State': {'Running': True}},
                {
                    'State': {'Running': True},
                    'NetworkSettings': {
                        'Ports': {
                            '80/tcp': [{'HostPort': '22345'}]
                        }
                    }
                }
            ]
        )

        # simplified manifest
        manifest = {
            'endpoints': [
                {
                    'port': '80',
                    'proto': 'tcp'
                }
            ]
        }

        # Access to a protected member
        # pylint: disable=W0212
        runtime._update_network_info_in_manifest(container, manifest)
        self.assertEqual(manifest['endpoints'][0]['real_port'], '22345')

    def test__check_aborted(self):
        """Tests checking aborted."""
        # Access to a protected member
        # pylint: disable=W0212
        aborted = runtime._check_aborted(self.data_dir)

        self.assertIsNone(aborted)

        with io.open(os.path.join(self.data_dir, 'aborted'), 'w') as aborted:
            aborted.write('{"why": "reason", "payload": "test"}')

        aborted = runtime._check_aborted(self.data_dir)

        self.assertEqual('reason', aborted['why'])
        self.assertEqual('test', aborted['payload'])

    @mock.patch('treadmill.runtime.allocate_network_ports', mock.Mock())
    @mock.patch('treadmill.runtime.docker.runtime._create_container',
                mock.Mock())
    @mock.patch(
        'treadmill.runtime.docker.runtime._update_network_info_in_manifest',
        mock.Mock())
    @mock.patch(
        'treadmill.runtime.docker.runtime._print_container_logs',
        mock.Mock())
    @mock.patch('treadmill.presence.EndpointPresence',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    @mock.patch('treadmill.trace.post', mock.Mock())
    @mock.patch('docker.from_env', mock.Mock())
    def test__run(self):
        """Tests docker runtime run."""
        # Access to a protected member
        # pylint: disable=W0212
        docker_runtime = runtime.DockerRuntime(
            self.tm_env, self.container_dir, {'version': '1.24'}
        )

        container = mock.Mock()
        treadmill.runtime.docker.runtime._create_container.return_value = \
            container

        type(container).status = mock.PropertyMock(
            side_effect=['running', 'running', 'exited']
        )

        docker_runtime._run(self.manifest)

        runtime._create_container.assert_called_once()
        container.start.assert_called_once()
        treadmill.trace.post.assert_called_with(
            self.tm_env.app_events_dir,
            events.ServiceRunningTraceEvent(
                instanceid='proid.app#001',
                uniqueid='abcdefghijklm',
                service='docker'
            )
        )

        self.assertEqual(container.reload.call_count, 1)

    @mock.patch('treadmill.runtime.allocate_network_ports', mock.Mock())
    @mock.patch('treadmill.runtime.docker.runtime._create_container',
                mock.Mock())
    @mock.patch('treadmill.presence.EndpointPresence',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    @mock.patch('treadmill.appcfg.abort.report_aborted', mock.Mock())
    @mock.patch('docker.from_env', mock.Mock())
    def test__run_aborted(self):
        """Tests docker runtime run when app has been aborted."""
        # Access to a protected member
        # pylint: disable=W0212
        docker_runtime = runtime.DockerRuntime(self.tm_env, self.container_dir)

        treadmill.runtime.docker.runtime._create_container.side_effect = \
            docker.errors.ImageNotFound('test')

        with self.assertRaises(treadmill.exc.ContainerSetupError) as context:
            docker_runtime._run(self.manifest)

            self.assertEqual(app_abort.AbortedReason.IMAGE,
                             context.exception.why)

        app_abort.report_aborted.reset_mock()

        app_presence = mock.Mock()
        treadmill.presence.EndpointPresence.return_value = app_presence
        app_presence.register.side_effect = exc.ContainerSetupError('test')

        with self.assertRaises(treadmill.exc.ContainerSetupError) as context:
            docker_runtime._run(self.manifest)

            self.assertEqual(app_abort.AbortedReason.PRESENCE,
                             context.exception.why)

    @mock.patch('treadmill.runtime.allocate_network_ports', mock.Mock())
    @mock.patch('treadmill.runtime.docker.runtime._create_container',
                mock.Mock())
    @mock.patch('treadmill.runtime.archive_logs', mock.Mock())
    @mock.patch('treadmill.presence.EndpointPresence',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    @mock.patch('treadmill.trace.post', mock.Mock())
    @mock.patch('docker.from_env', mock.Mock())
    def test__finish(self):
        """Tests docker runtime finish."""
        # Access to a protected member
        # pylint: disable=W0212
        if os.name == 'nt':
            treadmill.ad.credential_spec.cleanup = mock.Mock()

        treadmill.runtime.save_app(self.manifest, self.data_dir)

        client = mock.MagicMock()
        docker.from_env.return_value = client

        container = mock.MagicMock()
        client.containers.get.return_value = container

        type(container).attrs = mock.PropertyMock(return_value={
            'State': {
                'OOMKilled': False,
                'ExitCode': 5
            }
        })

        docker_runtime = runtime.DockerRuntime(
            self.tm_env, self.container_dir, {'version': '1.24'}
        )

        docker_runtime._finish()

        container.remove.assert_called_with(force=True)
        treadmill.trace.post.assert_called_with(
            self.tm_env.app_events_dir,
            events.FinishedTraceEvent(
                instanceid='proid.app#001',
                rc=5,
                signal=0,
                payload=mock.ANY
            )
        )

        treadmill.trace.post.reset_mock()
        type(container).attrs = mock.PropertyMock(return_value={
            'State': {
                'OOMKilled': True
            }
        })

        docker_runtime._finish()

        treadmill.trace.post.assert_called_with(
            self.tm_env.app_events_dir,
            events.KilledTraceEvent(
                instanceid='proid.app#001',
                is_oom=True,
            )
        )

        treadmill.runtime.archive_logs.assert_called()

    @mock.patch('treadmill.runtime.allocate_network_ports', mock.Mock())
    @mock.patch('treadmill.runtime.docker.runtime._create_container',
                mock.Mock())
    @mock.patch('treadmill.runtime.archive_logs', mock.Mock())
    @mock.patch('treadmill.presence.EndpointPresence',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    @mock.patch('treadmill.appcfg.abort.report_aborted', mock.Mock())
    @mock.patch('docker.from_env', mock.Mock())
    def test__finish_aborted(self):
        """Tests docker runtime finish when aborted."""
        # Access to a protected member
        # pylint: disable=W0212
        if os.name == 'nt':
            treadmill.ad.credential_spec.cleanup = mock.Mock()

        treadmill.runtime.save_app(self.manifest, self.data_dir)

        client = mock.MagicMock()
        docker.from_env.return_value = client

        container = mock.MagicMock()
        client.containers.get.return_value = container

        with io.open(os.path.join(self.data_dir, 'aborted'), 'w') as aborted:
            aborted.write('{"why": "reason", "payload": "test"}')

        docker_runtime = runtime.DockerRuntime(
            self.tm_env, self.container_dir, {'version': '1.24'}
        )

        docker_runtime._finish()

        app_abort.report_aborted.assert_called_with(
            self.tm_env, 'proid.app#001',
            why='reason',
            payload='test'
        )

        treadmill.runtime.archive_logs.assert_called()

    @mock.patch('treadmill.runtime.allocate_network_ports', mock.Mock())
    @mock.patch('treadmill.runtime.docker.runtime._create_container',
                mock.Mock())
    @mock.patch('treadmill.runtime.archive_logs', mock.Mock())
    @mock.patch('treadmill.presence.EndpointPresence',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    @mock.patch('treadmill.appcfg.abort.report_aborted', mock.Mock())
    @mock.patch('docker.from_env', mock.Mock())
    def test__finish_no_info(self):
        """Tests docker runtime finish when not aborted or exited."""
        # Access to a protected member
        # pylint: disable=W0212
        if os.name == 'nt':
            treadmill.ad.credential_spec.cleanup = mock.Mock()

        treadmill.runtime.save_app(self.manifest, self.data_dir)

        client = mock.MagicMock()
        docker.from_env.return_value = client

        container = mock.MagicMock()
        client.containers.get.return_value = container

        type(container).attrs = mock.PropertyMock(return_value={
            'State': None
        })

        docker_runtime = runtime.DockerRuntime(
            self.tm_env, self.container_dir, {'version': '1.24'}
        )

        # Should not throw any exception
        docker_runtime._finish()

        treadmill.runtime.archive_logs.assert_called()


if __name__ == '__main__':
    unittest.main()
