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

import kazoo
import mock

import treadmill
from treadmill import context
from treadmill import eventmgr
from treadmill import yamlwrapper as yaml

from treadmill.tests.testutils import mockzk


class MockEventObject:
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

        mock_zkclient.get.return_value = ('{}', mock.Mock(ctime=1000))
        mock_zkclient.exits.return_value = mock.Mock()
        # Decorator style watch
        mock_zkclient.DataWatch.return_value = mock_data_watch
        # Function style watch
        mock_zkclient.ChildrenWatch.side_effect = lambda _path, func: func(
            ['foo.bar#0']
        )
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
    def test_run_presence_not_ready(self):
        """Test EventMgr run method - no server presence.
        """
        mock_zkclient = mock.Mock()
        context.GLOBAL.zk.conn = mock_zkclient

        mock_data_watch = mock.Mock(
            side_effect=lambda func: func(None, None, None)
        )

        mock_zkclient.get.return_value = ('{}', mock.Mock(ctime=1000))
        mock_zkclient.exits.return_value = mock.Mock()
        # Decorator style watch
        mock_zkclient.DataWatch.return_value = mock_data_watch
        # Function style watch
        mock_zkclient.ChildrenWatch.side_effect = lambda _path, func: func(
            ['foo.bar#0']
        )
        mock_zkclient.handler.event_object.side_effect = mock_event_object

        self.evmgr.run(once=True)

        self.assertFalse(os.path.exists(os.path.join(self.cache, '.ready')))
        self.assertTrue(os.path.exists(os.path.join(self.cache, 'foo.bar#0')))

    @mock.patch('time.sleep', mock.Mock())
    @mock.patch('treadmill.context.GLOBAL.zk', mock.Mock())
    def test_run_placement_not_ready(self):
        """Test EventMgr run method - no placement.
        """
        mock_zkclient = mock.Mock()
        context.GLOBAL.zk.conn = mock_zkclient

        mock_data_watch = mock.Mock(
            side_effect=lambda func: func({'valid_until': 123.0}, None, None)
        )

        mock_zkclient.exists.return_value = None
        mock_zkclient.DataWatch.return_value = mock_data_watch
        mock_zkclient.handler.event_object.side_effect = mock_event_object

        self.evmgr.run(once=True)

        self.assertFalse(os.path.exists(os.path.join(self.cache, '.ready')))

    @mock.patch('treadmill.zkutils.get', mock.Mock())
    @mock.patch('treadmill.zkutils.get_with_metadata', mock.Mock())
    def test__cache(self):
        """Test application cache event.
        """
        # Access to a protected member _cache of a client class
        # pylint: disable=W0212
        treadmill.zkutils.get.return_value = {}

        treadmill.zkutils.get_with_metadata.return_value = (
            {}, mock.Mock(ctime=1000)
        )

        zkclient = kazoo.client.KazooClient()
        self.evmgr._cache(zkclient, 'foo#001')

        appcache = os.path.join(self.cache, 'foo#001')
        self.assertTrue(os.path.exists(appcache))

    @mock.patch('treadmill.zkutils.get', mock.Mock())
    @mock.patch('treadmill.zkutils.get_with_metadata', mock.Mock())
    def test__cache_placement_notfound(self):
        """Test application cache event when placement is not found.
        """
        # Access to a protected member _cache of a client class
        # pylint: disable=W0212
        treadmill.zkutils.get.return_value = {}

        treadmill.zkutils.get_with_metadata.side_effect = \
            kazoo.exceptions.NoNodeError

        zkclient = kazoo.client.KazooClient()
        self.evmgr._cache(zkclient, 'foo#001')

        appcache = os.path.join(self.cache, 'foo#001')
        self.assertFalse(os.path.exists(appcache))

    @mock.patch('treadmill.zkutils.get', mock.Mock())
    @mock.patch('treadmill.zkutils.get_with_metadata', mock.Mock())
    def test__cache_app_notfound(self):
        """Test application cache event when app is not found.
        """
        # Access to a protected member _cache of a client class
        # pylint: disable=W0212
        treadmill.zkutils.get.side_effect = \
            kazoo.exceptions.NoNodeError

        treadmill.zkutils.get_with_metadata.return_value = (
            {}, mock.Mock(ctime=1000)
        )

        zkclient = kazoo.client.KazooClient()
        self.evmgr._cache(zkclient, 'foo#001')

        appcache = os.path.join(self.cache, 'foo#001')
        self.assertFalse(os.path.exists(appcache))

    @mock.patch('treadmill.zkutils.get', mock.Mock())
    @mock.patch('treadmill.zkutils.get_with_metadata', mock.Mock())
    @mock.patch('treadmill.fs.write_safe', mock.Mock())
    @mock.patch('os.stat', mock.Mock())
    def test__cache_check_existing(self):
        """Test checking if the file already exists in cache and is up to date.
        """
        # Access to a protected member _cache of a client class
        # pylint: disable=W0212
        treadmill.zkutils.get.return_value = {}

        treadmill.zkutils.get_with_metadata.return_value = (
            {}, mock.Mock(ctime=1000)
        )

        zkclient = kazoo.client.KazooClient()

        # File doesn't exist.
        os.stat.side_effect = FileNotFoundError

        self.evmgr._cache(zkclient, 'foo#001', check_existing=True)

        treadmill.fs.write_safe.assert_called()

        # File is up to date.
        treadmill.fs.write_safe.reset_mock()
        os.stat.side_effect = None
        os.stat.return_value = mock.Mock(st_ctime=2)

        self.evmgr._cache(zkclient, 'foo#001', check_existing=True)

        treadmill.fs.write_safe.assert_not_called()

        # File is out of date.
        treadmill.fs.write_safe.reset_mock()
        os.stat.return_value = mock.Mock(st_ctime=0)

        self.evmgr._cache(zkclient, 'foo#001', check_existing=True)

        treadmill.fs.write_safe.assert_called()

    @mock.patch('glob.glob', mock.Mock())
    @mock.patch('treadmill.eventmgr.EventMgr._cache', mock.Mock())
    def test__synchronize(self):
        """Check that app events are synchronized properly."""
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
        """Check synchronized properly remove extra apps."""
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
        """Test sync of placement data.
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
