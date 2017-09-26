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


class MockEvent(object):
    """Mock Kazoo Event object."""

    def __init__(self, etype='ANY'):
        self.type = etype


class MockStat(object):
    """Mock ZnodeStat for convinience."""
    # C0103: Invalid name "ephemeralOwner"
    # pylint: disable=C0103
    def __init__(self, created=0, modified=None, ephemeralOwner=42):
        self.created = created
        self.last_modified = created
        self.ctime = self.created * 1000
        if modified is not None:
            self.last_modified = modified
        else:
            self.last_modified = created
        self.mtime = self.last_modified * 1000
        self.ephemeralOwner = ephemeralOwner


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

    # XXX(boysson): Test disabled for now
    # @mock.patch('treadmill.eventmgr.EventMgr._cache_notify', mock.Mock())
    # @mock.patch('treadmill.zkutils.connect', autospec=True)
    # def test_run(self, mock_connect):
    #     """.
    #     """
    #     # Access to a protected member _cache_notify of a client class
    #     # pylint: disable=W0212
    #     self.evmgr.run()
    #
    #     mock_watchdog = self.evmgr.tm_env.watchdogs
    #     mock_watchdog.create.assert_called_with(
    #         content=mock.ANY,
    #         name='svc:EventMgr',
    #         timeout='60s'
    #     )
    #     mock_watchdog_lease = mock_watchdog.create.return_value
    #     mock_watchdog_lease.heartbeat.assert_called_with()
    #
    #     mock_zkconnect = mock_connect.return_value
    #     mock_zkconnect.handler.event_object.assert_called_with()
    #
    #     mock_seen = mock_zkconnect.handler.event_object.return_value
    #     mock_seen.clear.assert_called_with()
    #
    #     treadmill.eventmgr.EventMgr._cache_notify.assert_called_with()
    #
    #     mock_zkconnect.DataWatch.assert_called_with(
    #         '/some/path',
    #     )
    #
    #     # The main loop terminates immediately
    #
    #     mock_watchdog_lease.remove.assert_called_with()

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
        """Tests sync of placement data."""
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


if __name__ == '__main__':
    unittest.main()
