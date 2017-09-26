"""Unit test for network_service - Treadmill Network configuration service.
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
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

import treadmill
from treadmill.services import network_service


class NetworkServiceTest(unittest.TestCase):
    """Unit tests for the network service implementation.
    """
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('treadmill.netdev.dev_mtu', mock.Mock())
    @mock.patch('treadmill.netdev.dev_speed', mock.Mock())
    @mock.patch('treadmill.services.network_service._device_ip', mock.Mock())
    def test_init(self):
        """Test Network service constructor.
        """
        network_service.NetworkResourceService(
            ext_device='eth42',
        )

        treadmill.netdev.dev_mtu.assert_called_with('eth42')
        treadmill.netdev.dev_speed.assert_called_with('eth42')

    @mock.patch('treadmill.netdev.addr_add', mock.Mock())
    @mock.patch('treadmill.netdev.bridge_addif', mock.Mock())
    @mock.patch('treadmill.netdev.bridge_create', mock.Mock())
    @mock.patch('treadmill.netdev.bridge_delete', mock.Mock())
    @mock.patch('treadmill.netdev.bridge_setfd', mock.Mock())
    @mock.patch('treadmill.netdev.dev_conf_route_localnet_set', mock.Mock())
    @mock.patch('treadmill.netdev.dev_mac',
                mock.Mock(return_value='11:22:33:44:55:66'))
    @mock.patch('treadmill.netdev.dev_mtu', mock.Mock())
    @mock.patch('treadmill.netdev.link_add_veth', mock.Mock())
    @mock.patch('treadmill.netdev.link_del_veth', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_addr', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_down', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_mtu', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_up', mock.Mock())
    @mock.patch('treadmill.services.network_service._device_ip', mock.Mock())
    def test__bridge_initialize(self):
        """Test Network service bridge initialization.
        """
        # Access to a protected member _bridge_initialize
        # pylint: disable=W0212

        svc = network_service.NetworkResourceService(
            ext_device='eth42',
            ext_speed=10000,
            ext_mtu=9000,
        )

        svc._bridge_initialize()

        treadmill.netdev.link_set_down.assert_has_calls(
            [
                mock.call('tm0'),
                mock.call('br0'),
            ]
        )
        treadmill.netdev.link_del_veth.assert_called_with('tm0')
        treadmill.netdev.bridge_delete.assert_has_calls(
            [
                mock.call('tm0'),  # FIXME(boysson): For legacy setup cleanup
                mock.call('br0'),
            ]
        )

        treadmill.netdev.bridge_create.assert_called_with('br0')
        treadmill.netdev.bridge_setfd.assert_called_with('br0', 0)
        # Setup the TM link with the right MTU
        treadmill.netdev.link_add_veth.assert_called_with('tm0', 'tm1')
        treadmill.netdev.link_set_mtu.assert_has_calls(
            [
                mock.call('tm0', 9000),
                mock.call('tm1', 9000),
            ]
        )
        treadmill.netdev.link_set_mtu.assert_called_with('tm1', 9000)
        # Make sure the bridge's address is fixed
        treadmill.netdev.dev_mac.assert_called_with('tm1')
        treadmill.netdev.link_set_addr('br0', '11:22:33:44:55:66')
        # Add one end of the link to the bridge
        treadmill.netdev.bridge_addif.assert_called_with('br0', 'tm1')
        # Everything is brought up
        treadmill.netdev.link_set_up.assert_has_calls(
            [
                mock.call('br0'),
                mock.call('tm1'),
                mock.call('tm0'),
            ]
        )
        # And the TM interface has the right IP
        treadmill.netdev.addr_add.assert_called_with(
            devname='tm0', addr='192.168.254.254/16',
        )
        treadmill.netdev.dev_conf_route_localnet_set.assert_called_with(
            'tm0', True
        )

    @mock.patch('treadmill.iptables.init_set', mock.Mock())
    @mock.patch('treadmill.netdev.bridge_brif',
                mock.Mock(return_value=['foo', 'bar']))
    @mock.patch('treadmill.netdev.bridge_setfd', mock.Mock())
    @mock.patch('treadmill.netdev.dev_conf_route_localnet_set', mock.Mock())
    @mock.patch('treadmill.netdev.dev_mtu', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_up', mock.Mock())
    @mock.patch('treadmill.services.network_service._device_info', mock.Mock())
    @mock.patch('treadmill.services.network_service.NetworkResourceService.'
                '_bridge_initialize', mock.Mock())
    @mock.patch('treadmill.services.network_service._device_ip', mock.Mock())
    @mock.patch('treadmill.vipfile.VipMgr', autospec=True)
    def test_initialize_quick(self, mock_vipmgr):
        """Test service initialization (quick restart).
        """
        # Access to a protected member _device_info of a client class
        # pylint: disable=W0212
        treadmill.services.network_service._device_info.side_effect = \
            lambda dev: {'alias': 'reqid_%s' % dev}
        mock_vipmgr_inst = mock_vipmgr.return_value
        mock_vipmgr_inst.list.return_value = [
            ('192.168.1.2', 'reqid_foo'),
            ('192.168.43.10', 'reqid_bar'),
            ('192.168.8.9', 'reqid_baz'),
        ]

        svc = network_service.NetworkResourceService(
            ext_device='eth42',
            ext_speed=10000,
            ext_mtu=9000,
        )

        svc.initialize(self.root)

        mock_vipmgr.assert_called_with(
            mock.ANY,
            svc._service_rsrc_dir
        )
        self.assertTrue(mock_vipmgr_inst.garbage_collect.called)
        treadmill.iptables.init_set.assert_has_calls(
            [
                mock.call(treadmill.iptables.SET_PROD_CONTAINERS,
                          family='inet', hashsize=1024, maxelem=65536),
                mock.call(treadmill.iptables.SET_NONPROD_CONTAINERS,
                          family='inet', hashsize=1024, maxelem=65536),
            ],
            any_order=True
        )
        treadmill.netdev.link_set_up.assert_has_calls(
            [
                mock.call('tm0'),
                mock.call('tm1'),
                mock.call('br0'),
            ]
        )
        # Re-init is not called
        self.assertFalse(svc._bridge_initialize.called)
        self.assertFalse(mock_vipmgr_inst.initialize.called)

        treadmill.netdev.bridge_setfd.assert_called_with('br0', 0)
        treadmill.netdev.dev_conf_route_localnet_set('tm0', True)
        treadmill.netdev.dev_mtu.assert_called_with('br0')
        treadmill.netdev.bridge_brif('br0')
        treadmill.services.network_service._device_info.assert_has_calls(
            [
                mock.call('foo'),
                mock.call('bar'),
            ]
        )
        mock_vipmgr_inst.free.assert_called_with('reqid_baz', '192.168.8.9')
        self.assertEqual(
            svc._devices,
            {
                'reqid_bar': {
                    'alias': 'reqid_bar',
                    'ip': '192.168.43.10',
                    'stale': True,
                },
                'reqid_foo': {
                    'alias': 'reqid_foo',
                    'ip': '192.168.1.2',
                    'stale': True,
                }
            },
            'All devices must be unified with their IP and marked stale'
        )

    @mock.patch('treadmill.iptables.init_set', mock.Mock())
    @mock.patch('treadmill.netdev.bridge_brif', mock.Mock(return_value=[]))
    @mock.patch('treadmill.netdev.bridge_setfd', mock.Mock())
    @mock.patch('treadmill.netdev.dev_conf_route_localnet_set', mock.Mock())
    @mock.patch('treadmill.netdev.dev_mtu', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_up', mock.Mock())
    @mock.patch('treadmill.services.network_service._device_info', mock.Mock())
    @mock.patch('treadmill.services.network_service._device_ip', mock.Mock())
    @mock.patch('treadmill.services.network_service.NetworkResourceService.'
                '_bridge_initialize', mock.Mock())
    @mock.patch('treadmill.vipfile.VipMgr', autospec=True)
    def test_initialize(self, mock_vipmgr):
        """Test service initialization.
        """
        # Access to a protected member _device_info of a client class
        # pylint: disable=W0212
        treadmill.services.network_service._device_info.side_effect = \
            lambda dev: {'alias': 'reqid_%s' % dev}
        treadmill.netdev.link_set_up.side_effect = [
            subprocess.CalledProcessError('any', 'how'),
            None,
        ]
        mock_vipmgr_inst = mock_vipmgr.return_value
        mock_vipmgr_inst.list.return_value = []

        svc = network_service.NetworkResourceService(
            ext_device='eth42',
            ext_speed=10000,
            ext_mtu=9000,
        )

        svc.initialize(self.root)

        mock_vipmgr.assert_called_with(
            mock.ANY,
            svc._service_rsrc_dir
        )
        self.assertTrue(mock_vipmgr_inst.garbage_collect.called)
        treadmill.iptables.init_set.assert_has_calls(
            [
                mock.call(treadmill.iptables.SET_PROD_CONTAINERS,
                          family='inet', hashsize=1024, maxelem=65536),
                mock.call(treadmill.iptables.SET_NONPROD_CONTAINERS,
                          family='inet', hashsize=1024, maxelem=65536),
            ],
            any_order=True
        )
        treadmill.netdev.link_set_up.assert_called_with('tm0')
        self.assertTrue(svc._bridge_initialize.called)
        self.assertTrue(mock_vipmgr_inst.initialize.called)
        treadmill.netdev.bridge_setfd.assert_called_with('br0', 0)
        treadmill.netdev.dev_mtu.assert_called_with('br0')
        treadmill.netdev.dev_conf_route_localnet_set('tm0', True)
        treadmill.netdev.bridge_brif('br0')
        self.assertFalse(
            treadmill.services.network_service._device_info.called
        )
        self.assertFalse(mock_vipmgr_inst.free.called)
        self.assertEqual(
            svc._devices,
            {}
        )

    @mock.patch('treadmill.services.network_service._device_ip', mock.Mock())
    def test_event_handlers(self):
        """Test event_handlers request.
        """
        svc = network_service.NetworkResourceService(
            ext_device='eth42',
            ext_speed=10000,
            ext_mtu=9000,
        )

        self.assertEqual(
            svc.event_handlers(),
            []
        )

    @mock.patch('treadmill.services.network_service._device_ip',
                mock.Mock(return_value='a.b.c.d'))
    def test_report_status(self):
        """Test service status reporting.
        """
        svc = network_service.NetworkResourceService(
            ext_device='eth42',
            ext_speed=10000,
            ext_mtu=9000,
        )

        status = svc.report_status()

        self.assertEqual(
            status,
            {
                'bridge_dev': 'br0',
                'bridge_mtu': 0,
                'internal_device': 'tm0',
                'internal_ip': '192.168.254.254',
                'devices': {},
                'external_mtu': 9000,
                'external_speed': 10000,
                'external_ip': 'a.b.c.d',
                'external_device': 'eth42',
            }
        )

    @mock.patch('treadmill.iptables.add_mark_rule', mock.Mock())
    @mock.patch('treadmill.netdev.addr_add', mock.Mock())
    @mock.patch('treadmill.netdev.bridge_addif', mock.Mock())
    @mock.patch('treadmill.netdev.link_add_veth', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_alias', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_mtu', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_up', mock.Mock())
    @mock.patch('treadmill.services.network_service._device_info',
                autospec=True)
    @mock.patch('treadmill.services.network_service._device_ip',
                mock.Mock(return_value='1.2.3.4'))
    def test_on_create_request(self, mock_devinfo):
        """Test processing of a network create request.
        """
        # Access to a protected member _devices
        # pylint: disable=W0212

        svc = network_service.NetworkResourceService(
            ext_device='eth42',
            ext_speed=10000,
            ext_mtu=9000,
        )
        svc._vips = mock.Mock()
        mockip = svc._vips.alloc.return_value
        request = {
            'environment': 'dev',
        }
        request_id = 'myproid.test-0-ID1234'
        mock_devinfo.return_value = {'test': 'me'}

        network = svc.on_create_request(request_id, request)

        svc._vips.alloc.assert_called_with(request_id)
        treadmill.netdev.link_add_veth.assert_called_with(
            '0000000ID1234.0', '0000000ID1234.1',
        )
        treadmill.netdev.link_set_mtu.assert_has_calls(
            [
                mock.call('0000000ID1234.0', 9000),
                mock.call('0000000ID1234.1', 9000),
            ]
        )
        treadmill.netdev.link_set_alias.assert_has_calls(
            [
                mock.call('0000000ID1234.0', request_id),
                mock.call('0000000ID1234.1', request_id),
            ]
        )
        treadmill.netdev.bridge_addif.assert_called_with(
            'br0', '0000000ID1234.0'
        )
        treadmill.netdev.link_set_up.assert_called_with(
            '0000000ID1234.0',
        )
        mock_devinfo.assert_called_with('0000000ID1234.0')
        self.assertEqual(
            network,
            {
                'gateway': '192.168.254.254',
                'veth': '0000000ID1234.1',
                'vip': mockip,
                'external_ip': '1.2.3.4',
            }
        )
        self.assertEqual(
            svc._devices,
            {
                request_id: {
                    'environment': 'dev',
                    'ip': mockip,
                    'test': 'me',
                }
            }
        )
        treadmill.iptables.add_mark_rule.assert_called_with(
            mockip, 'dev'
        )

    @mock.patch('treadmill.iptables.add_mark_rule', mock.Mock())
    @mock.patch('treadmill.netdev.addr_add', mock.Mock())
    @mock.patch('treadmill.netdev.bridge_addif', mock.Mock())
    @mock.patch('treadmill.netdev.link_add_veth', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_alias', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_mtu', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_up', mock.Mock())
    @mock.patch('treadmill.services.network_service._device_info',
                autospec=True)
    @mock.patch('treadmill.services.network_service._device_ip',
                mock.Mock(return_value='1.2.3.4'))
    def test_on_create_request_existing(self, mock_devinfo):
        """Test processing of a network create request when the device exists
        (restarts).
        """
        # Access to a protected member _devices
        # pylint: disable=W0212

        svc = network_service.NetworkResourceService(
            ext_device='eth42',
            ext_speed=10000,
            ext_mtu=9000,
        )
        svc._vips = mock.Mock()
        request = {
            'environment': 'dev',
        }
        request_id = 'myproid.test-0-ID1234'
        # Fake the exis
        svc._devices = {
            request_id: {
                'ip': 'old_ip',
            },
        }
        mock_devinfo.return_value = {'test': 'me'}

        network = svc.on_create_request(request_id, request)

        self.assertFalse(svc._vips.alloc.called)
        self.assertFalse(treadmill.netdev.link_add_veth.called)
        self.assertFalse(treadmill.netdev.link_set_mtu.called)
        self.assertFalse(treadmill.netdev.link_set_alias.called)
        self.assertFalse(treadmill.netdev.bridge_addif.called)
        self.assertFalse(treadmill.netdev.link_set_up.called)
        mock_devinfo.assert_called_with('0000000ID1234.0')
        self.assertEqual(
            network,
            {
                'gateway': '192.168.254.254',
                'veth': '0000000ID1234.1',
                'vip': 'old_ip',
                'external_ip': '1.2.3.4',
            }
        )
        self.assertEqual(
            svc._devices,
            {
                request_id: {
                    'environment': 'dev',
                    'ip': 'old_ip',
                    'test': 'me',
                }
            }
        )
        treadmill.iptables.add_mark_rule.assert_called_with(
            'old_ip', 'dev'
        )

    @mock.patch('treadmill.iptables.delete_mark_rule', mock.Mock())
    @mock.patch('treadmill.netdev.dev_state', mock.Mock())
    @mock.patch('treadmill.netdev.link_del_veth', mock.Mock())
    @mock.patch('treadmill.vipfile.VipMgr', autospec=True)
    @mock.patch('treadmill.services.network_service._device_ip', mock.Mock())
    def test_on_delete_request(self, mock_vipmgr):
        """Test processing of a localdisk delete request.
        """
        # Access to a protected member
        # pylint: disable=W0212

        svc = network_service.NetworkResourceService(
            ext_device='eth42',
            ext_speed=10000,
            ext_mtu=9000,
        )
        svc._vips = mock_vipmgr(mock.ANY, mock.ANY)
        request_id = 'myproid.test-0-ID1234'
        svc._devices[request_id] = {
            'ip': 'test_ip',
            'environment': 'test_env',
        }

        svc.on_delete_request(request_id)

        treadmill.netdev.dev_state.assert_called_with(
            '0000000ID1234.0'
        )
        treadmill.netdev.link_del_veth.assert_called_with(
            '0000000ID1234.0'
        )
        treadmill.iptables.delete_mark_rule.assert_called_with(
            'test_ip', 'test_env'
        )
        svc._vips.free.assert_called_with(
            request_id, 'test_ip',
        )


if __name__ == '__main__':
    unittest.main()
