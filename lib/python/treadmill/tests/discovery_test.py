"""Unit test for appwatch.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import kazoo
import kazoo.client
import mock

from treadmill import discovery
from treadmill import zknamespace as z

from treadmill.tests.testutils import mockzk


class DiscoveryTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.appwatch."""

    # W0212(protected-access): Access to a protected member of a client class
    # pylint: disable=W0212

    @mock.patch('treadmill.zkutils.connect', mock.Mock(
        return_value=kazoo.client.KazooClient()))
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock(
        return_value=('xxx:111', None)))
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('treadmill.utils.rootdir', mock.Mock(return_value='/some'))
    def test_sync(self):
        """Checks event processing and state sync."""
        zkclient = kazoo.client.KazooClient()
        app_discovery = discovery.Discovery(zkclient, 'appproid.foo.*', 'http')

        kazoo.client.KazooClient.get_children.return_value = [
            'foo.1#0:tcp:http',
            'foo.2#0:tcp:http',
            'foo.2#0:tcp:tcp',
            'bar.1#0:tcp:http'
        ]

        kazoo.client.KazooClient.get.return_value = (b'xxx:123', None)

        # Need to call sync first, then put 'exit' on the queue to terminate
        # the loop.
        #
        # Calling run will drain event queue and populate state.
        app_discovery.sync()
        kazoo.client.KazooClient.get_children.assert_called_with(
            '/endpoints/appproid', watch=mock.ANY)
        app_discovery.exit_loop()

        expected = {}
        for (endpoint, hostport) in app_discovery.iteritems():
            expected[endpoint] = hostport

        self.assertEqual(
            expected,
            {
                'appproid.foo.1#0:tcp:http': 'xxx:123',
                'appproid.foo.2#0:tcp:http': 'xxx:123'
            }
        )

    @mock.patch('treadmill.zkutils.connect', mock.Mock(
        return_value=kazoo.client.KazooClient()))
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock(
        return_value=('xxx:111', None)))
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock(
        side_effect=kazoo.exceptions.NoNodeError))
    @mock.patch('treadmill.utils.rootdir', mock.Mock(return_value='/some'))
    def test_noexists(self):
        """Check that discovery establishes watch for non-existing proid."""
        zkclient = kazoo.client.KazooClient()
        app_discovery = discovery.Discovery(zkclient, 'appproid.foo.*', 'http')
        app_discovery.sync()
        kazoo.client.KazooClient.exists.assert_called_with(
            '/endpoints/appproid', watch=mock.ANY)

    def test_pattern(self):
        """Checks instance aware pattern construction."""
        app_discovery = discovery.Discovery(None, 'appproid.foo', 'http')
        self.assertEqual(['appproid.foo#*'], app_discovery.patterns)

        app_discovery = discovery.Discovery(None, 'appproid.foo#1', 'http')
        self.assertEqual(['appproid.foo#1'], app_discovery.patterns)

    def test_snapshot(self):
        """Checks that snapshot is just a copy of the internal state."""
        app_discovery = discovery.Discovery(None, 'appproid.foo.*', 'http')
        app_discovery.state.add('foo')
        snapshot = app_discovery.snapshot()
        self.assertFalse(snapshot == app_discovery.state)
        self.assertEqual(set(snapshot), app_discovery.state)

    def test_prefixes(self):
        """Dummy _prefixes() test."""
        app_discovery = discovery.Discovery(
            None, ['appproid.foo*', 'fooproid.bar*'], '*'
        )
        self.assertEqual(
            app_discovery._prefixes(), set(('appproid', 'fooproid'))
        )

    def test_matching_endpoints(self):
        """_matching_endpoints()"""
        app_discovery = discovery.Discovery(
            None, ['proid_A.kafka*', 'proid_B.zookeeper*'], '*'
        )
        endpoints = []
        self.assertEqual(app_discovery._matching_endpoints(endpoints), set(()))
        endpoints = [
            discovery._join_prefix('proid_A', endpoint) for endpoint in [
                'kafka#111:tcp:http', 'kafka#111:tcp:kafka_cluster_comm',
                'other#222:tcp:foo', 'asdf#333:tcp:bar',
            ]
        ]
        endpoints.extend(
            [
                discovery._join_prefix('proid_B', endpoint) for endpoint in [
                    'zookeeper#444:tcp:zk_listener', 'zookeeper#444:tcp:http',
                    'xzy#555:tcp:http'
                ]
            ]
        )
        self.assertEqual(
            app_discovery._matching_endpoints(endpoints),
            set(
                (
                    'proid_A.kafka#111:tcp:http',
                    'proid_A.kafka#111:tcp:kafka_cluster_comm',
                    'proid_B.zookeeper#444:tcp:http',
                    'proid_B.zookeeper#444:tcp:zk_listener',
                )
            )
        )

    @mock.patch(
        'treadmill.zkutils.connect',
        mock.Mock(return_value=kazoo.client.KazooClient())
    )
    def test_get_endpoints_zk(self):
        """get_endpoints_zk(); get_endpoints()"""
        zkclient = mock.Mock()
        zkclient.get_children.return_value = [
            'foo.1#0:tcp:http', 'foo.2#0:tcp:http', 'foo.1#0:tcp:tcp',
            'bar.3#0:tcp:http'
        ]

        app_discovery = discovery.Discovery(
            zkclient, ['proid_A.foo.1*', 'proid_B.bar.3*'], '*'
        )

        self.assertEqual(
            app_discovery.get_endpoints_zk(),
            set(
                (
                    'proid_A.foo.1#0:tcp:http', 'proid_A.foo.1#0:tcp:tcp',
                    'proid_B.bar.3#0:tcp:http'
                )
            )
        )

        # Test get_endpoints()
        def zk_get(fullpath):
            """Mock the zkclient.get() method."""
            if fullpath.startswith(
                    z.join_zookeeper_path(z.ENDPOINTS, 'proid_A', 'foo')
            ):
                return (b'xxx:123', None)
            elif fullpath.startswith(
                    z.join_zookeeper_path(z.ENDPOINTS, 'proid_B', 'bar')
            ):
                return (b'yyy:987', None)
            else:
                raise ValueError(fullpath)

        zkclient.get = zk_get
        self.assertEqual(
            set(app_discovery.get_endpoints()),
            set(('xxx:123', 'xxx:123', 'yyy:987'))
        )


if __name__ == '__main__':
    unittest.main()
