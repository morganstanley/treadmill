"""Unit test for trace.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest

import mock

from treadmill import trace
from treadmill.trace import events_publisher
from treadmill.trace.app import events as app_events
from treadmill.trace.app import zk as app_zk
from treadmill.trace.server import events as server_events
from treadmill.trace.server import zk as server_zk

from treadmill.tests.testutils import mockzk


class TraceTest(mockzk.MockZookeeperTestCase):
    """Tests for teadmill.trace."""

    def setUp(self):
        super(TraceTest, self).setUp()
        self.root = tempfile.mkdtemp()
        self.app_events_dir = tempfile.mkdtemp(dir=self.root)
        self.server_events_dir = tempfile.mkdtemp(dir=self.root)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)
        super(TraceTest, self).tearDown()

    @mock.patch('time.time', mock.Mock(return_value=100))
    @mock.patch('treadmill.trace.app.zk._HOSTNAME', 'baz')
    @mock.patch('treadmill.trace.server.zk._HOSTNAME', 'baz')
    def test_post(self):
        """Test trace.post."""
        # Disable W0212(protected-access)
        # pylint: disable=W0212
        zkclient_mock = mock.Mock()
        zkclient_mock.get_children.return_value = []
        publisher = events_publisher.EventsPublisher(
            zkclient_mock,
            app_events_dir=self.app_events_dir,
            server_events_dir=self.server_events_dir
        )

        trace.post(
            self.app_events_dir,
            app_events.PendingTraceEvent(
                instanceid='foo.bar#123',
                why='created',
            )
        )
        path = os.path.join(
            self.app_events_dir, '100,foo.bar#123,pending,created'
        )
        self.assertTrue(os.path.exists(path))
        publisher._on_created(path, app_zk.publish)
        zkclient_mock.create.assert_called_once_with(
            '/trace/007B/foo.bar#123,100,baz,pending,created',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )

        zkclient_mock.reset_mock()
        trace.post(
            self.app_events_dir,
            app_events.PendingDeleteTraceEvent(
                instanceid='foo.bar#123',
                why='deleted'
            )
        )
        path = os.path.join(
            self.app_events_dir, '100,foo.bar#123,pending_delete,deleted'
        )
        self.assertTrue(os.path.exists(path))
        publisher._on_created(path, app_zk.publish)
        zkclient_mock.create.assert_called_once_with(
            '/trace/007B/foo.bar#123,100,baz,pending_delete,deleted',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )

        zkclient_mock.reset_mock()
        trace.post(
            self.app_events_dir,
            app_events.AbortedTraceEvent(
                instanceid='foo.bar#123',
                why='test'
            )
        )
        path = os.path.join(
            self.app_events_dir, '100,foo.bar#123,aborted,test'
        )
        self.assertTrue(os.path.exists(path))
        publisher._on_created(path, app_zk.publish)
        self.assertEqual(zkclient_mock.create.call_args_list, [
            mock.call(
                '/trace/007B/foo.bar#123,100,baz,aborted,test',
                b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            ),
            mock.call(
                '/finished/foo.bar#123',
                b'{data: test, host: baz, state: aborted, when: \'100\'}\n',
                makepath=True,
                ephemeral=False,
                acl=mock.ANY,
                sequence=False
            )
        ])

        zkclient_mock.reset_mock()
        trace.post(
            self.server_events_dir,
            server_events.ServerStateTraceEvent(
                servername='test.xx.com',
                state='up'
            )
        )
        path = os.path.join(
            self.server_events_dir, '100,test.xx.com,server_state,up'
        )
        self.assertTrue(os.path.exists(path))
        publisher._on_created(path, server_zk.publish)
        zkclient_mock.create.assert_called_once_with(
            '/server-trace/005D/test.xx.com,100,baz,server_state,up',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )

        zkclient_mock.reset_mock()
        trace.post(
            self.server_events_dir,
            server_events.ServerBlackoutTraceEvent(
                servername='test.xx.com'
            )
        )
        path = os.path.join(
            self.server_events_dir, '100,test.xx.com,server_blackout,'
        )
        self.assertTrue(os.path.exists(path))
        publisher._on_created(path, server_zk.publish)
        zkclient_mock.create.assert_called_once_with(
            '/server-trace/005D/test.xx.com,100,baz,server_blackout,',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )

    @mock.patch('time.time', mock.Mock(return_value=100))
    @mock.patch('treadmill.trace.app.zk._HOSTNAME', 'baz')
    @mock.patch('treadmill.trace.server.zk._HOSTNAME', 'baz')
    def test_post_zk(self):
        """Test trace.post_zk."""
        zkclient_mock = mock.Mock()
        zkclient_mock.get_children.return_value = []

        trace.post_zk(
            zkclient_mock,
            app_events.PendingTraceEvent(
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

        trace.post_zk(
            zkclient_mock,
            app_events.PendingDeleteTraceEvent(
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

        trace.post_zk(
            zkclient_mock,
            app_events.AbortedTraceEvent(
                instanceid='foo.bar#123',
                why='test'
            )
        )
        zkclient_mock.create.assert_has_calls([
            mock.call(
                '/trace/007B/foo.bar#123,100,baz,aborted,test',
                b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            ),
            mock.call(
                '/finished/foo.bar#123',
                b'{data: test, host: baz, state: aborted, when: \'100\'}\n',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            )
        ])
        zkclient_mock.reset_mock()

        trace.post_zk(
            zkclient_mock,
            server_events.ServerStateTraceEvent(
                servername='test.xx.com',
                state='up'
            )
        )
        zkclient_mock.create.assert_called_once_with(
            '/server-trace/005D/test.xx.com,100,baz,server_state,up',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )
        zkclient_mock.reset_mock()

        trace.post_zk(
            zkclient_mock,
            server_events.ServerBlackoutTraceEvent(
                servername='test.xx.com'
            )
        )
        zkclient_mock.create.assert_called_once_with(
            '/server-trace/005D/test.xx.com,100,baz,server_blackout,',
            b'',
            ephemeral=False, makepath=True, sequence=False,
            acl=mock.ANY
        )


if __name__ == '__main__':
    unittest.main()
