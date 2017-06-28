"""
Unit test for appevents.
"""

import os
import shutil
import tempfile
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

from treadmill import appevents
from treadmill.apptrace import events


class AppeventsTest(unittest.TestCase):
    """Tests for teadmill.appevents."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

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
                payload=''
            )
        )
        path = os.path.join(
            self.root, '100,foo.bar#123,pending,created'
        )
        self.assertTrue(os.path.exists(path))
        watcher._on_created(path)
        zkclient_mock.create.assert_called_once_with(
            '/trace/007B/foo.bar#123,100,baz,pending,created',
            '',
            makepath=True,
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
            mock.ANY,
            makepath=True,
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
                mock.ANY,
                makepath=True,
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
            '',
            makepath=True,
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
            mock.ANY,
            makepath=True,
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
                mock.ANY,
                makepath=True,
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


if __name__ == '__main__':
    unittest.main()
