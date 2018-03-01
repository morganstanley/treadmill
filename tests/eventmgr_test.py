"""Unit test for eventmgr - processing Zookeeper events.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import io
import os
import shutil
import tempfile
import unittest

from tests.testutils import mockzk

import kazoo
import mock

import treadmill
from treadmill import context
from treadmill import eventmgr
from treadmill import yamlwrapper as yaml


class MockEventObject(object):
    """Mock event object."""

    def __init__(self):
        self._is_set = False

    def clear(self):
        """Clear the internal flag to false."""
        self._is_set = False

    def set(self):
        """Set the internal flag to true."""
        self._is_set = True

    def is_set(self):
        """Return true if the internal flag is set to true, false otherwise."""
        return self._is_set


def mock_event_object():
    """Return mock event object."""
    return MockEventObject()


class EventMgrTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.eventmgr.EventMgr."""

    @mock.patch('treadmill.appenv.AppEnvironment', mock.Mock(autospec=True))
    @mock.patch('treadmill.watchdog.Watchdog', mock.Mock(autospec=True))
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.cache = os.path.join(self.root, 'cache')
        os.mkdir(self.cache)

        context.GLOBAL.cell = 'test'
        context.GLOBAL.zk.url = 'zookeeper://xxx@yyy:123'

        self.evmgr = eventmgr.EventMgr(root=self.root)
        self.evmgr.tm_env.root = self.root
        self.evmgr.tm_env.cache_dir = self.cache

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('time.sleep', mock.Mock())
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    def test_run(self):
        """Test EventMgr run method.
        """
        mock_zkclient = mock.Mock()
        context.GLOBAL.zk.conn = mock_zkclient

        mock_data_watch = mock.Mock(
            side_effect=lambda func: func({'valid_until': 123.0}, None, None)
        )

        mock_children_watch = mock.Mock(
            side_effect=lambda func: func(['foo.bar#0'])
        )

        mock_zkclient.get.return_value = ('{}', None)
        mock_zkclient.DataWatch.return_value = mock_data_watch
        mock_zkclient.ChildrenWatch.return_value = mock_children_watch
        mock_zkclient.handler.event_object.side_effect = mock_event_object

        self.evmgr.run(once=True)

        self.assertTrue(os.path.exists(os.path.join(self.cache, '.ready')))
        self.assertTrue(os.path.exists(os.path.join(self.cache, 'foo.bar#0')))

        mock_watchdog = self.evmgr.tm_env.watchdogs
        mock_watchdog.create.assert_called_with(
            content=mock.ANY,
            name='svc-EventMgr',
            timeout='120s'
        )
        mock_watchdog_lease = mock_watchdog.create.return_value
        mock_watchdog_lease.heartbeat.assert_called_with()

        # The main loop terminates immediately
        mock_watchdog_lease.remove.assert_called_with()

    @mock.patch('time.sleep', mock.Mock())
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    def test_run_not_present(self):
        """Test EventMgr run method - no server presence.
        """
        mock_zkclient = mock.Mock()
        context.GLOBAL.zk.conn = mock_zkclient

        mock_data_watch = mock.Mock(
            side_effect=lambda func: func(None, None, None)
        )

        mock_children_watch = mock.Mock(
            side_effect=lambda func: func(['foo.bar#0'])
        )

        mock_zkclient.get.return_value = ('{}', None)
        mock_zkclient.DataWatch.return_value = mock_data_watch
        mock_zkclient.ChildrenWatch.return_value = mock_children_watch
        mock_zkclient.handler.event_object.side_effect = mock_event_object

        self.evmgr.run(once=True)

        self.assertFalse(os.path.exists(os.path.join(self.cache, '.ready')))
        self.assertTrue(os.path.exists(os.path.join(self.cache, 'foo.bar#0')))

    @mock.patch('time.sleep', mock.Mock())
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    def test_run_not_synchronized(self):
        """Test EventMgr run method - apps not synchronized.
        """
        mock_zkclient = mock.Mock()
        context.GLOBAL.zk.conn = mock_zkclient

        mock_data_watch = mock.Mock(
            side_effect=lambda func: func({'valid_until': 123.0}, None, None)
        )

        mock_zkclient.DataWatch.return_value = mock_data_watch
        mock_zkclient.handler.event_object.side_effect = mock_event_object

        self.evmgr.run(once=True)

        self.assertFalse(os.path.exists(os.path.join(self.cache, '.ready')))

    @mock.patch('treadmill.zkutils.get', mock.Mock())
    def test__cache(self):
        """Tests application cache event.
        """
        # Access to a protected member _cache of a client class
        # pylint: disable=W0212
        treadmill.zkutils.get.return_value = {}

        zkclient = kazoo.client.KazooClient()
        self.evmgr._cache(zkclient, 'foo#001')

        appcache = os.path.join(self.cache, 'foo#001')
        self.assertTrue(os.path.exists(appcache))

    @mock.patch('treadmill.zkutils.get', mock.Mock())
    def test__cache_notfound(self):
        """Tests application cache event when app is not found.
        """
        # Access to a protected member _cache of a client class
        # pylint: disable=W0212
        treadmill.zkutils.get.side_effect = \
            kazoo.exceptions.NoNodeError

        zkclient = kazoo.client.KazooClient()
        self.evmgr._cache(zkclient, 'foo#001')

        appcache = os.path.join(self.cache, 'foo#001')
        self.assertFalse(os.path.exists(appcache))

    @mock.patch('glob.glob', mock.Mock())
    @mock.patch('treadmill.eventmgr.EventMgr._cache', mock.Mock())
    def test__synchronize(self):
        """Checks that app events are synchronized properly."""
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212
        existing_apps = []
        glob.glob.return_value = (app for app in existing_apps)

        zkclient = kazoo.client.KazooClient()
        self.evmgr._synchronize(zkclient, ['foo#001'])

        # cache should have been called with 'foo' app
        treadmill.eventmgr.EventMgr._cache.assert_called_with(
            zkclient, 'foo#001')

    @mock.patch('glob.glob', mock.Mock())
    @mock.patch('os.unlink', mock.Mock())
    @mock.patch('treadmill.eventmgr.EventMgr._cache', mock.Mock())
    def test__synchronize_empty(self):
        """Checks synchronized properly remove extra apps."""
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212
        existing_apps = ['proid.app#0', 'proid.app#1', 'proid.app#2']
        glob.glob.return_value = (app for app in existing_apps)

        zkclient = kazoo.client.KazooClient()
        self.evmgr._synchronize(zkclient, [])

        os.unlink.assert_has_calls(
            [
                mock.call(os.path.join(self.cache, app))
                for app in existing_apps
            ],
            any_order=True
        )
        self.assertFalse(treadmill.eventmgr.EventMgr._cache.called)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_cache_placement_data(self):
        """Tests sync of placement data.
        """
        # Access to a protected member _synchronize of a client class
        # pylint: disable=W0212
        zk_content = {
            'placement': {
                'test.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.data': '{identity: 1}\n',
                    },
                }
            },
            'scheduled': {
                'xxx.app1#1234': {
                    'affinity': 'app1',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                    'identity_group': 'xxx.app1',
                },
            }
        }
        self.make_mock_zk(zk_content)
        zkclient = kazoo.client.KazooClient()
        self.evmgr._hostname = 'test.xx.com'
        self.evmgr._cache(zkclient, 'xxx.app1#1234')

        appcache = os.path.join(self.cache, 'xxx.app1#1234')
        self.assertTrue(os.path.exists(appcache))

        with io.open(appcache) as f:
            data = yaml.load(stream=f)
            self.assertEqual(data['identity'], 1)

    def test__cache_notify(self):
        """Test sending a cache status notification event."""
        # Access to a protected member _cache_notify of a client class
        # pylint: disable=W0212
        ready_file = os.path.join(self.cache, '.ready')

        self.evmgr._cache_notify(True)
        self.assertTrue(os.path.exists(ready_file))

        self.evmgr._cache_notify(False)
        self.assertFalse(os.path.exists(ready_file))


if __name__ == '__main__':
    unittest.main()
