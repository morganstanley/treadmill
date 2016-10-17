"""Unit test for Zookeeper helper - testing zk connection and leader election.
"""

import os
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import kazoo
import kazoo.client
import mock
import yaml

from treadmill import zkutils


class ZkTest(unittest.TestCase):
    """Mock test for treadmill.zk."""

    def setUp(self):
        os.environ['TREADMILL_MASTER_ROOT'] = '/'

    def test_path(self):
        """Test path construction for various entities."""
        self.assertEquals('/scheduled/foo',
                          zkutils.path_scheduled('foo'))
        self.assertEquals('/running/foo',
                          zkutils.path_running('foo'))
        self.assertEquals('/apps/foo',
                          zkutils.path_config('foo'))
        self.assertEquals('/servers/foo',
                          zkutils.path_server('foo'))
        self.assertEquals('/allocations/foo',
                          zkutils.path_allocation('foo'))
        self.assertEquals('/tasks/foo/0001',
                          zkutils.path_task('foo#0001'))

    def test_sequence_watch(self):
        """Tests sequence watch."""
        events = []
        callback = lambda path, data, stat: events.append(path)
        watcher = zkutils.SequenceNodeWatch(kazoo.client.KazooClient(),
                                            callback,
                                            delim='-', pattern=None,
                                            include_data=False)

        # no delimieter, no events fired.
        for node in watcher.nodes(['aaa', 'bbb']):
            watcher.invoke_callback('/xxx', node)
        self.assertEquals(0, len(events))
        for node in watcher.nodes(['1-001', '1-002']):
            watcher.invoke_callback('/xxx', node)
        # events == [/001, /002] pop works from the end.
        self.assertEquals('/xxx/1-002', events.pop())
        self.assertEquals('/xxx/1-001', events.pop())

        # added new node, make sure only one event is called
        for node in watcher.nodes(['1-001', '1-002', '1-003']):
            watcher.invoke_callback('/xxx', node)
        self.assertEquals(1, len(events))
        self.assertEquals('/xxx/1-003', events.pop())

        # Check that order of children nodes does not matter, only seq number
        # counts.
        for node in watcher.nodes(['0-004', '1-003', '1-002', '0-001']):
            watcher.invoke_callback('/xxx', node)
        self.assertEquals(1, len(events))
        self.assertEquals('/xxx/0-004', events.pop())

        # Test that pattern is being filtered.
        watcher = zkutils.SequenceNodeWatch(kazoo.client.KazooClient(),
                                            callback, delim='-',
                                            pattern='foo',
                                            include_data=False)

        for node in watcher.nodes(['aaa', 'bbb', 'foo']):
            watcher.invoke_callback('/xxx', node)
        self.assertEquals(0, len(events))
        for node in watcher.nodes(['aaa', 'bbb', 'foo-1']):
            watcher.invoke_callback('/xxx', node)
        self.assertEquals(1, len(events))

    def test_construct_acl(self):
        """Verifies make_acl helper functions."""
        acl = zkutils.make_user_acl('foo', 'crwd')
        self.assertEquals('user://foo', acl.id.id)
        self.assertEquals('kerberos', acl.id.scheme)
        self.assertIn('READ', acl.acl_list)
        self.assertIn('WRITE', acl.acl_list)
        self.assertIn('CREATE', acl.acl_list)
        self.assertIn('DELETE', acl.acl_list)
        self.assertNotIn('ADMIN', acl.acl_list)

        acl = zkutils.make_host_acl('crwd', 'host.foo.com')
        self.assertEquals('user://host/host.foo.com', acl.id.id)
        self.assertEquals('kerberos', acl.id.scheme)
        self.assertIn('READ', acl.acl_list)
        self.assertIn('WRITE', acl.acl_list)
        self.assertIn('CREATE', acl.acl_list)
        self.assertIn('DELETE', acl.acl_list)
        self.assertNotIn('ADMIN', acl.acl_list)

        acl = zkutils.make_file_acl('/var/tmp/xxx', 'r')
        self.assertEquals('file:///var/tmp/xxx', acl.id.id)
        self.assertEquals('kerberos', acl.id.scheme)
        self.assertIn('READ', acl.acl_list)
        self.assertNotIn('WRITE', acl.acl_list)
        self.assertNotIn('CREATE', acl.acl_list)
        self.assertNotIn('DELETE', acl.acl_list)
        self.assertNotIn('ADMIN', acl.acl_list)

        acl = zkutils.make_anonymous_acl('r')
        self.assertEquals('anyone', acl.id.id)
        self.assertEquals('world', acl.id.scheme)
        self.assertIn('READ', acl.acl_list)
        self.assertNotIn('WRITE', acl.acl_list)
        self.assertNotIn('CREATE', acl.acl_list)
        self.assertNotIn('DELETE', acl.acl_list)
        self.assertNotIn('ADMIN', acl.acl_list)

    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    def test_put(self):
        """Tests updating/creating node content."""
        client = kazoo.client.KazooClient()
        zkutils.put(client, '/foo/bar')
        kazoo.client.KazooClient.create.assert_called_with(
            '/foo/bar', '', acl=mock.ANY, makepath=True,
            sequence=False, ephemeral=False)

    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set_acls', mock.Mock())
    def test_put_existing(self):
        """Test update content of existing node."""
        def raise_exists(*args_unused, **kwargs_unused):
            """zk.create side effect, raising appropriate exception."""
            raise kazoo.client.NodeExistsError()

        client = kazoo.client.KazooClient()
        kazoo.client.KazooClient.create.side_effect = raise_exists
        zkutils.put(client, '/foo/bar')
        kazoo.client.KazooClient.set.assert_called_with('/foo/bar', '')
        kazoo.client.KazooClient.set_acls.assert_called_with('/foo/bar',
                                                             mock.ANY)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    def test_get(self):
        """Test zkutils.get parsing of YAML data."""
        client = kazoo.client.KazooClient()
        kazoo.client.KazooClient.get.return_value = ('{xxx: 123}', None)
        self.assertEquals({'xxx': 123}, zkutils.get(client, '/foo'))

        # parsing error
        kazoo.client.KazooClient.get.return_value = ('{xxx: 123', None)
        self.assertEquals('{xxx: 123', zkutils.get(client, '/foo',
                                                   strict=False))
        self.assertRaises(yaml.YAMLError, zkutils.get, client, '/foo')

        kazoo.client.KazooClient.get.return_value = (None, None)
        self.assertIsNone(zkutils.get(client, '/foo'))

    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    def test_ensure_exists(self):
        """Tests updating/creating node content."""
        # with data
        client = kazoo.client.KazooClient()
        zkutils.ensure_exists(client, '/foo/bar', data='foo')
        kazoo.client.KazooClient.create.assert_called_with(
            '/foo/bar', 'foo', acl=mock.ANY, makepath=True,
            sequence=False)

        # non-data
        zkutils.ensure_exists(client, '/foo/bar')
        kazoo.client.KazooClient.create.assert_called_with(
            '/foo/bar', '', acl=mock.ANY, makepath=True,
            sequence=False)

    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set_acls', mock.Mock())
    def test_ensure_exists_existing(self):
        """Test update content of existing node."""
        def raise_exists(*args_unused, **kwargs_unused):
            """zk.create side effect, raising appropriate exception."""
            raise kazoo.client.NodeExistsError()

        client = kazoo.client.KazooClient()
        kazoo.client.KazooClient.create.side_effect = raise_exists
        zkutils.ensure_exists(client, '/foo/bar')
        kazoo.client.KazooClient.set_acls.assert_called_with('/foo/bar',
                                                             mock.ANY)

        # ensure with data
        zkutils.ensure_exists(client, '/foo/bar', data='foo')
        kazoo.client.KazooClient.set.assert_called_with('/foo/bar', 'foo')
        kazoo.client.KazooClient.set_acls.assert_called_with('/foo/bar',
                                                             mock.ANY)

    @mock.patch('kazoo.client.KazooClient.start', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.add_listener', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists',
                mock.Mock(return_value=False))
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    def test_connect_chroot(self):
        """Test connecting with chroot."""
        zkutils.connect('zookeeper://me@xxx:123,yyy:123,zzz:123/a/b/c')
        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call('/a', '', makepath=True, acl=mock.ANY),
            mock.call('/a/b', '', makepath=True, acl=mock.ANY),
            mock.call('/a/b/c', '', makepath=True, acl=mock.ANY),
        ])

    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set_acls', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    def test_put_check_content(self):
        """Verifies put/update with check_content=True."""
        kazoo.client.KazooClient.create.side_effect = (
            kazoo.client.NodeExistsError)
        kazoo.client.KazooClient.get.return_value = ('aaa', {})
        zkclient = kazoo.client.KazooClient()
        zkutils.put(zkclient, '/a', 'aaa', check_content=True)
        self.assertFalse(kazoo.client.KazooClient.set.called)

        zkutils.put(zkclient, '/a', 'bbb', check_content=True)
        kazoo.client.KazooClient.set.assert_called_with('/a', 'bbb')

    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set_acls', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    def test_update_check_content(self):
        """Verifies put/update with check_content=True."""
        kazoo.client.KazooClient.get.return_value = ('aaa', {})
        zkclient = kazoo.client.KazooClient()
        zkutils.update(zkclient, '/a', 'aaa', check_content=True)
        self.assertFalse(kazoo.client.KazooClient.set.called)

        zkutils.update(zkclient, '/a', 'bbb', check_content=True)
        kazoo.client.KazooClient.set.assert_called_with('/a', 'bbb')


if __name__ == "__main__":
    unittest.main()
