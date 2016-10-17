"""
Unit test for Treadmill presense module.
"""

import time
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock
import kazoo
import kazoo.client

from treadmill import apptrace
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


class AppTraceTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.apptrace."""

    def setUp(self):
        super(AppTraceTest, self).setUp()

    def tearDown(self):
        super(AppTraceTest, self).tearDown()

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

        apptrace.cleanup(zkclient, 100, max_events=1)

        kazoo.client.KazooClient.delete.assert_has_calls([
            # 002 task has > 1 event, extra will be removed.
            mock.call('/tasks/app1/002/xxx-001'),
            # 001 task has > 1 event, extra will be removed.
            mock.call('/tasks/app1/001/xxx-001'),
            # 001 task is expired, recursive delete.
            mock.call('/tasks/app1/001', recursive=True),
            # try to delete (and fail as not empty)
            mock.call('/tasks/app1'),
        ])

    def test_wait_snapshot(self):
        """Tests that .wait() return True when not initialized."""
        trace = apptrace.AppTrace(None, None, None)
        self.assertTrue(trace.wait())


if __name__ == '__main__':
    unittest.main()
