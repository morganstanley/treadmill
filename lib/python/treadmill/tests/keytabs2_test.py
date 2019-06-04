"""Unit test for keytabs2
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import base64
import os
import sqlite3
import shutil
import tempfile
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import keytabs2
from treadmill.keytabs2 import client as kt2_client
from treadmill.keytabs2 import locker as kt2_locker
from treadmill.keytabs2 import receiver as kt2_receiver


class Keytabs2Test(unittest.TestCase):
    """Tests for module teadmill.keytabs2"""

    def setUp(self):
        self.spool_dir = tempfile.mkdtemp()
        self.sqlite3_dir = tempfile.mkdtemp()
        self.database = os.path.join(self.sqlite3_dir, 'test.db')

    def tearDown(self):
        shutil.rmtree(self.spool_dir)
        shutil.rmtree(self.sqlite3_dir)

    @mock.patch('kazoo.client.KazooClient')
    @mock.patch('treadmill.discovery.iterator')
    @mock.patch('treadmill.gssapiprotocol.jsonclient.GSSAPIJsonClient')
    @mock.patch('treadmill.keytabs2.write_keytab')
    def test_request_keytabs(self, mock_write_keytab, mock_client_class,
                             mock_iterator, mock_zk):
        """Test request_keytabs"""
        os.environ['TREADMILL_ID'] = 'treadmill'
        app_name = 'proida.foo'
        spool_dir = self.spool_dir

        mock_iterator.return_value = [('foo:tcp:keytabs', '127.0.0.1:12345')]
        mock_json_client = mock.Mock()
        mock_client_class.return_value = mock_json_client

        # test connection error
        mock_json_client.connect.return_value = False

        with self.assertRaises(keytabs2.KeytabClientError):
            kt2_client.request_keytabs(mock_zk, app_name, spool_dir, 'foo')
        mock_json_client.connect.assert_called_once()

        # test server internal error
        mock_json_client.reset_mock()
        mock_json_client.connect.return_value = True
        mock_json_client.read_json.return_value = {
            'success': False,
            'message': 'ops..',
        }
        with self.assertRaises(keytabs2.KeytabClientError):
            kt2_client.request_keytabs(mock_zk, app_name, spool_dir, 'foo')
        mock_json_client.write_json.assert_called_once_with(
            {
                'action': 'get',
                'app': app_name,
            }
        )

        # test valid keytabs with arbitrary bytes
        keytab_1 = base64.b64encode(os.urandom(10))
        keytab_2 = base64.b64encode(os.urandom(10))
        mock_json_client.read_json.return_value = {
            'success': True,
            'keytabs': {
                'ktname_1': keytab_1,
                'ktname_2': keytab_2,
            },
        }
        kt2_client.request_keytabs(mock_zk, app_name, spool_dir, 'foo')
        mock_write_keytab.assert_has_calls(
            [
                mock.call(os.path.join(self.spool_dir, 'ktname_1'), keytab_1),
                mock.call(os.path.join(self.spool_dir, 'ktname_2'), keytab_2),
            ],
            any_order=True,
        )

    def test_compare_data(self):
        """test compare data
        """
        stored = []
        desired = [(1, 1), (2, 2)]

        # pylint: disable=protected-access
        (add, modify, delete) = kt2_receiver._compare_data(stored, desired)
        self.assertEqual(add, desired)
        self.assertEqual(modify, [])
        self.assertEqual(delete, [])

        stored = [(1, 1)]
        desired = [(1, 1), (2, 2)]
        (add, modify, delete) = kt2_receiver._compare_data(stored, desired)
        self.assertEqual(add, [(2, 2)])
        self.assertEqual(modify, [])
        self.assertEqual(delete, [])

        stored = [(2, 2), (3, 3)]
        desired = [(1, 1), (2, 3), (4, 4)]
        (add, modify, delete) = kt2_receiver._compare_data(stored, desired)
        self.assertEqual(add, [(1, 1), (4, 4)])
        self.assertEqual(modify, [(2, 3)])
        self.assertEqual(delete, [(3, 3)])

        stored = [(2, 2), (3, 3)]
        desired = [(1, 1), (2, 3)]
        (add, modify, delete) = kt2_receiver._compare_data(stored, desired)
        self.assertEqual(add, [(1, 1)])
        self.assertEqual(modify, [(2, 3)])
        self.assertEqual(delete, [(3, 3)])

    @mock.patch('pwd.getpwnam', mock.Mock())
    @mock.patch('os.chown', mock.Mock())
    def test_sync_relations(self):
        """Test sync_relations"""
        data = [
            ('proid1', 'vip1.com'),
            ('proid2', 'vip2.com'),
        ]

        receiver = kt2_receiver.KeytabReceiver(
            self.spool_dir, self.database, 'owner'
        )
        receiver.sync('owner', data)

        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        rows = cur.execute(
            'SELECT proid, vip FROM keytab_proid'
        ).fetchall()
        self.assertEqual(data, rows)

        data = [
            ('proid1', 'vip1.com'),
            ('proid3', 'vip2.com'),
            ('proid2', 'vip3.com'),
        ]
        receiver.sync('owner', data)

        cur = conn.cursor()
        rows = cur.execute(
            'SELECT proid, vip FROM keytab_proid order by vip'
        ).fetchall()
        self.assertEqual(data, rows)

        conn.close()

    @mock.patch('socket.gethostbyname', mock.Mock(return_value='192.168.1.1'))
    def test_translate_vip(self):
        """test translate keytab magic string to vip address
        """
        # pylint: disable=protected-access
        self.assertEqual('192.168.1.1',
                         kt2_locker._translate_vip('host#myhost@realm'))

        # test wrong keytab format
        with self.assertRaises(keytabs2.KeytabLockerError):
            kt2_locker._translate_vip('host#myhost#realm')

    @mock.patch('pwd.getpwnam', mock.Mock())
    @mock.patch('os.chown', mock.Mock())
    @mock.patch('treadmill.zkutils.with_retry',
                mock.Mock(return_value={'keytabs': ['vip1.com']}))
    @mock.patch('treadmill.keytabs2.locker._translate_vip',
                mock.Mock(side_effect=['192.168.1.1', '192.168.2.1']))
    def test_locker(self):
        """test locker method
        """
        locker = kt2_locker.KeytabLocker(
            self.spool_dir, self.database, mock.Mock()
        )
        with self.assertRaises(keytabs2.KeytabLockerError):
            # pylint: disable=protected-access
            locker._get_app_keytabs('foo/xxxx@xxx', 'foo.bar')

        data = [
            ('proid1', '192.168.1.1'),
            ('proid2', '192.168.1.2'),
        ]

        receiver = kt2_receiver.KeytabReceiver(
            self.spool_dir, self.database, 'owner'
        )
        receiver.sync('owner', data)

        # first test, vip 192.168.1.1 is in the db
        keytabs = locker.query('host/xxxx@xxx', 'proid1.xxx')
        self.assertEqual(['vip1.com'], keytabs)

        # second test, vip 192.168.2.1 is not in sqlite db
        with self.assertRaises(keytabs2.KeytabLockerError):
            locker.query('host/xxxx@xxx', 'proid1.yyy')


if __name__ == '__main__':
    unittest.main()
