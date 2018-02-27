"""Unit test for cellsync.
"""

from __future__ import absolute_import

import unittest

import os
import sqlite3
import tempfile

# Disable W0611: Unused import
import tests.treadmill_test_skip_windows  # pylint: disable=W0611
import tests.treadmill_test_deps  # pylint: disable=W0611

import kazoo
import mock

from treadmill import cellsync  # pylint: disable=no-name-in-module
from treadmill import zkutils


# Disable W0212: Test access protected members of admin module.
# pylint: disable=W0212
class CellsyncTest(unittest.TestCase):
    """Test treadmill.cellsync"""

    @mock.patch('treadmill.context.GLOBAL', mock.Mock(cell='test'))
    def test_sync_collection(self):
        """"Test syncing ldap collection to Zookeeper."""

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

    def test_appgroup_lookup_db(self):
        """Test lookup db construction."""
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
        """Test saving appgroup loopkup."""

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
        """Test partitioning of appgroups by proid, generating checksum."""
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
