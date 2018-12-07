"""Unit test for Treadmill ZK app trace module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import time
import sqlite3

import kazoo
import kazoo.client
import mock

import treadmill
from treadmill import zkutils
from treadmill.trace.app import zk

from treadmill.tests.testutils import mockzk


class AppTraceZKTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.trace.app.zk.
    """

    @mock.patch('treadmill.trace.app.zk._HOSTNAME', 'baz')
    def test_publish(self):
        """Test publishing app event to ZK."""
        zkclient_mock = mock.Mock()
        zkclient_mock.get_children.return_value = []

        zk.publish(
            zkclient_mock, '100', 'foo.bar#123', 'pending', 'created', ''
        )
        zkclient_mock.create.assert_called_once_with(
            '/trace/007B/foo.bar#123,100,baz,pending,created',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )
        zkclient_mock.reset_mock()

        zk.publish(
            zkclient_mock, '100', 'foo.bar#123', 'pending_delete', 'deleted',
            ''
        )
        zkclient_mock.create.assert_called_once_with(
            '/trace/007B/foo.bar#123,100,baz,pending_delete,deleted',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )
        zkclient_mock.reset_mock()

        zk.publish(
            zkclient_mock, '100', 'foo.bar#123', 'aborted', 'test', ''
        )
        zkclient_mock.create.assert_has_calls([
            mock.call(
                '/trace/007B/foo.bar#123,100,baz,aborted,test',
                b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            ),
            mock.call(
                '/finished/foo.bar#123',
                b'{data: test, host: baz, state: aborted, when: \'100\'}\n',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            )
        ])

    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.trace.app.zk._HOSTNAME', 'host_x')
    def test_unschedule(self):
        """Tests unschedule when server owns placement."""
        # Disable W0212: accessing protected members.
        # pylint: disable=W0212
        zk_content = {
            'placement': {
                'host_x': {
                    'app#1': {},
                },
                'host_y': {
                },
            },
            'scheduled': {
                'app#1': {
                },
            },
        }
        self.make_mock_zk(zk_content)

        zkclient = kazoo.client.KazooClient()
        zk._unschedule(zkclient, 'app#1')

        zkutils.ensure_deleted.assert_called_with(zkclient, '/scheduled/app#1')

    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.trace.app.zk._HOSTNAME', 'host_x')
    def test_unschedule_stale(self):
        """Tests unschedule when server does not own placement."""
        # Disable W0212: accessing protected members.
        # pylint: disable=W0212
        zk_content = {
            'placement': {
                'host_x': {
                },
                'host_y': {
                    'app#1': {},
                },
            },
            'scheduled': {
                'app#1': {
                },
            },
        }
        self.make_mock_zk(zk_content)

        zkclient = kazoo.client.KazooClient()
        zk._unschedule(zkclient, 'app#1')

        self.assertFalse(zkutils.ensure_deleted.called)

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_prune_trace_service_events(self):
        """Test pruning trace service events.
        """
        zk_content = {
            'trace': {
                '0001': {
                    'app1#001,1000.0,s1,service_running,uniq1.service1': {},
                    'app1#001,1001.0,s1,service_exited,uniq1.service1.0.0': {},
                    'app1#001,1002.0,s1,service_running,uniq1.service1': {},
                    'app1#001,1003.0,s1,service_exited,uniq1.service1.0.0': {},
                    'app1#001,1004.0,s1,service_running,uniq1.service1': {},
                    'app1#001,1005.0,s1,service_exited,uniq1.service1.0.0': {},
                    'app1#001,1006.0,s1,service_running,uniq1.service1': {},
                },
                '0002': {
                    'app1#002,1000.0,s1,service_running,uniq1.service1': {},
                    'app1#002,1001.0,s1,service_exited,uniq1.service1.0.0': {},
                    'app1#002,1002.0,s1,service_running,uniq1.service1': {},
                    'app1#002,1003.0,s1,service_exited,uniq1.service1.0.0': {},
                },
                '0003': {
                    'app1#003,1000.0,s1,service_running,uniq1.service1': {},
                    'app1#003,1001.0,s1,service_running,uniq1.service2': {},
                    'app1#003,1002.0,s1,service_running,uniq1.service3': {},
                    'app1#003,1003.0,s1,service_running,uniq1.service4': {},
                    'app1#003,1004.0,s1,service_running,uniq1.service5': {},
                },
                '0004': {
                    'app1#004,1000.0,s1,service_running,uniq1.service1': {},
                    'app1#004,1001.0,s2,service_running,uniq2.service1': {},
                    'app1#004,1002.0,s3,service_running,uniq3.service1': {},
                    'app1#004,1003.0,s4,service_running,uniq4.service1': {},
                    'app1#004,1004.0,s5,service_running,uniq5.service1': {},
                },
            },
        }

        self.make_mock_zk(zk_content)
        zkclient = treadmill.zkutils.ZkClient()

        zk.prune_trace_service_events(zkclient, 4)

        self.assertEqual(kazoo.client.KazooClient.delete.call_args_list, [
            mock.call('/trace/0001/'
                      'app1#001,1002.0,s1,service_running,uniq1.service1'),
            mock.call('/trace/0001/'
                      'app1#001,1001.0,s1,service_exited,uniq1.service1.0.0'),
            mock.call('/trace/0001/'
                      'app1#001,1000.0,s1,service_running,uniq1.service1'),
        ])

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_prune_trace_evictions(self):
        """Test pruning trace evictions.
        """
        zk_content = {
            'trace': {
                '0001': {
                    'app1#001,1000.0,s1,pending,monitor:created': {},
                    'app1#001,1001.0,s1,scheduled,host1': {},
                    'app1#001,1002.0,host1,configured,uniq1': {},
                    'app1#001,1003.0,host1,service_running,uniq1.service1': {},
                    'app1#001,1004.0,s1,pending,evicted': {},
                    'app1#001,1005.0,s1,scheduled,host2': {},
                    'app1#001,1006.0,host2,configured,uniq2': {},
                    'app1#001,1007.0,host2,service_running,uniq2.service1': {},
                    'app1#001,1008.0,s1,scheduled,host3:evicted': {},
                    'app1#001,1009.0,host3,configured,uniq3': {},
                    'app1#001,1010.0,host3,service_running,uniq3.service1': {},
                    'app1#001,1011.0,s1,pending,evicted': {},
                    'app1#001,1012.0,s1,scheduled,host4': {},
                    'app1#001,1013.0,host4,configured,uniq4': {},
                    'app1#001,1014.0,host4,service_running,uniq4.service1': {},
                    'app1#001,1015.0,s1,scheduled,host5:evicted': {},
                    'app1#001,1016.0,host5,configured,uniq5': {},
                    'app1#001,1017.0,host5,service_running,uniq5.service1': {},
                },
                '0002': {
                    'app1#002,1000.0,s1,pending,monitor:created': {},
                    'app1#002,1001.0,s1,scheduled,host1': {},
                    'app1#002,1002.0,host1,configured,uniq1': {},
                    'app1#002,1003.0,host1,service_running,uniq1.service1': {},
                },
            },
        }

        self.make_mock_zk(zk_content)
        zkclient = kazoo.client.KazooClient()

        zk.prune_trace_evictions(zkclient, 4)

        self.assertEqual(kazoo.client.KazooClient.delete.call_args_list, [
            mock.call('/trace/0001/'
                      'app1#001,1003.0,host1,service_running,uniq1.service1'),
            mock.call('/trace/0001/'
                      'app1#001,1002.0,host1,configured,uniq1'),
            mock.call('/trace/0001/'
                      'app1#001,1001.0,s1,scheduled,host1'),
        ])

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=1000))
    @mock.patch('sqlite3.connect', mock.Mock())
    def test_trace_cleanup(self):
        """Test trace cleanup.
        """
        zk_content = {
            'scheduled': {
                'app1#0003': {},
                'app1#0004': {},
            },
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
                '0003': {
                    'app1#0003,1000.00,s1,configured,2DqcoXnaIXEgy': {},
                    'app1#0003,1001.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0003,1003.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0003,1004.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0003,1005.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0003,1006.00,configured,2DqcoXnaIXEgy': {},
                },
                '0004': {
                    'app1#0004,1000.00,s1,configured,2DqcoXnaIXEgy': {},
                    'app1#0004,1001.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0004,1003.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0004,1004.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0004,1005.00,configured,2DqcoXnaIXEgy': {},
                    'app1#0004,1006.00,configured,2DqcoXnaIXEgy': {},
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
        zkclient = treadmill.zkutils.ZkClient()

        conn_mock = mock.MagicMock()
        sqlite3.connect.return_value = conn_mock

        # Current time - 1000, expiration - 3 seconds, there are < 10 events
        # that are expired, nothing is uploaded.
        zk.cleanup_trace(zkclient, 10, 3)
        self.assertEqual(0, len(zk_content['trace.history']))
        self.assertFalse(kazoo.client.KazooClient.create.called)

        # There are twelve expired events, expect batch to be uploaded.
        # Instances app1#0003 and 0004 are running and will not be included.
        time.time.return_value = 1100
        zk.cleanup_trace(zkclient, 10, 3)

        conn_mock.executemany.assert_called_once_with(
            """
            INSERT INTO trace (
                path, timestamp, data, directory, name
            ) VALUES(?, ?, ?, ?, ?)
            """,
            [
                ('/trace/0001/app1#0001,1000.00,s1,configured,2DqcoXnaIXEgy',
                 1000.0,
                 None,
                 '/trace/0001',
                 'app1#0001,1000.00,s1,configured,2DqcoXnaIXEgy'),
                ('/trace/0002/app1#0002,1000.00,s1,configured,2DqcoXnaIXEgy',
                 1000.0,
                 None,
                 '/trace/0002',
                 'app1#0002,1000.00,s1,configured,2DqcoXnaIXEgy'),
                ('/trace/0001/app1#0001,1001.00,configured,2DqcoXnaIXEgy',
                 1001.0,
                 None,
                 '/trace/0001',
                 'app1#0001,1001.00,configured,2DqcoXnaIXEgy'),
                ('/trace/0002/app1#0002,1001.00,configured,2DqcoXnaIXEgy',
                 1001.0,
                 None,
                 '/trace/0002',
                 'app1#0002,1001.00,configured,2DqcoXnaIXEgy'),
                ('/trace/0001/app1#0001,1003.00,configured,2DqcoXnaIXEgy',
                 1003.0,
                 None,
                 '/trace/0001',
                 'app1#0001,1003.00,configured,2DqcoXnaIXEgy'),
                ('/trace/0002/app1#0002,1003.00,configured,2DqcoXnaIXEgy',
                 1003.0,
                 None,
                 '/trace/0002',
                 'app1#0002,1003.00,configured,2DqcoXnaIXEgy'),
                ('/trace/0001/app1#0001,1004.00,configured,2DqcoXnaIXEgy',
                 1004.0,
                 None,
                 '/trace/0001',
                 'app1#0001,1004.00,configured,2DqcoXnaIXEgy'),
                ('/trace/0002/app1#0002,1004.00,configured,2DqcoXnaIXEgy',
                 1004.0,
                 None,
                 '/trace/0002',
                 'app1#0002,1004.00,configured,2DqcoXnaIXEgy'),
                ('/trace/0001/app1#0001,1005.00,configured,2DqcoXnaIXEgy',
                 1005.0,
                 None,
                 '/trace/0001',
                 'app1#0001,1005.00,configured,2DqcoXnaIXEgy'),
                ('/trace/0002/app1#0002,1005.00,configured,2DqcoXnaIXEgy',
                 1005.0,
                 None,
                 '/trace/0002',
                 'app1#0002,1005.00,configured,2DqcoXnaIXEgy')
            ]
        )

        kazoo.client.KazooClient.create.assert_called_with(
            '/trace.history/trace.db.gzip-',
            value=mock.ANY,
            acl=mock.ANY,
            makepath=True, ephemeral=False, sequence=True,
        )

        self.assertEqual(10, kazoo.client.KazooClient.delete.call_count)
        self.assertEqual(kazoo.client.KazooClient.delete.call_args_list, [
            (('/trace/0001/app1#0001,1000.00,s1,configured,2DqcoXnaIXEgy',),),
            (('/trace/0002/app1#0002,1000.00,s1,configured,2DqcoXnaIXEgy',),),
            (('/trace/0001/app1#0001,1001.00,configured,2DqcoXnaIXEgy',),),
            (('/trace/0002/app1#0002,1001.00,configured,2DqcoXnaIXEgy',),),
            (('/trace/0001/app1#0001,1003.00,configured,2DqcoXnaIXEgy',),),
            (('/trace/0002/app1#0002,1003.00,configured,2DqcoXnaIXEgy',),),
            (('/trace/0001/app1#0001,1004.00,configured,2DqcoXnaIXEgy',),),
            (('/trace/0002/app1#0002,1004.00,configured,2DqcoXnaIXEgy',),),
            (('/trace/0001/app1#0001,1005.00,configured,2DqcoXnaIXEgy',),),
            (('/trace/0002/app1#0002,1005.00,configured,2DqcoXnaIXEgy',),),
        ])

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=1000))
    @mock.patch('sqlite3.connect', mock.Mock())
    def test_finished_cleanup(self):
        """Test finished cleanup.
        """
        data = b"{data: '1.0', host: foo, state: finished, when: '123.45'}\n"
        zk_content = {
            'trace': {
                '0001': {
                },
                '0002': {
                },
            },
            'finished': {
                'app1#0001': {'.metadata': {'last_modified': 1000},
                              '.data': data},
                'app1#0002': {'.metadata': {'last_modified': 1000},
                              '.data': data},
                'app1#0003': {'.metadata': {'last_modified': 1000},
                              '.data': data},
                'app1#0004': {'.metadata': {'last_modified': 1000},
                              '.data': data},
                'app1#0005': {'.metadata': {'last_modified': 1000},
                              '.data': data},
                'app1#0006': {'.metadata': {'last_modified': 1000},
                              '.data': data},
                'app1#0007': {'.metadata': {'last_modified': 1000},
                              '.data': data},
            },
            'trace.history': {
            },
            'finished.history': {
            },
        }

        self.make_mock_zk(zk_content)
        zkclient = treadmill.zkutils.ZkClient()

        conn_mock = mock.MagicMock()
        sqlite3.connect.return_value = conn_mock

        zk.cleanup_finished(zkclient, 10, 3)
        self.assertFalse(kazoo.client.KazooClient.create.called)

        # Current time - 1000, expiration - 3 seconds, there are < 10 events
        # that are expired, nothing is uploaded.

        self.assertEqual(0, len(zk_content['finished.history']))

        time.time.return_value = 1100
        # There are twelve expired events, expect batch to be uploaded
        zk.cleanup_finished(zkclient, 5, 3)

        conn_mock.executemany.assert_called_once_with(
            """
            INSERT INTO finished (
                path, timestamp, data, directory, name
            ) VALUES(?, ?, ?, ?, ?)
            """,
            [
                ('/finished/app1#0001', 1000.0,
                 "{data: '1.0', host: foo, state: finished, when: '123.45'}\n",
                 '/finished', 'app1#0001'),
                ('/finished/app1#0002', 1000.0,
                 "{data: '1.0', host: foo, state: finished, when: '123.45'}\n",
                 '/finished', 'app1#0002'),
                ('/finished/app1#0003', 1000.0,
                 "{data: '1.0', host: foo, state: finished, when: '123.45'}\n",
                 '/finished', 'app1#0003'),
                ('/finished/app1#0004', 1000.0,
                 "{data: '1.0', host: foo, state: finished, when: '123.45'}\n",
                 '/finished', 'app1#0004'),
                ('/finished/app1#0005', 1000.0,
                 "{data: '1.0', host: foo, state: finished, when: '123.45'}\n",
                 '/finished', 'app1#0005')
            ]
        )

        kazoo.client.KazooClient.create.assert_called_with(
            '/finished.history/finished.db.gzip-',
            value=mock.ANY,
            acl=mock.ANY,
            makepath=True, ephemeral=False, sequence=True,
        )

        self.assertEqual(5, kazoo.client.KazooClient.delete.call_count)

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_trace_history_cleanup(self):
        """Test trace history cleanup.
        """
        zk_content = {
            'trace.history': {
                'trace.db.gzip-0000000000': {},
                'trace.db.gzip-0000000001': {},
                'trace.db.gzip-0000000002': {},
                'trace.db.gzip-0000000003': {},
                'trace.db.gzip-0000000004': {},
            },
        }

        self.make_mock_zk(zk_content)
        zkclient = treadmill.zkutils.ZkClient()

        # There are < 10 snapshots, nothing is deleted.
        zk.cleanup_trace_history(zkclient, 10)
        self.assertEqual(5, len(zk_content['trace.history']))
        self.assertFalse(kazoo.client.KazooClient.delete.called)

        # Expect 2 oldest snapshots to be deleted.
        zk.cleanup_trace_history(zkclient, 3)
        self.assertEqual(3, len(zk_content['trace.history']))
        self.assertEqual(kazoo.client.KazooClient.delete.call_args_list, [
            (('/trace.history/trace.db.gzip-0000000000',),),
            (('/trace.history/trace.db.gzip-0000000001',),),
        ])


if __name__ == '__main__':
    unittest.main()
