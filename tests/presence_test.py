"""Unit test for Treadmill linux runtime presence module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import time
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611
from tests.testutils import mockzk

import mock
import kazoo
import kazoo.client

import treadmill
from treadmill import exc
from treadmill import presence


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


if __name__ == '__main__':
    unittest.main()
