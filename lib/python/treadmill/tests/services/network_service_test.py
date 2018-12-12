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

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import subproc
from treadmill import services
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

    @mock.patch('treadmill.iptables.create_set', mock.Mock())
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
            '192.168.0.0/16',
            mock.ANY,
            svc._service_rsrc_dir
        )
        mock_vipmgr_inst.garbage_collect.assert_not_called()
        treadmill.iptables.create_set.assert_has_calls(
            [
                mock.call(treadmill.iptables.SET_PROD_CONTAINERS,
                          family='inet', set_type='hash:ip',
                          hashsize=1024, maxelem=65536),
                mock.call(treadmill.iptables.SET_NONPROD_CONTAINERS,
                          family='inet', set_type='hash:ip',
                          hashsize=1024, maxelem=65536),
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
        svc._bridge_initialize.assert_not_called()
        mock_vipmgr_inst.initialize.assert_not_called()

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
        mock_vipmgr_inst.free.assert_not_called()

        self.assertEqual(
            svc._devices,
            {
                'reqid_foo': {
                    'alias': 'reqid_foo',
                    'ip': '192.168.1.2',
                    'stale': True,
                },
                'reqid_bar': {
                    'alias': 'reqid_bar',
                    'ip': '192.168.43.10',
                    'stale': True,
                },
                'reqid_baz': {
                    # No device, so no 'alias'
                    'ip': '192.168.8.9',
                    'stale': True,
                },
            },
            'All devices must be unified with their IP and marked stale'
        )

    @mock.patch('treadmill.iptables.create_set', mock.Mock())
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
            subproc.CalledProcessError('any', 'how'),
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
            '192.168.0.0/16',
            mock.ANY,
            svc._service_rsrc_dir
        )
        mock_vipmgr_inst.garbage_collect.assert_not_called()
        treadmill.iptables.create_set.assert_has_calls(
            [
                mock.call(treadmill.iptables.SET_PROD_CONTAINERS,
                          family='inet', set_type='hash:ip',
                          hashsize=1024, maxelem=65536),
                mock.call(treadmill.iptables.SET_NONPROD_CONTAINERS,
                          family='inet', set_type='hash:ip',
                          hashsize=1024, maxelem=65536),
            ],
            any_order=True
        )
        treadmill.netdev.link_set_up.assert_called_with('tm0')
        svc._bridge_initialize.assert_called()
        mock_vipmgr_inst.initialize.assert_not_called()
        treadmill.netdev.bridge_setfd.assert_called_with('br0', 0)
        treadmill.netdev.dev_mtu.assert_called_with('br0')
        treadmill.netdev.dev_conf_route_localnet_set('tm0', True)
        treadmill.netdev.bridge_brif('br0')
        treadmill.services.network_service._device_info.assert_not_called()
        mock_vipmgr_inst.free.assert_not_called()
        self.assertEqual(
            svc._devices,
            {}
        )

    @mock.patch('treadmill.netdev.dev_mtu', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.dev_speed', mock.Mock(set_spec=True))
    @mock.patch('treadmill.iptables.atomic_set', mock.Mock(set_spec=True))
    @mock.patch('treadmill.vipfile.VipMgr', autospec=True)
    @mock.patch('treadmill.services.network_service._device_ip',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.services.network_service.'
                'NetworkResourceService.on_delete_request',
                mock.Mock(set_spec=True))
    def test_synchronize(self, mock_vipmgr):
        """Test service synchronize.
        """
        # Access to a protected member _device_info of a client class
        # pylint: disable=W0212
        svc = network_service.NetworkResourceService(
            ext_device='eth42',
            ext_speed=10000,
            ext_mtu=9000,
        )
        svc._vips = mock_vipmgr(mock.ANY, mock.ANY, mock.ANY)
        svc._devices = {
            'reqid_foo': {
                'alias': 'reqid_foo',
                'device': '0000000ID5678.0',
                'environment': 'prod',
                'ip': '192.168.1.2',
            },
            'reqid_bar': {
                # Device but no request, no environment
                'alias': 'reqid_bar',
                'device': '0000000ID1234.0',
                'ip': '192.168.43.10',
                'stale': True,
            },
            'reqid_baz': {
                # No device, so no 'alias', 'device'.
                'ip': '192.168.8.9',
                'stale': True,
            },
        }

        def _mock_delete(rsrc_id):
            svc._devices.pop(rsrc_id, None)

        svc.on_delete_request.side_effect = _mock_delete

        svc.synchronize()

        svc.on_delete_request.assert_has_calls(
            [
                mock.call('reqid_bar'),
                mock.call('reqid_baz'),
            ],
            any_order=True
        )
        treadmill.iptables.atomic_set.assert_has_calls(
            [
                mock.call(
                    treadmill.iptables.SET_PROD_CONTAINERS,
                    {'192.168.1.2'},
                    set_type='hash:ip', family='inet',
                    hashsize=1024, maxelem=65536,
                ),
                mock.call(
                    treadmill.iptables.SET_NONPROD_CONTAINERS,
                    set(),
                    set_type='hash:ip', family='inet',
                    hashsize=1024, maxelem=65536,
                ),
            ],
            any_order=True
        )
        res = svc.report_status()
        self.assertEqual(
            res,
            {
                'bridge_dev': 'br0',
                'bridge_mtu': treadmill.netdev.dev_mtu.return_value,
                'devices':
                    {
                        'reqid_foo':
                            {
                                'alias': 'reqid_foo',
                                'device': '0000000ID5678.0',
                                'environment': 'prod',
                                'ip': '192.168.1.2',
                            }
                    },
                'external_device': 'eth42',
                'external_ip': network_service._device_ip.return_value,
                'external_mtu': 9000,
                'external_speed': 10000,
                'internal_device': 'tm0',
                'internal_ip': '192.168.254.254'
            }
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

    @mock.patch('treadmill.netdev.addr_add', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.bridge_addif', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.link_add_veth', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.link_set_alias', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.link_set_mtu', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.link_set_up', mock.Mock(set_spec=True))
    @mock.patch('treadmill.services.network_service._device_info',
                autospec=True)
    @mock.patch('treadmill.services.network_service._device_ip',
                mock.Mock(set_spec=True, return_value='1.2.3.4'))
    @mock.patch('treadmill.services.network_service._add_mark_rule',
                mock.Mock(set_spec=True))
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
        network_service._add_mark_rule.assert_called_with(
            mockip, 'dev'
        )

    @mock.patch('treadmill.netdev.addr_add', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.bridge_addif', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.link_add_veth', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.link_set_alias', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.link_set_mtu', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.link_set_up', mock.Mock(set_spec=True))
    @mock.patch('treadmill.services.network_service._device_info',
                autospec=True)
    @mock.patch('treadmill.services.network_service._device_ip',
                mock.Mock(set_spec=True, return_value='1.2.3.4'))
    @mock.patch('treadmill.services.network_service._add_mark_rule',
                mock.Mock(set_spec=True))
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
                'device': '0000000ID1234.0',
            },
        }
        mock_devinfo.return_value = {'test': 'me'}

        network = svc.on_create_request(request_id, request)

        svc._vips.alloc.assert_not_called()
        treadmill.netdev.link_add_veth.assert_not_called()
        treadmill.netdev.link_set_mtu.assert_not_called()
        treadmill.netdev.link_set_alias.assert_not_called()
        treadmill.netdev.bridge_addif.assert_not_called()
        treadmill.netdev.link_set_up.assert_not_called()
        mock_devinfo.assert_called_with('0000000ID1234.0')
        network_service._add_mark_rule.assert_called_with(
            'old_ip', 'dev'
        )
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

    @mock.patch('treadmill.netdev.dev_state', mock.Mock(set_spec=True))
    @mock.patch('treadmill.netdev.link_del_veth', mock.Mock(set_spec=True))
    @mock.patch('treadmill.vipfile.VipMgr', autospec=True)
    @mock.patch('treadmill.services.network_service._device_ip',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.services.network_service._delete_mark_rule',
                mock.Mock(set_spec=True))
    def test_on_delete_request(self, mock_vipmgr):
        """Test processing of a vip delete request.
        """
        # Access to a protected member
        # pylint: disable=W0212

        svc = network_service.NetworkResourceService(
            ext_device='eth42',
            ext_speed=10000,
            ext_mtu=9000,
        )
        svc._vips = mock_vipmgr(mock.ANY, mock.ANY, mock.ANY)
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
        network_service._delete_mark_rule.assert_called_with(
            'test_ip', 'test_env'
        )
        svc._vips.free.assert_called_with(
            request_id, 'test_ip',
        )

    @mock.patch('treadmill.iptables.add_ip_set', mock.Mock())
    @mock.patch('treadmill.iptables.test_ip_set',
                mock.Mock(return_value=False))
    def test__add_mark_rule(self):
        """Test mark rule addition
        """
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        # Called with the NONPROD interface
        network_service._add_mark_rule('2.2.2.2', 'dev')

        treadmill.iptables.add_ip_set.assert_called_with(
            treadmill.iptables.SET_NONPROD_CONTAINERS, '2.2.2.2'
        )
        treadmill.iptables.test_ip_set.assert_called_with(
            treadmill.iptables.SET_PROD_CONTAINERS, '2.2.2.2'
        )
        treadmill.iptables.add_ip_set.reset_mock()
        treadmill.iptables.test_ip_set.reset_mock()

        # Called with the PROD interface
        network_service._add_mark_rule('3.3.3.3', 'prod')

        treadmill.iptables.add_ip_set.assert_called_with(
            treadmill.iptables.SET_PROD_CONTAINERS, '3.3.3.3'
        )
        treadmill.iptables.test_ip_set.assert_called_with(
            treadmill.iptables.SET_NONPROD_CONTAINERS, '3.3.3.3'
        )

    @mock.patch('treadmill.iptables.add_ip_set', mock.Mock())
    @mock.patch('treadmill.iptables.test_ip_set',
                mock.Mock(return_value=True))
    def test__add_mark_rule_dup(self):
        """Test mark rule addition (integrity error).
        """
        # Access to a protected member _device_info of a client class
        # pylint: disable=W0212
        self.assertRaises(
            Exception,
            network_service._add_mark_rule,
            '2.2.2.2', 'dev'
        )

    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    def test__delete_mark_rule(self):
        """Test mark rule deletion.
        """
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access

        # Called with the NONPROD interface
        network_service._delete_mark_rule('2.2.2.2', 'dev')

        treadmill.iptables.rm_ip_set.assert_called_with(
            treadmill.iptables.SET_NONPROD_CONTAINERS, '2.2.2.2'
        )
        treadmill.iptables.rm_ip_set.reset_mock()

        # Called with the PROD interface
        network_service._delete_mark_rule('4.4.4.4', 'prod')

        treadmill.iptables.rm_ip_set.assert_called_with(
            treadmill.iptables.SET_PROD_CONTAINERS, '4.4.4.4'
        )

    def test_load(self):
        """Test loading service using alias."""
        # pylint: disable=W0212
        self.assertEqual(
            network_service.NetworkResourceService,
            services.ResourceService(self.root, 'network')._load_impl()
        )


if __name__ == '__main__':
    unittest.main()
