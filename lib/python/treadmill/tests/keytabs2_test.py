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

from treadmill import fs
from treadmill import keytabs2


class Keytabs2Test(unittest.TestCase):
    """Tests for module teadmill.keytabs2"""

    def setUp(self):
        self.spool_dir = tempfile.mkdtemp()
        self.sqlite3_dir = tempfile.mkdtemp()
        self.database = os.path.join(self.sqlite3_dir, 'test.db')

    def tearDown(self):
        shutil.rmtree(self.spool_dir)

    @mock.patch('kazoo.client.KazooClient')
    @mock.patch('treadmill.discovery.iterator')
    @mock.patch('treadmill.gssapiprotocol.jsonclient.GSSAPIJsonClient')
    @mock.patch('treadmill.keytabs2._write_keytab')
    def test_request_keytabs(self, mock_write_keytab, mock_client_class,
                             mock_iterator, mock_zkclient):
        """Test request_keytabs"""
        os.environ['TREADMILL_ID'] = 'treadmill'
        proid = 'proida'
        vips = ['host1.com', 'host2.com']
        spool_dir = self.spool_dir

        mock_iterator.return_value = [('foo:tcp:keytabs', '127.0.0.1:12345')]
        mock_json_client = mock.Mock()
        mock_client_class.return_value = mock_json_client

        # test connection error
        mock_json_client.connect.return_value = False
        self.assertFalse(
            keytabs2.request_keytabs(mock_zkclient, proid, vips, spool_dir)
        )
        mock_json_client.connect.assert_called_once()

        # test server internal error
        mock_json_client.reset_mock()
        mock_json_client.connect.return_value = True
        mock_json_client.read_json.return_value = {
            'success': False,
            'message': 'ops..',
        }
        self.assertFalse(
            keytabs2.request_keytabs(mock_zkclient, proid, vips, spool_dir)
        )
        mock_json_client.write_json.assert_called_once_with(
            {
                'action': 'get',
                'proid': proid,
                'vips': vips,
            }
        )

        # test valid keytabs with arbitrary bytes
        keytab_1 = os.urandom(10)
        keytab_2 = os.urandom(10)
        mock_json_client.read_json.return_value = {
            'success': True,
            'keytabs': {
                'ktname_1': base64.b64encode(keytab_1),
                'ktname_2': base64.b64encode(keytab_2),
            },
        }
        self.assertTrue(
            keytabs2.request_keytabs(mock_zkclient, proid, vips, spool_dir)
        )
        mock_write_keytab.assert_has_calls(
            [
                mock.call(os.path.join(self.spool_dir, 'ktname_1'), keytab_1),
                mock.call(os.path.join(self.spool_dir, 'ktname_2'), keytab_2),
            ],
            any_order=True,
        )

    def test_sync_relations(self):
        """Test sync_relations"""
        fs.mkfile_safe(os.path.join(self.spool_dir, 'princ#vip1.com@realm'))
        fs.mkfile_safe(os.path.join(self.spool_dir, 'princ#vip2.com@realm'))

        data = {
            'princ#vip1.com@realm': 'proid1',
            'princ#vip2.com@realm': 'proid2',
        }

        def find_proid(ktname):
            """Peuso proid lookup func"""
            return data[ktname]

        keytabs2.ensure_table_exists(self.database)
        keytabs2.sync_relations(self.spool_dir, self.database, find_proid)

        conn = sqlite3.connect(self.database)
        cur = conn.cursor()
        rows = cur.execute('SELECT keytab, proid FROM keytab_proid_relations')
        try:
            self.assertEqual(data, dict(rows))
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
