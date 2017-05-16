"""
Unit test for Treadmill ZK apptrace module.
"""

import unittest
import time

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611
from tests.testutils import mockzk

import mock
import kazoo
import kazoo.client

from treadmill.apptrace import zk


class AppTraceZKTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.apptrace."""

    def setUp(self):
        super(AppTraceZKTest, self).setUp()

    def tearDown(self):
        super(AppTraceZKTest, self).tearDown()

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=1000))
    def test_trace_cleanup(self):
        """"Tests tasks cleanup."""
        zk_content = {
            'trace': {
                '0001': {
                    'app1#0001,1000.00,s1,configured,2DqcoXnaIXEgy': {},
                    'app1#0001,1001.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0001,1003.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0001,1004.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0001,1005.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0001,1006.00,configured,2DqcoXnaIXEgy': {},
                },
                '0002': {
                    'app1#0002,1000.00,s1,configured,2DqcoXnaIXEgy': {},
                    'app1#0002,1001.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0002,1003.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0002,1004.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0002,1005.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0002,1006.00,configured,2DqcoXnaIXEgy': {},
                },
            },
            'finished': {
            },
            'trace.history': {
            },
            'finished.history': {
            },
        }

        self.make_mock_zk(zk_content)
        zkclient = kazoo.client.KazooClient()

        zk.cleanup_trace(zkclient, 10, 3)
        self.assertFalse(kazoo.client.KazooClient.create.called)

        # Current time - 1000, expiration - 3 seconds, there are < 10 events
        # that are expired, nothing is uploaded.

        self.assertEqual(0, len(zk_content['trace.history']))

        time.time.return_value = 1100
        # There are twelve expired events, expect batch to be uploaded
        zk.cleanup_trace(zkclient, 10, 3)
        kazoo.client.KazooClient.create.assert_called_with(
            '/trace.history/trace.db.gzip-',
            mock.ANY,
            acl=mock.ANY,
            makepath=True, ephemeral=False, sequence=True,
        )

        self.assertEqual(10, kazoo.client.KazooClient.delete.call_count)

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=1000))
    def test_finished_cleanup(self):
        """"Tests tasks cleanup."""
        zk_content = {
            'trace': {
                '0001': {
                },
                '0002': {
                },
            },
            'finished': {
                'app1#0001': {'.metadata': {'last_modified': 1000}},
                'app1#0002': {'.metadata': {'last_modified': 1000}},
                'app1#0003': {'.metadata': {'last_modified': 1000}},
                'app1#0004': {'.metadata': {'last_modified': 1000}},
                'app1#0005': {'.metadata': {'last_modified': 1000}},
                'app1#0006': {'.metadata': {'last_modified': 1000}},
                'app1#0007': {'.metadata': {'last_modified': 1000}},
            },
            'trace.history': {
            },
            'finished.history': {
            },
        }

        self.make_mock_zk(zk_content)
        zkclient = kazoo.client.KazooClient()

        zk.cleanup_finished(zkclient, 10, 3)
        self.assertFalse(kazoo.client.KazooClient.create.called)

        # Current time - 1000, expiration - 3 seconds, there are < 10 events
        # that are expired, nothing is uploaded.

        self.assertEqual(0, len(zk_content['finished.history']))

        time.time.return_value = 1100
        # There are twelve expired events, expect batch to be uploaded
        zk.cleanup_finished(zkclient, 5, 3)
        kazoo.client.KazooClient.create.assert_called_with(
            '/finished.history/finished.db.gzip-',
            mock.ANY,
            acl=mock.ANY,
            makepath=True, ephemeral=False, sequence=True,
        )

        self.assertEqual(5, kazoo.client.KazooClient.delete.call_count)


if __name__ == '__main__':
    unittest.main()
