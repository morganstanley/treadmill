"""Unit test for treadmill.appcfg.abort
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import json
import os
import shutil
import tempfile
import unittest

import kazoo
import mock

import treadmill
from treadmill import appenv
from treadmill import context
from treadmill import fs
from treadmill.trace.app import events
from treadmill.appcfg import abort as app_abort


class AppCfgAbortTest(unittest.TestCase):
    """Tests for teadmill.appcfg.abort"""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.tm_env = appenv.AppEnvironment(root=self.root)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.appcfg.abort.flag_aborted', mock.Mock())
    @mock.patch('treadmill.supervisor.control_service', mock.Mock())
    def test_abort(self):
        """Tests abort sequence."""
        container_dir = os.path.join(self.root, 'apps', 'proid.myapp#001',
                                     'data')
        fs.mkdir_safe(container_dir)

        app_abort.abort(container_dir,
                        why=app_abort.AbortedReason.INVALID_TYPE,
                        payload='test')

        treadmill.appcfg.abort.flag_aborted.assert_called_with(
            container_dir,
            app_abort.AbortedReason.INVALID_TYPE,
            'test'
        )

        treadmill.supervisor.control_service.assert_called_with(
            os.path.join(self.root, 'apps', 'proid.myapp#001'),
            treadmill.supervisor.ServiceControlAction.down
        )

    def test_flag_aborted(self):
        """Tests flag abort sequence."""
        container_dir = os.path.join(self.root, 'apps', 'proid.myapp#001',
                                     'data')
        fs.mkdir_safe(container_dir)

        app_abort.flag_aborted(container_dir,
                               why=app_abort.AbortedReason.INVALID_TYPE,
                               payload='test')

        aborted_file = os.path.join(container_dir, 'aborted')
        with io.open(aborted_file) as f:
            aborted = json.load(f)

        self.assertEqual('invalid_type', aborted.get('why'))
        self.assertEqual('test', aborted.get('payload'))

    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.trace.post', mock.Mock())
    @mock.patch('treadmill.sysinfo.hostname',
                mock.Mock(return_value='xxx.xx.com'))
    @mock.patch('treadmill.zkutils.connect', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    def test_report_aborted(self):
        """Tests report abort sequence."""
        context.GLOBAL.zk.url = 'zookeeper://xxx@hhh:123/treadmill/mycell'
        treadmill.zkutils.connect.return_value = kazoo.client.KazooClient()
        kazoo.client.KazooClient.get_children.return_value = []
        kazoo.client.KazooClient.exists.return_value = True

        kazoo.client.KazooClient.create.reset()
        kazoo.client.KazooClient.delete.reset()

        app_abort.report_aborted(self.tm_env, 'proid.myapp#001',
                                 why=app_abort.AbortedReason.TICKETS,
                                 payload='test')
        treadmill.trace.post.assert_called_with(
            mock.ANY,
            events.AbortedTraceEvent(
                instanceid='proid.myapp#001',
                why='tickets',
                payload='test',
            ),
        )


if __name__ == '__main__':
    unittest.main()
