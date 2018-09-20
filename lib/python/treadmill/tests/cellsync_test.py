"""Unit test for cellsync.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import os
import sqlite3
import tempfile

import kazoo
import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import cellsync
from treadmill import zkutils


class CellsyncTest(unittest.TestCase):
    """Test treadmill.cellsync"""

    @mock.patch('treadmill.context.GLOBAL', mock.Mock(cell='test'))
    def test_sync_collection(self):
        """"Test syncing ldap collection to Zookeeper."""
        # pylint: disable=protected-access

        zkclient = mock.Mock()
        zkclient.get_children.side_effect = lambda path: {
            '/app-groups': ['test.foo', 'test.bar', 'test.baz']
        }.get(path, [])

        entities = [
            {'_id': 'test.foo', 'cells': ['test']},
            {'_id': 'test.bar', 'cells': []},
        ]

        cellsync._sync_collection(zkclient, entities, '/app-groups',
                                  match=cellsync._match_appgroup)

        zkclient.delete.assert_has_calls([
            mock.call('/app-groups/test.bar'),
            mock.call('/app-groups/test.baz')
        ], any_order=True)
        zkclient.create.assert_called_once_with(
            '/app-groups/test.foo',
            b'cells: [test]\n',
            makepath=True, ephemeral=False, acl=mock.ANY, sequence=False
        )

    @mock.patch('treadmill.context.AdminContext.server')
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    @mock.patch('treadmill.scheduler.masterapi.create_bucket',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.scheduler.masterapi.cell_insert_bucket',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.scheduler.masterapi.create_server',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.scheduler.masterapi.update_server_attrs',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.scheduler.masterapi.list_servers',
                mock.Mock(spec_set=True))
    @mock.patch('treadmill.scheduler.masterapi.delete_server',
                mock.Mock(spec_set=True))
    def test_sync_server_topology(self, server_factory):
        """"Test syncing LDAP servers to Zookeeper.
        """
        treadmill.context.GLOBAL.cell = 'test'
        mock_zkclient = treadmill.context.GLOBAL.zk.conn
        mock_admsrv = server_factory.return_value

        mock_admsrv.list.return_value = [
            {'_id': 'foo'},
            {'_id': 'bar', 'partition': 'one'},
            {'_id': 'baz', 'partition': 'two'},
        ]
        treadmill.scheduler.masterapi.list_servers.return_value = [
            'extra_and_down',
        ]
        mock_zkclient.get_children.return_value = [
            'extra_but_up',
        ]

        cellsync.sync_server_topology()

        treadmill.scheduler.masterapi.create_bucket.assert_has_calls(
            [
                mock.call(mock_zkclient, 'pod:0000', parent_id=None),
                mock.call(mock_zkclient, 'pod:0001', parent_id=None),
                mock.call(mock_zkclient, 'pod:0002', parent_id=None),
                mock.call(mock_zkclient, 'rack:0002', parent_id='pod:0000'),
                mock.call(mock_zkclient, 'rack:0008', parent_id='pod:0001'),
                mock.call(mock_zkclient, 'rack:0008', parent_id='pod:0002'),
            ],
            any_order=True
        )
        treadmill.scheduler.masterapi.cell_insert_bucket.assert_has_calls(
            [
                mock.call(mock_zkclient, 'pod:0001'),
            ],
            any_order=True
        )
        treadmill.scheduler.masterapi.create_server.assert_has_calls(
            [
                mock.call(mock_zkclient, 'foo', 'rack:0008', partition=None),
                mock.call(mock_zkclient, 'bar', 'rack:0002', partition='one'),
                mock.call(mock_zkclient, 'baz', 'rack:0008', partition='two'),
            ]
        )
        treadmill.scheduler.masterapi.delete_server.assert_called_once_with(
            mock_zkclient, 'extra_and_down'
        )

    def test_appgroup_lookup_db(self):
        """Test lookup db construction.
        """
        # pylint: disable=protected-access

        rows = [
            ('foo.bar.*', 'dns', 'http', '{"name":"value"}'),
            ('foo.bar.*', 'lbendpoint', 'http', '{"name":"value"}'),
        ]
        fname = cellsync._create_lookup_db(rows)
        conn = sqlite3.connect(fname)
        rows = list(conn.execute(
            'select pattern from appgroups where group_type = "dns"'))
        self.assertEqual('foo.bar.*', rows[0][0])
        os.unlink(fname)

    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    def test_save_appgroup_lookup(self):
        """Test saving appgroup loopkup.
        """
        # pylint: disable=protected-access

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'xxx')

        zkclient = kazoo.client.KazooClient()
        kazoo.client.KazooClient.get_children.return_value = []
        cellsync._save_appgroup_lookup(zkclient, f.name, 'foo', '1234')

        zkutils.put.assert_called_with(
            zkclient,
            '/appgroup-lookups/foo/1234',
            b'xxx'
        )
        zkutils.put.reset_mock()

        kazoo.client.KazooClient.get_children.return_value = ['3456']
        cellsync._save_appgroup_lookup(zkclient, f.name, 'foo', '1234')

        zkutils.put.assert_called_with(
            zkclient,
            '/appgroup-lookups/foo/1234',
            b'xxx'
        )
        zkutils.ensure_deleted.assert_called_with(
            zkclient,
            '/appgroup-lookups/foo/3456',
        )

    def test_appgroup_group_by(self):
        """Test partitioning of appgroups by proid, generating checksum.
        """
        # pylint: disable=protected-access

        appgroups1 = [
            {'pattern': 'foo.2.*', 'data': {},
             'endpoints': ['http'], 'group-type': 'dns'},
            {'pattern': 'foo.1.*', 'data': {},
             'endpoints': ['tcp'], 'group-type': 'lbendpoint'},
            {'pattern': 'bar.1.*', 'data': {},
             'endpoints': ['tcp'], 'group-type': 'lbendpoint'},
        ]

        grouped_by1, checksums1 = cellsync._appgroup_group_by_proid(appgroups1)

        # different order
        appgroups2 = [
            {'pattern': 'bar.1.*', 'data': {},
             'endpoints': ['tcp'], 'group-type': 'lbendpoint'},
            {'pattern': 'foo.1.*', 'data': {},
             'endpoints': ['tcp'], 'group-type': 'lbendpoint'},
            {'pattern': 'foo.2.*', 'data': {},
             'endpoints': ['http'], 'group-type': 'dns'},
        ]

        grouped_by2, checksums2 = cellsync._appgroup_group_by_proid(appgroups2)

        self.assertIn('bar', checksums2)
        self.assertIn('foo', checksums2)

        self.assertEqual(checksums2['bar'].hexdigest(),
                         checksums1['bar'].hexdigest())
        self.assertEqual(checksums2['foo'].hexdigest(),
                         checksums1['foo'].hexdigest())

        # Check rows are ordered correctly.
        self.assertEqual(grouped_by1['foo'],
                         [('foo.1.*', 'lbendpoint', 'tcp', '{}'),
                          ('foo.2.*', 'dns', 'http', '{}')])


if __name__ == '__main__':
    unittest.main()
