"""Unit test for Treadmill ZK server trace module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import sqlite3

import kazoo
import kazoo.client
import mock

import treadmill
from treadmill.trace.server import zk

from treadmill.tests.testutils import mockzk


class ServerTraceZKTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.trace.server.zk.
    """

    @mock.patch('treadmill.trace.server.zk._HOSTNAME', 'tests')
    def test_publish(self):
        """Test publishing server event to ZK."""
        zkclient_mock = mock.Mock()

        zk.publish(
            zkclient_mock, '1000.00', 'test1.xx.com', 'server_state', 'up', ''
        )
        zkclient_mock.create.assert_called_once_with(
            '/server-trace/002F/test1.xx.com,1000.00,tests,server_state,up',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )
        zkclient_mock.reset_mock()

        zk.publish(
            zkclient_mock, '1001.00', 'test2.xx.com', 'server_blackout', '', ''
        )
        zkclient_mock.create.assert_called_once_with(
            '/server-trace/005B/test2.xx.com,1001.00,tests,server_blackout,',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('sqlite3.connect', mock.Mock())
    def test_server_trace_cleanup(self):
        """Test server trace cleanup.
        """
        zk_content = {
            'server-trace': {
                '0001': {
                    'test1.xx.com,1000.00,tests,server_state,up': {},
                    'test1.xx.com,1001.00,tests,server_state,down': {},
                    'test1.xx.com,1002.00,tests,server_state,up': {},
                },
                '0002': {
                    'test2.xx.com,1000.00,tests,server_state,up': {},
                    'test2.xx.com,1001.00,tests,server_state,down': {},
                },
            },
            'server-trace.history': {
            },
        }

        self.make_mock_zk(zk_content)
        zkclient = treadmill.zkutils.ZkClient()

        conn_mock = mock.MagicMock()
        sqlite3.connect.return_value = conn_mock

        # There are < 10 events, nothing is uploaded.
        zk.cleanup_server_trace(zkclient, 10)
        self.assertEqual(0, len(zk_content['server-trace.history']))
        self.assertFalse(kazoo.client.KazooClient.create.called)

        # Expect batch to be uploaded.
        zk.cleanup_server_trace(zkclient, 3)

        conn_mock.executemany.assert_called_once_with(
            """
            INSERT INTO server_trace (
                path, timestamp, data, directory, name
            ) VALUES(?, ?, ?, ?, ?)
            """,
            [
                ('/server-trace/0001/'
                 'test1.xx.com,1000.00,tests,server_state,up',
                 1000.0,
                 None,
                 '/server-trace/0001',
                 'test1.xx.com,1000.00,tests,server_state,up'),
                ('/server-trace/0002/'
                 'test2.xx.com,1000.00,tests,server_state,up',
                 1000.0,
                 None,
                 '/server-trace/0002',
                 'test2.xx.com,1000.00,tests,server_state,up'),
                ('/server-trace/0001/'
                 'test1.xx.com,1001.00,tests,server_state,down',
                 1001.0,
                 None,
                 '/server-trace/0001',
                 'test1.xx.com,1001.00,tests,server_state,down'),
            ]
        )

        kazoo.client.KazooClient.create.assert_called_with(
            '/server-trace.history/server_trace.db.gzip-',
            value=mock.ANY,
            acl=mock.ANY,
            makepath=True, ephemeral=False, sequence=True,
        )

        self.assertEqual(kazoo.client.KazooClient.delete.call_args_list, [
            (('/server-trace/0001/'
              'test1.xx.com,1000.00,tests,server_state,up',),),
            (('/server-trace/0002/'
              'test2.xx.com,1000.00,tests,server_state,up',),),
            (('/server-trace/0001/'
              'test1.xx.com,1001.00,tests,server_state,down',),),
        ])

    # Disable C0103(Invalid method name)
    # pylint: disable=C0103
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_server_trace_history_cleanup(self):
        """Test server trace history cleanup.
        """
        zk_content = {
            'server-trace.history': {
                'server_trace.db.gzip-0000000000': {},
                'server_trace.db.gzip-0000000001': {},
                'server_trace.db.gzip-0000000002': {},
                'server_trace.db.gzip-0000000003': {},
                'server_trace.db.gzip-0000000004': {},
            },
        }

        self.make_mock_zk(zk_content)
        zkclient = treadmill.zkutils.ZkClient()

        # There are < 10 snapshots, nothing is deleted.
        zk.cleanup_server_trace_history(zkclient, 10)
        self.assertEqual(5, len(zk_content['server-trace.history']))
        self.assertFalse(kazoo.client.KazooClient.delete.called)

        # Expect 2 oldest snapshots to be deleted.
        zk.cleanup_server_trace_history(zkclient, 3)
        self.assertEqual(3, len(zk_content['server-trace.history']))
        self.assertEqual(kazoo.client.KazooClient.delete.call_args_list, [
            (('/server-trace.history/server_trace.db.gzip-0000000000',),),
            (('/server-trace.history/server_trace.db.gzip-0000000001',),),
        ])


if __name__ == '__main__':
    unittest.main()
