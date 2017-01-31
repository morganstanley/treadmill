"""
Unit test for Treadmill ZK apptrace module.
"""

import time
import unittest

import mock
import kazoo
import kazoo.client

from treadmill.apptrace import zk
from treadmill.test import mockzk


class MockStat(object):
    """Mock ZnodeStat for convinience."""

    def __init__(self, created, modified=None):
        self.created = created
        self.ctime = self.created * 1000
        if modified:
            self.last_modified = modified
        else:
            self.last_modified = created
        self.mtime = self.last_modified * 1000


class AppTraceZKTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.apptrace."""

    def setUp(self):
        super(AppTraceZKTest, self).setUp()

    def tearDown(self):
        super(AppTraceZKTest, self).tearDown()

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_task_cleanup(self):
        """"Tests expired tasks removal."""
        zk_content = {
            'scheduled': {
                'app1#003': '',
            },
            'tasks': {
                'app1': {
                    '001': {
                        # Old task, to be removed.
                        'xxx-001': {
                            '.metadata': {
                                'last_modified': time.time() - 101
                            }
                        },
                        'yyy-002': {
                            '.metadata': {
                                'last_modified': time.time() - 101
                            }
                        },
                    },
                    # Task still active, as not all subnodes expired.
                    '002': {
                        'xxx-001': {
                            '.metadata': {
                                'last_modified': time.time() - 101
                            }
                        },
                        'yyy-002': {
                            '.metadata': {
                                'last_modified': time.time() - 10
                            }
                        }
                    },
                    # Active task is not evaluated.
                    '003': {
                    }
                },
            }
        }

        self.make_mock_zk(zk_content)
        zkclient = kazoo.client.KazooClient()

        zk.cleanup(zkclient, 100, max_events=1)

        kazoo.client.KazooClient.delete.assert_has_calls(
            [
                # 002 task has > 1 event, extra will be removed.
                mock.call('/tasks/app1/002/xxx-001'),
                # 001 task has > 1 event, extra will be removed.
                mock.call('/tasks/app1/001/xxx-001'),
                # 001 task is expired, recursive delete.
                mock.call('/tasks/app1/001', recursive=True),
                # try to delete (and fail as not empty)
                mock.call('/tasks/app1'),
            ],
            any_order=True
        )

    @mock.patch('kazoo.client.KazooClient', mock.Mock(spec_set=True))
    def test_wait_snapshot(self):
        """Tests that .wait() return True when not initialized."""
        zkclient = kazoo.client.KazooClient()
        trace = zk.AppTrace(zkclient, None, None)
        self.assertTrue(trace.wait())


if __name__ == '__main__':
    unittest.main()
