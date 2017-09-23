"""Unit test for appevents.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest

from tests.testutils import mockzk

import kazoo
import mock

from treadmill import appevents
from treadmill import zkutils
from treadmill.apptrace import events


class AppeventsTest(mockzk.MockZookeeperTestCase):
    """Tests for teadmill.appevents."""

    def setUp(self):
        super(AppeventsTest, self).setUp()
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)
        super(AppeventsTest, self).tearDown()

    @mock.patch('time.time', mock.Mock(return_value=100))
    @mock.patch('treadmill.appevents._HOSTNAME', 'baz')
    def test_post(self):
        """Test appevents.post."""
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        zkclient_mock = mock.Mock()
        zkclient_mock.get_children.return_value = []
        watcher = appevents.AppEventsWatcher(zkclient_mock, self.root)

        appevents.post(
            self.root,
            events.PendingTraceEvent(
                instanceid='foo.bar#123',
                why='created',
            )
        )
        path = os.path.join(
            self.root, '100,foo.bar#123,pending,created'
        )
        self.assertTrue(os.path.exists(path))
        watcher._on_created(path)
        zkclient_mock.create.assert_called_once_with(
            '/trace/007B/foo.bar#123,100,baz,pending,created',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )

        zkclient_mock.reset_mock()
        appevents.post(
            self.root,
            events.PendingDeleteTraceEvent(
                instanceid='foo.bar#123',
                why='deleted'
            )
        )
        path = os.path.join(
            self.root, '100,foo.bar#123,pending_delete,deleted'
        )
        self.assertTrue(os.path.exists(path))
        watcher._on_created(path)
        zkclient_mock.create.assert_called_once_with(
            '/trace/007B/foo.bar#123,100,baz,pending_delete,deleted',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )

        zkclient_mock.reset_mock()
        appevents.post(
            self.root,
            events.AbortedTraceEvent(
                instanceid='foo.bar#123',
                why='test'
            )
        )
        path = os.path.join(
            self.root, '100,foo.bar#123,aborted,test'
        )
        self.assertTrue(os.path.exists(path))
        watcher._on_created(path)
        self.assertEqual(zkclient_mock.create.call_args_list, [
            mock.call(
                '/trace/007B/foo.bar#123,100,baz,aborted,test',
                b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            ),
            mock.call(
                '/finished/foo.bar#123',
                "{data: test, host: baz, "
                "state: aborted, when: '100'}\n",
                makepath=True,
                ephemeral=False,
                acl=mock.ANY,
                sequence=False
            )
        ])

    @mock.patch('time.time', mock.Mock(return_value=100))
    @mock.patch('treadmill.appevents._HOSTNAME', 'baz')
    def test_post_zk(self):
        """Test appevents.post.zk."""
        zkclient_mock = mock.Mock()
        zkclient_mock.get_children.return_value = []

        appevents.post_zk(
            zkclient_mock,
            events.PendingTraceEvent(
                instanceid='foo.bar#123',
                why='created',
                payload=''
            )
        )
        zkclient_mock.create.assert_called_once_with(
            '/trace/007B/foo.bar#123,100,baz,pending,created',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )
        zkclient_mock.reset_mock()

        appevents.post_zk(
            zkclient_mock,
            events.PendingDeleteTraceEvent(
                instanceid='foo.bar#123',
                why='deleted'
            )
        )
        zkclient_mock.create.assert_called_once_with(
            '/trace/007B/foo.bar#123,100,baz,pending_delete,deleted',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )
        zkclient_mock.reset_mock()

        appevents.post_zk(
            zkclient_mock,
            events.AbortedTraceEvent(
                instanceid='foo.bar#123',
                why='test'
            )
        )
        self.assertEqual(zkclient_mock.create.call_args_list, [
            mock.call(
                '/trace/007B/foo.bar#123,100,baz,aborted,test',
                b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            ),
            mock.call(
                '/finished/foo.bar#123',
                "{data: test, host: baz, "
                "state: aborted, when: '100'}\n",
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            )
        ])

    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.appevents._HOSTNAME', 'host_x')
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
        appevents._unschedule(zkclient, 'app#1')

        zkutils.ensure_deleted.assert_called_with(zkclient, '/scheduled/app#1')

    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.appevents._HOSTNAME', 'host_x')
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
        appevents._unschedule(zkclient, 'app#1')

        self.assertFalse(zkutils.ensure_deleted.called)


if __name__ == '__main__':
    unittest.main()
