"""Unit test for netdev - Linux network device interface
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import errno
import io
import os
import shutil
import tempfile
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import netdev


class NetDevTest(unittest.TestCase):
    """Tests for teadmill.fs."""

    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    @mock.patch('io.open', mock.mock_open())
    @mock.patch('os.listdir', mock.Mock(spec_set=True))
    def test_dev_list(self):
        """Test device listing.
        """
        os.listdir.return_value = [
            'foo', 'bar', 'baz', 'bad',
        ]

        def _mock_open_dispatch(f, **kwargs):
            if f == '/sys/class/net/foo/type':
                return mock.mock_open(read_data='1\n')(f, **kwargs)
            elif f == '/sys/class/net/bar/type':
                return mock.mock_open(read_data='772\n')(f, **kwargs)
            elif f == '/sys/class/net/baz/type':
                return mock.mock_open(read_data='778\n')(f, **kwargs)
            elif f == '/sys/class/net/bad/type':
                return mock.mock_open(read_data='-1\n')(f, **kwargs)
            else:
                return io.open.return_value
        io.open.side_effect = _mock_open_dispatch

        res = netdev.dev_list()

        self.assertEqual(res, ['foo', 'bar', 'baz', 'bad'])
        io.open.reset_mock()

        res = netdev.dev_list(typefilter=netdev.DevType.Ether)

        io.open.assert_has_calls(
            [
                mock.call('/sys/class/net/foo/type'),
                mock.call('/sys/class/net/bar/type'),
                mock.call('/sys/class/net/baz/type'),
            ],
            any_order=True
        )
        self.assertEqual(res, ['foo'])
        io.open.reset_mock()

        self.assertEqual(
            netdev.dev_list(typefilter=netdev.DevType.GRE),
            ['baz']
        )

        self.assertEqual(
            netdev.dev_list(typefilter=netdev.DevType.Loopback),
            ['bar']
        )

    @mock.patch('io.open', mock.mock_open())
    def test_dev_mtu(self):
        """Test device MTU read.
        """
        mock_handle = io.open.return_value
        mock_handle.read.return_value = '1234\n'

        res = netdev.dev_mtu('foo')

        io.open.assert_called_with('/sys/class/net/foo/mtu')
        self.assertEqual(res, 1234)

    @mock.patch('io.open', mock.mock_open())
    def test_dev_mac(self):
        """Test device MAC address read.
        """
        mock_handle = io.open.return_value
        mock_handle.read.return_value = '11:22:33:44:55\n'

        res = netdev.dev_mac('foo')

        io.open.assert_called_with('/sys/class/net/foo/address')
        self.assertEqual(res, '11:22:33:44:55')

    @mock.patch('io.open', mock.mock_open())
    def test_dev_alias(self):
        """Test device alias read.
        """
        mock_handle = io.open.return_value
        mock_handle.read.return_value = 'foo alias\n'

        res = netdev.dev_alias('foo')

        io.open.assert_called_with('/sys/class/net/foo/ifalias')
        self.assertEqual(res, 'foo alias')

    @mock.patch('io.open', mock.mock_open())
    def test_dev_state_up(self):
        """Test device state read.
        """
        mock_handle = io.open.return_value
        mock_handle.read.return_value = 'up\n'

        res = netdev.dev_state('foo')

        io.open.assert_called_with('/sys/class/net/foo/operstate')
        self.assertEqual(res, netdev.DevState.UP)

    @mock.patch('io.open', mock.mock_open())
    def test_dev_state_lldown(self):
        """Test device state read.
        """
        mock_handle = io.open.return_value
        mock_handle.read.return_value = 'lowerlayerdown\n'

        res = netdev.dev_state('foo')

        io.open.assert_called_with('/sys/class/net/foo/operstate')
        self.assertEqual(res, netdev.DevState.LOWER_LAYER_DOWN)

    @mock.patch('io.open', mock.mock_open())
    def test_dev_speed(self):
        """Test device link speed read.
        """
        mock_handle = io.open.return_value
        mock_handle.read.return_value = '10000\n'

        res = netdev.dev_speed('foo')

        io.open.assert_called_with('/sys/class/net/foo/speed')
        self.assertEqual(res, 10000)

    @mock.patch('io.open', mock.mock_open())
    def test_dev_speed_inval(self):
        """Test device link speed read when the device does not support it.
        """
        mock_handle = io.open.return_value
        mock_handle.read.side_effect = IOError(errno.EINVAL, 'Invalid device')

        res = netdev.dev_speed('foo')

        io.open.assert_called_with('/sys/class/net/foo/speed')
        self.assertEqual(res, 0)

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_link_set_up(self):
        """Test of device up."""
        netdev.link_set_up('foo')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'link',
                'set',
                'dev', 'foo',
                'up',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_link_set_down(self):
        """Test of device down."""
        netdev.link_set_down('foo')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'link',
                'set',
                'dev', 'foo',
                'down',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_link_set_name(self):
        """Test of device name change.
        """
        netdev.link_set_name('foo', 'bar')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'link',
                'set',
                'dev', 'foo',
                'name', 'bar',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_link_set_alias(self):
        """Test configuration of device alias.
        """
        netdev.link_set_alias('foo', 'hello world!')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'link',
                'set',
                'dev', 'foo',
                'alias', 'hello world!',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_link_set_mtu(self):
        """Test configuration of device MTU.
        """
        netdev.link_set_mtu('foo', 9000)

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'link',
                'set',
                'dev', 'foo',
                'mtu', '9000',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_link_set_addr(self):
        """Test configuration of device MTU.
        """
        netdev.link_set_addr('foo', '11:22:33:44:55:66')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'link',
                'set',
                'dev', 'foo',
                'address', '11:22:33:44:55:66',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_link_set_netns(self):
        """Test setting of device network namespace.
        """
        netdev.link_set_netns('foo', 123)

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'link',
                'set',
                'dev', 'foo',
                'netns', '123',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_link_add_veth(self):
        """Test definitiion of veth device.
        """
        netdev.link_add_veth('foo', 'bar')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'link',
                'add', 'name', 'foo',
                'type', 'veth',
                'peer', 'name', 'bar'
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_link_del_veth(self):
        """Test veth deletion.
        """
        netdev.link_del_veth('foo')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'link',
                'delete',
                'dev', 'foo',
                'type', 'veth',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_addr_add(self):
        """Test IP address configuration.
        """
        netdev.addr_add('1.2.3.4', 'foo_dev', addr_scope='foo_scope')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'addr',
                'add', '1.2.3.4',
                'dev', 'foo_dev',
                'scope', 'foo_scope',
            ],
        )

        netdev.addr_add('1.2.3.4', 'foo_dev',
                        ptp_addr='3.4.5.6', addr_scope='foo_scope')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'addr',
                'add', '1.2.3.4',
                'peer', '3.4.5.6',
                'dev', 'foo_dev',
                'scope', 'foo_scope',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_route_add(self):
        """Test route definition.
        """
        netdev.route_add('1.2.3.4', via='bar')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'route',
                'add', 'unicast', '1.2.3.4',
                'via', 'bar',
            ],
        )
        treadmill.subproc.check_call.reset_mock()

        netdev.route_add('1.2.3.4', devname='foo_dev')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'route',
                'add', 'unicast', '1.2.3.4',
                'dev', 'foo_dev',
            ],
        )
        treadmill.subproc.check_call.reset_mock()

        netdev.route_add('1.2.3.4', via='bar', src='baz', route_scope='local')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'route',
                'add', 'unicast', '1.2.3.4',
                'via', 'bar',
                'src', 'baz',
                'scope', 'local',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_bridge_create(self):
        """Test bridge interface definition.
        """
        netdev.bridge_create('foo')

        treadmill.subproc.check_call.assert_called_with(
            [
                'brctl', 'addbr', 'foo',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_bridge_delete(self):
        """Test bridge interface deletion.
        """
        netdev.bridge_delete('foo')

        treadmill.subproc.check_call.assert_called_with(
            [
                'brctl', 'delbr', 'foo',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_bridge_setfd(self):
        """Test bridge interface forward-delay configuration.
        """
        netdev.bridge_setfd('foo', 2)

        treadmill.subproc.check_call.assert_called_with(
            [
                'brctl', 'setfd', 'foo', '2'
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_bridge_addif(self):
        """Test bridge interface addition.
        """
        netdev.bridge_addif('foo', 'bar')

        treadmill.subproc.check_call.assert_called_with(
            [
                'brctl', 'addif', 'foo', 'bar',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_bridge_delif(self):
        """Test bridge interface removal.
        """
        netdev.bridge_delif('foo', 'bar')

        treadmill.subproc.check_call.assert_called_with(
            [
                'brctl', 'delif', 'foo', 'bar',
            ],
        )

    @mock.patch('io.open', mock.mock_open())
    def test_bridge_forward_delay(self):
        """Test reading of bridge forward-delay setting.
        """
        mock_handle = io.open.return_value
        mock_handle.read.return_value = '42\n'

        res = netdev.bridge_forward_delay('foo')

        io.open.assert_called_with('/sys/class/net/foo/bridge/forward_delay')
        self.assertEqual(res, 42)

    @mock.patch('os.listdir', mock.Mock(return_value=['a', 'b', 'c']))
    def test_bridge_brif(self):
        """Test reading of bridge interfaces.
        """
        res = netdev.bridge_brif('foo')

        os.listdir.assert_called_with(
            '/sys/class/net/foo/brif'
        )
        self.assertEqual(
            res,
            ['a', 'b', 'c']
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_gre_create(self):
        """Test bridge interface removal.
        """
        netdev.gre_create('bar', 'basedev', '1.2.3.4')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'tunnel',
                'add', 'bar',
                'mode', 'gre',
                'dev', 'basedev',
                'local', '1.2.3.4',
            ],
        )
        treadmill.subproc.check_call.reset_mock()

        netdev.gre_create('bar', 'basedev',
                          '1.2.3.4', '4.3.2.1',
                          66)

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'tunnel',
                'add', 'bar',
                'mode', 'gre',
                'dev', 'basedev',
                'local', '1.2.3.4',
                'remote', '4.3.2.1',
                'key', '0x42',
            ],
        )
        treadmill.subproc.check_call.reset_mock()

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_gre_change(self):
        """Test bridge interface removal.
        """
        netdev.gre_change('bar', key=4242)

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'tunnel',
                'change', 'bar',
                'mode', 'gre',
                'key', '0x1092',
            ],
        )

        netdev.gre_change('bar', remoteaddr='4.4.4.4', key=4242)

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'tunnel',
                'change', 'bar',
                'mode', 'gre',
                'remote', '4.4.4.4',
                'key', '0x1092',
            ],
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_gre_delete(self):
        """Test bridge interface removal.
        """
        netdev.gre_delete('bar')

        treadmill.subproc.check_call.assert_called_with(
            [
                'ip', 'tunnel',
                'del', 'bar',
                'mode', 'gre',
            ],
        )

    @mock.patch('io.open', mock.mock_open())
    def test_dev_conf_route_lnet_set(self):
        """Test enabling to local network routing on interface.
        """
        mock_handle = io.open.return_value

        netdev.dev_conf_route_localnet_set('foo', True)

        io.open.assert_called_with(
            '/proc/sys/net/ipv4/conf/foo/route_localnet', 'w'
        )
        mock_handle.write.assert_called_with('1')

    @mock.patch('io.open', mock.mock_open())
    def test_dev_conf_proxy_arp_set(self):
        """Test enabling of proxy ARP on interface.
        """
        mock_handle = io.open.return_value

        netdev.dev_conf_proxy_arp_set('foo', True)

        io.open.assert_called_with(
            '/proc/sys/net/ipv4/conf/foo/proxy_arp', 'w'
        )
        mock_handle.write.assert_called_with('1')

    @mock.patch('io.open', mock.mock_open())
    def test_dev_conf_arp_ignore_set(self):
        """Test enabling of proxy ARP on interface.
        """
        mock_handle = io.open.return_value

        netdev.dev_conf_arp_ignore_set('foo', 2)

        io.open.assert_called_with(
            '/proc/sys/net/ipv4/conf/foo/arp_ignore', 'w'
        )
        mock_handle.write.assert_called_with('2')

    @mock.patch('io.open', mock.mock_open())
    def test_dev_conf_forwarding_set(self):
        """Test enabling of proxy ARP on interface.
        """
        mock_handle = io.open.return_value

        netdev.dev_conf_forwarding_set('foo', True)

        io.open.assert_called_with(
            '/proc/sys/net/ipv4/conf/foo/forwarding', 'w'
        )
        mock_handle.write.assert_called_with('1')


if __name__ == '__main__':
    unittest.main()
