"""Unit test for higher level custom specialized ZK watching API's.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import threading

import kazoo.client
import kazoo.exceptions
import mock

from treadmill import zkwatchers

from treadmill.tests.testutils import mockzk


class ZkwatchersTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.zkwatchers."""

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_existing_data_watch(self):
        """Test ExistingDataWatch."""
        zk_content = {
            'foo': {
                '.data': 'foo_data',
                '.metadata': {'mzxid': 0},
            },
            'baz': {
                '.data': 'baz_data',
                '.metadata': {'mzxid': 0},
            },
        }
        self.make_mock_zk(zk_content, events=True)

        zkclient = kazoo.client.KazooClient()

        # Test using ExistingDataWatch as a class
        foo_func = mock.Mock()
        zkwatchers.ExistingDataWatch(zkclient, '/foo', foo_func)
        foo_func.assert_called_once_with('foo_data', mock.ANY, None)

        # Test using ExistingDataWatch on a non-existing node
        bar_func = mock.Mock()
        zkwatchers.ExistingDataWatch(zkclient, '/bar', bar_func)
        bar_func.assert_called_once_with(None, None, None)

        # Test using ExistingDataWatch as a decorator
        # Events are processed in separate thread, use Event object to wait
        baz_func = mock.Mock()
        baz_func_event = threading.Event()

        @zkwatchers.ExistingDataWatch(zkclient, '/baz')
        def _func(data, stat, event):
            baz_func(data, stat, event)
            baz_func_event.set()
        baz_func.assert_called_once_with('baz_data', mock.ANY, None)
        self.assertTrue(baz_func_event.is_set())

        foo_func.reset_mock()
        bar_func.reset_mock()
        baz_func.reset_mock()
        baz_func_event.clear()

        zk_content['foo']['.metadata']['mzxid'] = 1
        zk_content['baz']['.metadata']['mzxid'] = 1

        self.notify('DELETED', '/foo')
        self.notify('CHANGED', '/foo')  # DELETED is first, no watch
        self.notify('CREATED', '/bar')  # /bar did not exist, no watch
        self.notify('CHANGED', '/baz')

        # Wait for the last event to be processed before making assertions
        baz_func_event.wait(timeout=1)

        foo_func.assert_called_once_with(
            'foo_data', mock.ANY, ('CHANGED', 'CONNECTED', '/foo')
        )
        self.assertEqual(bar_func.call_count, 0)
        baz_func.assert_called_once_with(
            'baz_data', mock.ANY, ('CHANGED', 'CONNECTED', '/baz')
        )


if __name__ == '__main__':
    unittest.main()
