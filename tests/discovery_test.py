"""Unit test for appwatch.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from tests.testutils import mockzk

import kazoo
import kazoo.client
import mock

from treadmill import discovery


class DiscoveryTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.appwatch."""

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
        self.assertEqual('foo#*', app_discovery.pattern)

        app_discovery = discovery.Discovery(None, 'appproid.foo#1', 'http')
        self.assertEqual('foo#1', app_discovery.pattern)


if __name__ == '__main__':
    unittest.main()
