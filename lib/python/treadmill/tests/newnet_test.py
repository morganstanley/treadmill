"""Unit test for newnet - configuring unshared network subsystem.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import multiprocessing
import os
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import newnet


class NewnetTest(unittest.TestCase):
    """Mock test for treadmill.newnet."""

    @mock.patch('multiprocessing.synchronize.Event', mock.Mock())
    @mock.patch('os.fork', mock.Mock(return_value=1234))
    @mock.patch('os.getpid', mock.Mock(return_value=7777))
    @mock.patch('os.waitpid', mock.Mock(return_value=(1234, 0)))
    @mock.patch('treadmill.syscall.unshare.unshare', mock.Mock(return_value=0))
    @mock.patch('treadmill.newnet._configure_veth', mock.Mock())
    def test_create_newnet_parent(self):
        """Tests configuring unshared network (parent)"""
        # Access protected _configure_veth
        # pylint: disable=W0212
        mock_event = multiprocessing.synchronize.Event.return_value

        newnet.create_newnet(
            'foo1234', '192.168.0.100', '192.168.254.254', '10.0.0.1',
        )

        treadmill.syscall.unshare.unshare.assert_called_with(
            treadmill.syscall.unshare.CLONE_NEWNET
        )
        self.assertTrue(mock_event.set.called)
        os.waitpid.assert_called_with(1234, 0)
        treadmill.newnet._configure_veth.assert_called_with(
            'foo1234', '192.168.0.100', '192.168.254.254', '10.0.0.1',
        )

    @mock.patch('multiprocessing.synchronize.Event', mock.Mock())
    @mock.patch('os.fork', mock.Mock(return_value=0))
    @mock.patch('os.getpid', mock.Mock(return_value=7777))
    @mock.patch('treadmill.netdev.link_set_netns', mock.Mock())
    @mock.patch('treadmill.utils.sys_exit', mock.Mock())
    def test_create_newnet_child(self):
        """Tests configuring veth pair (child)"""
        mock_event = multiprocessing.synchronize.Event.return_value

        newnet.create_newnet(
            'foo1234', '192.168.0.100', '192.168.254.254', '10.0.0.1',
        )

        self.assertTrue(mock_event.wait.called)
        treadmill.netdev.link_set_netns.assert_called_with(
            'foo1234', 7777,
        )
        treadmill.utils.sys_exit.assert_called_with(0)

    @mock.patch('treadmill.iptables.initialize_container', mock.Mock())
    @mock.patch('treadmill.netdev.addr_add', mock.Mock())
    @mock.patch('treadmill.netdev.dev_conf_arp_ignore_set', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_name', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_up', mock.Mock())
    @mock.patch('treadmill.netdev.route_add', mock.Mock())
    def test__configure_veth(self):
        """Tests configuring container networking.
        """
        # Access protected _configure_veth
        # pylint: disable=W0212
        newnet._configure_veth(
            'test1234', '192.168.0.100', '192.168.254.254'
        )

        treadmill.netdev.link_set_up.assert_has_calls(
            [
                mock.call('lo'),
                mock.call('eth0'),
            ]
        )
        treadmill.netdev.dev_conf_arp_ignore_set.assert_called_with('eth0', 3)
        treadmill.netdev.addr_add.assert_called_with(
            '192.168.0.100/32', 'eth0', addr_scope='link'
        )
        treadmill.netdev.route_add.assert_has_calls(
            [
                mock.call(
                    '192.168.254.254',
                    devname='eth0',
                    route_scope='link'
                ),
                mock.call(
                    'default',
                    via='192.168.254.254',
                    src='192.168.0.100',
                )
            ]
        )
        self.assertTrue(treadmill.iptables.initialize_container.called)

    @mock.patch('treadmill.iptables.initialize_container', mock.Mock())
    @mock.patch('treadmill.iptables.add_raw_rule', mock.Mock())
    @mock.patch('treadmill.netdev.addr_add', mock.Mock())
    @mock.patch('treadmill.netdev.dev_conf_arp_ignore_set', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_name', mock.Mock())
    @mock.patch('treadmill.netdev.link_set_up', mock.Mock())
    @mock.patch('treadmill.netdev.route_add', mock.Mock())
    def test__configure_veth_service_ip(self):
        """Tests configuring container networking with service ip.
        """
        # Access protected _configure_veth
        # pylint: disable=W0212
        newnet._configure_veth(
            'test1234', '192.168.0.100', '192.168.254.254', '10.0.0.1',
        )

        treadmill.netdev.link_set_up.assert_has_calls(
            [
                mock.call('lo'),
                mock.call('eth0'),
            ]
        )
        treadmill.netdev.dev_conf_arp_ignore_set.assert_called_with('eth0', 3)
        treadmill.netdev.addr_add.assert_has_calls(
            [
                mock.call('10.0.0.1/32', 'eth0', addr_scope='host'),
                mock.call('192.168.0.100/32', 'eth0', addr_scope='link'),
            ]
        )
        treadmill.netdev.route_add.assert_has_calls(
            [
                mock.call(
                    '192.168.254.254',
                    devname='eth0',
                    route_scope='link'
                ),
                mock.call(
                    'default',
                    via='192.168.254.254',
                    src='10.0.0.1',
                )
            ]
        )
        self.assertTrue(treadmill.iptables.initialize_container.called)
        treadmill.iptables.add_raw_rule.assert_has_calls(
            [
                mock.call('nat', 'PREROUTING',
                          '-i eth0 -j DNAT --to-destination 10.0.0.1'),
                mock.call('nat', 'POSTROUTING',
                          '-o eth0  -j SNAT --to-source 192.168.0.100'),
            ]
        )


if __name__ == '__main__':
    unittest.main()
