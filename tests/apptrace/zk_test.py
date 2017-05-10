"""Unit test for Treadmill ZK apptrace module.
"""

import unittest
import sqlite3

import mock
import kazoo
import kazoo.client

import treadmill
from treadmill.apptrace import zk

from tests.testutils import mockzk


class AppTraceZKTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.apptrace."""

    def setUp(self):
        super(AppTraceZKTest, self).setUp()

    def tearDown(self):
        super(AppTraceZKTest, self).tearDown()

    @mock.patch('kazoo.client.KazooClient', mock.Mock())
    @mock.patch('tempfile.NamedTemporaryFile', mock.MagicMock())
    @mock.patch('sqlite3.connect', mock.Mock())
    def test_task_db_add(self):
        """"Tests adding rows to task DB."""
        conn_mock = mock.Mock()
        cur_mock = mock.Mock()
        sqlite3.connect.return_value = conn_mock
        conn_mock.cursor.return_value = cur_mock

        zkclient = kazoo.client.KazooClient()
        task_db = zk.TaskDB(zkclient)
        uploaded = task_db.add([
            ('path1', 1, 'data1'),
            ('path2', 2, 'data2'),
        ])

        self.assertEquals(uploaded, False)
        cur_mock.execute.assert_called_once_with(
            '\n    create table tasks '
            '(path text, timestamp integer, data text)\n    '
        )
        cur_mock.executemany.assert_called_once_with(
            'insert into tasks values(?, ?, ?)',
            [('path1', 1, 'data1'), ('path2', 2, 'data2')]
        )
        conn_mock.commit.assert_called_once_with()
        self.assertEquals(zkclient.create.call_count, 0)

    @mock.patch('kazoo.client.KazooClient', mock.Mock())
    @mock.patch('tempfile.NamedTemporaryFile', mock.MagicMock())
    @mock.patch('sqlite3.connect', mock.Mock())
    @mock.patch('builtins.open', mock.mock_open(read_data=b'test'))
    @mock.patch('os.unlink', mock.Mock())
    def test_task_db_add_upload_size(self):
        """"Tests adding rows to task DB and uploading to ZK if enough rows."""
        conn_mock = mock.Mock()
        cur_mock = mock.Mock()
        sqlite3.connect.return_value = conn_mock
        conn_mock.cursor.return_value = cur_mock

        zkclient = kazoo.client.KazooClient()
        task_db = zk.TaskDB(zkclient)
        # Add 10000 rows, no uploading yet
        for i in range(10):
            self.assertEquals(
                task_db.add([('path', i, 'data')] * 1000),
                False
            )
        # Upload as we hit snapshot size threshold
        self.assertEquals(
            task_db.add([('path', 10, 'data')] * 1000),
            True
        )
        self.assertEquals(zkclient.create.call_count, 1)

    @mock.patch('kazoo.client.KazooClient', mock.Mock())
    @mock.patch('tempfile.NamedTemporaryFile', mock.MagicMock())
    @mock.patch('sqlite3.connect', mock.Mock())
    @mock.patch('builtins.open', mock.mock_open(read_data=b'test'))
    @mock.patch('os.unlink', mock.Mock())
    def test_task_db_add_upload_close(self):
        """"Tests adding rows to task DB and uploading to ZK on close."""
        conn_mock = mock.Mock()
        cur_mock = mock.Mock()
        sqlite3.connect.return_value = conn_mock
        conn_mock.cursor.return_value = cur_mock

        zkclient = kazoo.client.KazooClient()
        task_db = zk.TaskDB(zkclient)
        task_db.add([
            ('path1', 1, 'data1'),
            ('path2', 2, 'data2'),
        ], close=True)

        self.assertEquals(zkclient.create.call_count, 1)

    @mock.patch('kazoo.client.KazooClient', mock.Mock())
    @mock.patch('tempfile.NamedTemporaryFile', mock.MagicMock())
    @mock.patch('sqlite3.connect', mock.Mock())
    @mock.patch('builtins.open', mock.mock_open(read_data='test'))
    @mock.patch('os.unlink', mock.Mock())
    def test_task_db_add_close_empty(self):
        """"Tests closing empty task DB (should not upload anything)."""
        conn_mock = mock.Mock()
        cur_mock = mock.Mock()
        sqlite3.connect.return_value = conn_mock
        conn_mock.cursor.return_value = cur_mock

        zkclient = kazoo.client.KazooClient()
        task_db = zk.TaskDB(zkclient)
        task_db.add([], close=True)

        self.assertEquals(zkclient.create.call_count, 0)

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.apptrace.zk.TaskDB.add', mock.Mock())
    def test_tasks_cleanup(self):
        """"Tests tasks cleanup."""
        zk_content = {
            'scheduled': {
                'app1#0000000001': '',
                'app2#0000000338': '',
                'app2#0000000339': ''
            },
            'tasks': {
                'app1': {
                    '0000000001': {}
                },
                'app2': {
                    '0000000337': {
                        '.data': ("{data: '256.256', host: host,"
                                  " state: finished, when: '1.2'}\n"),
                        '.metadata': {
                            'last_modified': 2.2
                        },
                        '1.1,host,service_exited,abc0.test.0.0': '',
                        '1.2,host,finished,0.0': ''
                    },
                    '0000000338': {},
                    '0000000339': {},
                }
            },
            'tasks.history': {}
        }
        # Generate 335 finished tasks for app1 (this is > 1000 rows in total)
        for i in range(2, 337):
            zk_content['tasks']['app1']['%010d' % i] = {
                '.data': ("{data: '0.0', host: host,"
                          " state: finished, when: '1.2'}\n"),
                '.metadata': {
                    'last_modified': 2.2
                },
                '1.1,host,service_exited,abc0.test.0.0': '',
                '1.2,host,finished,0.0': ''
            }

        self.make_mock_zk(zk_content)
        zkclient = kazoo.client.KazooClient()

        zk.cleanup(zkclient)

        rows1 = []
        for i in range(2, 336):
            rows1.extend([
                ('/tasks/app1/%010d' % i, 2,
                 "{data: '0.0', host: host, state: finished, when: '1.2'}\n"),
                ('/tasks/app1/%010d/1.1,host,service_exited,abc0.test.0.0' % i,
                 1, None),
                ('/tasks/app1/%010d/1.2,host,finished,0.0' % i,
                 1, None)
            ])
        # Second commit, last finished app1 task and finished app2 task
        rows2 = [
            ('/tasks/app1/0000000336', 2,
             "{data: '0.0', host: host, state: finished, when: '1.2'}\n"),
            ('/tasks/app1/0000000336/1.1,host,service_exited,abc0.test.0.0',
             1, None),
            ('/tasks/app1/0000000336/1.2,host,finished,0.0',
             1, None),
            ('/tasks/app2/0000000337', 2,
             "{data: '256.256', host: host, state: finished, when: '1.2'}\n"),
            ('/tasks/app2/0000000337/1.1,host,service_exited,abc0.test.0.0',
             1, None),
            ('/tasks/app2/0000000337/1.2,host,finished,0.0',
             1, None)
        ]
        self.assertEquals(
            treadmill.apptrace.zk.TaskDB.add.call_args_list,
            [
                mock.call(rows1),
                mock.call(rows2, close=True)
            ]
        )
        self.assertEquals(zk_content, {
            'scheduled': {
                'app1#0000000001': '',
                'app2#0000000338': '',
                'app2#0000000339': ''
            },
            'tasks': {
                'app1': {
                    '0000000001': {}
                },
                'app2': {
                    '0000000338': {},
                    '0000000339': {}
                }
            },
            'tasks.history': {}
        })

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.apptrace.zk.TaskDB.add', mock.Mock())
    def test_tasks_history_cleanup(self):
        """"Tests tasks history cleanup."""
        zk_content = {
            'tasks': {},
            'tasks.history': dict(
                ('tasks.db.gzip-%010d' % i, '') for i in range(1, 1003)
            )
        }
        self.make_mock_zk(zk_content)
        zkclient = kazoo.client.KazooClient()

        zk.cleanup(zkclient)

        self.assertEquals(
            treadmill.zkutils.ensure_deleted.call_args_list,
            [
                mock.call(
                    zkclient, '/tasks.history/tasks.db.gzip-0000000001', False
                ),
                mock.call(
                    zkclient, '/tasks.history/tasks.db.gzip-0000000002', False
                )
            ]
        )

    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.apptrace.zk.TaskDB.add', mock.Mock())
    def test_no_tasks_history_cleanup(self):
        """"Tests tasks history cleanup when there is nothing to delete yet."""
        zk_content = {
            'tasks': {},
            'tasks.history': {
                'tasks.db.gzip-0000000001': ''
            }
        }
        self.make_mock_zk(zk_content)
        zkclient = kazoo.client.KazooClient()

        zk.cleanup(zkclient)

        self.assertEquals(treadmill.zkutils.ensure_deleted.call_count, 0)

    @mock.patch('kazoo.client.KazooClient', mock.Mock(spec_set=True))
    def test_wait_snapshot(self):
        """Tests that .wait() return True when not initialized."""
        zkclient = kazoo.client.KazooClient()
        trace = zk.AppTrace(zkclient, None, None)
        self.assertTrue(trace.wait())


if __name__ == '__main__':
    unittest.main()
