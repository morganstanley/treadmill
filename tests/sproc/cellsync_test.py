"""Unit test for cellsync.
"""

from __future__ import absolute_import

import unittest

import mock

from treadmill.sproc import cellsync


class CellsyncTest(unittest.TestCase):
    """Test treadmill.sproc.cellsync"""

    @mock.patch('treadmill.context.GLOBAL', mock.Mock(cell='test'))
    def test_sync_collection(self):
        """"Test syncing ldap collection to Zookeeper."""
        # Disable W0212: Test access protected members of admin module.
        # pylint: disable=W0212

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


if __name__ == '__main__':
    unittest.main()
