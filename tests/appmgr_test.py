"""
Unit test for treadmill.appmgr.
"""

import os
import shutil
import tempfile
import unittest

import kazoo
import mock

import treadmill
from treadmill import appmgr
from treadmill import context
from treadmill import fs
from treadmill.apptrace import events
from treadmill.appmgr import abort as app_abort
from treadmill.appmgr import initialize as app_init


class AppMgrTest(unittest.TestCase):
    """Tests for teadmill.appmgr."""

    @mock.patch('netifaces.ifaddresses', mock.Mock(
        return_value={
            2: [{'addr': '172.31.81.67',
                 'broadcast': '172.31.81.67',
                 'netmask': '255.255.255.192'}],
            17: [{'addr': 'b4:b5:2f:c2:7c:bf',
                  'broadcast': 'ff:ff:ff:ff:ff:ff'}]
        }
    ))
    @mock.patch('treadmill.services.ResourceService')
    def setUp(self, mock_resource_service):
        # W0221 Arguments number differs from overridden method
        # pylint: disable=W0221
        def _fake_service_factory(impl, *_args, **_kw_args):
            """Generate a unique mock object for each service implementation.
            """
            return mock.Mock(name=impl)
        mock_resource_service.side_effect = _fake_service_factory
        self.root = tempfile.mkdtemp()
        self.app_env = appmgr.AppEnvironment(root=self.root)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def _write_app_yaml(self, event, manifest_str):
        """Helper method to create app.yaml file in the event directory."""
        fs.mkdir_safe(os.path.dirname(event))
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(event),
                                         delete=False, mode='w') as f:
            f.write(manifest_str)
        os.rename(f.name, event)

    @mock.patch('os.kill', mock.Mock())
    @mock.patch('treadmill.iptables.initialize', mock.Mock())
    @mock.patch('treadmill.sysinfo.port_range',
                mock.Mock(return_value=(5050, 65535)))
    def test_initialize(self):
        """Test AppMgr environment initialization.
        """
        app_init.initialize(self.app_env)
        self.assertFalse(os.kill.called)
        treadmill.iptables.initialize.assert_called_with('172.31.81.67')

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

        app_abort.abort(self.app_env, manifest_file, exc=Exception('test'))
        treadmill.appevents.post.assert_called_with(
            mock.ANY,
            events.AbortedTraceEvent(
                instanceid='proid.myapp#001',
                why='Exception',
                payload=None,
            ),
        )

    def test_gen_uniqueid(self):
        """Test generation of app uniqueid.
        """
        manifest = """
---
foo: bar
"""
        event_filename0 = os.path.join(self.root, 'proid.myapp#0')
        self._write_app_yaml(event_filename0, manifest)
        uniqueid1 = appmgr.gen_uniqueid(event_filename0)
        self._write_app_yaml(event_filename0, manifest)
        uniqueid2 = appmgr.gen_uniqueid(event_filename0)

        self.assertTrue(len(uniqueid1) <= 13)
        self.assertNotEquals(uniqueid1, uniqueid2)


if __name__ == '__main__':
    unittest.main()
