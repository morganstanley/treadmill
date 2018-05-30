"""Unit test for Zookeeper helper - testing zk connection and leader election.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import unittest

import kazoo
import kazoo.client
import mock

import treadmill
from treadmill import zkutils
from treadmill import yamlwrapper as yaml


class ZkTest(unittest.TestCase):
    """Mock test for treadmill.zk."""

    def setUp(self):
        os.environ['TREADMILL_MASTER_ROOT'] = '/'

    def test_sequence_watch(self):
        """Tests sequence watch."""
        events = []

        def _callback(path, _data, _stat):
            return events.append(path)

        watcher = zkutils.SequenceNodeWatch(treadmill.zkutils.ZkClient(),
                                            _callback,
                                            delim='-', pattern=None,
                                            include_data=False)

        # no delimieter, no events fired.
        for node in watcher.nodes(['aaa', 'bbb']):
            watcher.invoke_callback('/xxx', node)
        self.assertEqual(0, len(events))
        for node in watcher.nodes(['1-001', '1-002']):
            watcher.invoke_callback('/xxx', node)
        # events == [/001, /002] pop works from the end.
        self.assertEqual('/xxx/1-002', events.pop())
        self.assertEqual('/xxx/1-001', events.pop())

        # added new node, make sure only one event is called
        for node in watcher.nodes(['1-001', '1-002', '1-003']):
            watcher.invoke_callback('/xxx', node)
        self.assertEqual(1, len(events))
        self.assertEqual('/xxx/1-003', events.pop())

        # Check that order of children nodes does not matter, only seq number
        # counts.
        for node in watcher.nodes(['0-004', '1-003', '1-002', '0-001']):
            watcher.invoke_callback('/xxx', node)
        self.assertEqual(1, len(events))
        self.assertEqual('/xxx/0-004', events.pop())

        # Test that pattern is being filtered.
        watcher = zkutils.SequenceNodeWatch(treadmill.zkutils.ZkClient(),
                                            _callback, delim='-',
                                            pattern='foo',
                                            include_data=False)

        for node in watcher.nodes(['aaa', 'bbb', 'foo']):
            watcher.invoke_callback('/xxx', node)
        self.assertEqual(0, len(events))
        for node in watcher.nodes(['aaa', 'bbb', 'foo-1']):
            watcher.invoke_callback('/xxx', node)
        self.assertEqual(1, len(events))

    @mock.patch('treadmill.zkutils.ZkClient.create', mock.Mock())
    def test_put(self):
        """Tests updating/creating node content."""
        client = treadmill.zkutils.ZkClient()
        zkutils.put(client, '/foo/bar')
        treadmill.zkutils.ZkClient.create.assert_called_with(
            '/foo/bar',
            b'',
            acl=mock.ANY,
            makepath=True, sequence=False, ephemeral=False
        )

    @mock.patch('treadmill.zkutils.ZkClient.create', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.set', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.set_acls', mock.Mock())
    def test_put_existing(self):
        """Test update content of existing node."""
        def raise_exists(*_args, **_kwargs):
            """zk.create side effect, raising appropriate exception."""
            raise kazoo.client.NodeExistsError()

        client = treadmill.zkutils.ZkClient()
        treadmill.zkutils.ZkClient.create.side_effect = raise_exists
        zkutils.put(client, '/foo/bar')
        treadmill.zkutils.ZkClient.set.assert_called_with('/foo/bar', b'')
        treadmill.zkutils.ZkClient.set_acls.assert_called_with('/foo/bar',
                                                               mock.ANY)

    @mock.patch('treadmill.zkutils.ZkClient.get', mock.Mock())
    def test_get(self):
        """Test zkutils.get parsing of YAML data."""
        client = treadmill.zkutils.ZkClient()
        treadmill.zkutils.ZkClient.get.return_value = ('{xxx: 123}', None)
        self.assertEqual({'xxx': 123}, zkutils.get(client, '/foo'))

        # parsing error
        treadmill.zkutils.ZkClient.get.return_value = ('{xxx: 123', None)
        self.assertEqual(
            '{xxx: 123',
            zkutils.get(client, '/foo', strict=False)
        )
        self.assertRaises(yaml.YAMLError, zkutils.get, client, '/foo')

        treadmill.zkutils.ZkClient.get.return_value = (None, None)
        self.assertIsNone(zkutils.get(client, '/foo'))

    @mock.patch('treadmill.zkutils.ZkClient.create', mock.Mock())
    def test_ensure_exists(self):
        """Tests updating/creating node content."""
        # with data
        client = treadmill.zkutils.ZkClient()
        zkutils.ensure_exists(client, '/foo/bar', data='foo')
        treadmill.zkutils.ZkClient.create.assert_called_with(
            '/foo/bar',
            b'foo',
            acl=mock.ANY,
            makepath=True, sequence=False
        )

        # non-data
        zkutils.ensure_exists(client, '/foo/bar')
        treadmill.zkutils.ZkClient.create.assert_called_with(
            '/foo/bar',
            b'',
            acl=mock.ANY,
            makepath=True, sequence=False
        )

    @mock.patch('treadmill.zkutils.ZkClient.set', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.create', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.set_acls', mock.Mock())
    def test_ensure_exists_existing(self):
        """Test update content of existing node."""
        def raise_exists(*_args, **_kwargs):
            """zk.create side effect, raising appropriate exception."""
            raise kazoo.client.NodeExistsError()

        client = treadmill.zkutils.ZkClient()
        treadmill.zkutils.ZkClient.create.side_effect = raise_exists
        zkutils.ensure_exists(client, '/foo/bar')
        treadmill.zkutils.ZkClient.set_acls.assert_called_with('/foo/bar',
                                                               mock.ANY)

        # ensure with data
        zkutils.ensure_exists(client, '/foo/bar', data='foo')
        treadmill.zkutils.ZkClient.set.assert_called_with('/foo/bar', b'foo')
        treadmill.zkutils.ZkClient.set_acls.assert_called_with('/foo/bar',
                                                               mock.ANY)

    @mock.patch('treadmill.zkutils.ZkClient.start', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.add_listener', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.exists',
                mock.Mock(return_value=False))
    @mock.patch('treadmill.zkutils.ZkClient.create', mock.Mock())
    def test_connect_chroot(self):
        """Test connecting with chroot."""
        zkutils.connect('zookeeper://me@xxx:123,yyy:123,zzz:123/a/b/c')
        treadmill.zkutils.ZkClient.create.assert_has_calls(
            [
                mock.call('/a', b'', makepath=True, acl=mock.ANY),
                mock.call('/a/b', b'', makepath=True, acl=mock.ANY),
                mock.call('/a/b/c', b'', makepath=True, acl=mock.ANY),
            ]
        )

    @mock.patch('treadmill.zkutils.ZkClient.set', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.set_acls', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.create', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.get', mock.Mock())
    def test_put_check_content(self):
        """Verifies put/update with check_content=True."""
        treadmill.zkutils.ZkClient.create.side_effect = (
            kazoo.client.NodeExistsError)
        treadmill.zkutils.ZkClient.get.return_value = (b'aaa', {})
        zkclient = treadmill.zkutils.ZkClient()
        zkutils.put(zkclient, '/a', 'aaa', check_content=True)
        self.assertFalse(treadmill.zkutils.ZkClient.set.called)

        zkutils.put(zkclient, '/a', 'bbb', check_content=True)
        treadmill.zkutils.ZkClient.set.assert_called_with('/a', b'bbb')

    @mock.patch('treadmill.zkutils.ZkClient.set', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.set_acls', mock.Mock())
    @mock.patch('treadmill.zkutils.ZkClient.get', mock.Mock())
    def test_update_check_content(self):
        """Verifies put/update with check_content=True."""
        treadmill.zkutils.ZkClient.get.return_value = (b'aaa', {})
        zkclient = treadmill.zkutils.ZkClient()
        zkutils.update(zkclient, '/a', 'aaa', check_content=True)
        self.assertFalse(treadmill.zkutils.ZkClient.set.called)

        zkutils.update(zkclient, '/a', 'bbb', check_content=True)
        treadmill.zkutils.ZkClient.set.assert_called_with('/a', b'bbb')


if __name__ == '__main__':
    unittest.main()
