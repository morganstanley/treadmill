"""
Unit test for treadmill.appcfg.abort
"""

import os
import shutil
import tempfile
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import kazoo
import mock

import treadmill
from treadmill import appenv
from treadmill import context
from treadmill.apptrace import events
from treadmill.appcfg import abort as app_abort


class AppCfgAbortTest(unittest.TestCase):
    """Tests for teadmill.appcfg.abort"""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.tm_env = appenv.AppEnvironment(root=self.root)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.appevents.post', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='xxx.xx.com'))
    @mock.patch('treadmill.zkutils.connect', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    def test_abort(self):
        """Tests abort sequence."""
        context.GLOBAL.zk.url = 'zookeeper://xxx@hhh:123/treadmill/mycell'
        treadmill.zkutils.connect.return_value = kazoo.client.KazooClient()
        kazoo.client.KazooClient.get_children.return_value = []
        kazoo.client.KazooClient.exists.return_value = True

        # Check abort sequence when name is not part of the manifest, rather
        # derived from the manifest appname.
        manifest_file = os.path.join(self.root, 'schema', 'proid.myapp#001')

        kazoo.client.KazooClient.create.reset()
        kazoo.client.KazooClient.delete.reset()

        app_abort.abort(self.tm_env, manifest_file, exc=StandardError('test'))
        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            events.AbortedTraceEvent(
                instanceid='proid.myapp#001',
                why='StandardError',
                payload=None,
            ),
        )

if __name__ == '__main__':
    unittest.main()
