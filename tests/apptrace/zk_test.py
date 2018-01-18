"""Unit test for Treadmill ZK apptrace module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import time
import sqlite3

import mock
import kazoo
import kazoo.client

from treadmill.apptrace import zk

from tests.testutils import mockzk


class AppTraceZKTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.apptrace.
    """

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_trace_pruning(self):
        """Tests trace pruning.
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
        zkclient = kazoo.client.KazooClient()

        zk.prune_trace(zkclient, 4)

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
    @mock.patch('time.time', mock.Mock(return_value=1000))
    @mock.patch('sqlite3.connect', mock.Mock())
    def test_trace_cleanup(self):
        """Tests tasks cleanup.
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
        zkclient = kazoo.client.KazooClient()

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
            mock.ANY,
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
        """Tests tasks cleanup.
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
        zkclient = kazoo.client.KazooClient()

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
            mock.ANY,
            acl=mock.ANY,
            makepath=True, ephemeral=False, sequence=True,
        )

        self.assertEqual(5, kazoo.client.KazooClient.delete.call_count)


if __name__ == '__main__':
    unittest.main()
