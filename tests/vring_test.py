"""Unit test for iptables - manipulating iptables rules.
"""

import socket
import unittest

import mock

import treadmill
from treadmill import vring


class VRingTest(unittest.TestCase):
    """Mock test for treadmill.vring."""

    @mock.patch('treadmill.iptables.add_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.configure_dnat_rules', mock.Mock())
    @mock.patch('treadmill.discovery.Discovery.items', mock.Mock())
    @mock.patch('socket.gethostbyname', mock.Mock())
    def test_run(self):
        """Test vring."""
        dns = {
            'xxx.xx.com': '1.1.1.1',
            'yyy.xx.com': '2.2.2.2'
        }

        socket.gethostbyname.side_effect = lambda hostname: dns[hostname]

        mock_discovery = treadmill.discovery.Discovery(None, 'a.a', None)
        treadmill.discovery.Discovery.items.return_value = [
            ('proid.foo#123:tcp:tcp_ep', 'xxx.xx.com:12345'),
            ('proid.foo#123:udp:udp_ep', 'xxx.xx.com:23456'),
            ('proid.foo#123:tcp:other_tcp_ep', 'xxx.xx.com:34567'),
            ('proid.bla#123:tcp:tcp_ep', 'yyy.xx.com:54321'),
        ]
        vring.run('ring_0',
                  {'tcp_ep': 10000, 'udp_ep': 11000},
                  ['tcp_ep', 'udp_ep'],
                  mock_discovery)

        # Ignore all but tcp0 endpoints.
        #
        # Ignore tcp2 as it is not listed in the port map.
        treadmill.iptables.add_dnat_rule.assert_has_calls(
            [
                mock.call(
                    treadmill.firewall.DNATRule(
                        'tcp',
                        '1.1.1.1', 10000,
                        '1.1.1.1', '12345'
                    ),
                    chain='ring_0'
                ),
                mock.call(
                    treadmill.firewall.DNATRule(
                        'tcp',
                        '2.2.2.2', 10000,
                        '2.2.2.2', '54321'
                    ),
                    chain='ring_0'
                ),
                mock.call(
                    treadmill.firewall.DNATRule(
                        'udp',
                        '1.1.1.1', 11000,
                        '1.1.1.1', '23456'
                    ),
                    chain='ring_0'
                ),
            ],
            any_order=True
        )

        treadmill.iptables.add_dnat_rule.reset()
        treadmill.discovery.Discovery.items.return_value = [
            ('proid.foo#123:tcp:tcp_ep', 'xxx.xx.com:12345'),
            ('proid.foo#123:udp:udp_ep', 'xxx.xx.com:23456'),
            ('proid.foo#123:tcp:other_tcp_ep', 'xxx.xx.com:34567'),
            ('proid.bla#123:tcp:tcp_ep', 'yyy.xx.com:54321'),
            ('proid.foo#123:tcp:tcp_ep', None),
            ('proid.foo#123:udp:udp_ep', None),
        ]
        vring.run(
            'ring_0',
            {'tcp_ep': 10000, 'udp_ep': 11000},
            ['tcp_ep', 'udp_ep'],
            mock_discovery
        )

        treadmill.iptables.add_dnat_rule.assert_has_calls(
            [
                mock.call(
                    treadmill.firewall.DNATRule(
                        'tcp',
                        '1.1.1.1', 10000,
                        '1.1.1.1', '12345'
                    ),
                    chain='ring_0'
                ),
                mock.call(
                    treadmill.firewall.DNATRule(
                        'tcp',
                        '2.2.2.2', 10000,
                        '2.2.2.2', '54321'
                    ),
                    chain='ring_0'
                ),
                mock.call(
                    treadmill.firewall.DNATRule(
                        'udp',
                        '1.1.1.1', 11000,
                        '1.1.1.1', '23456'
                    ),
                    chain='ring_0'
                ),
            ],
            any_order=True
        )
        # Check the rule is removed for foo:tcp0 endpoint.
        treadmill.iptables.delete_dnat_rule.assert_has_calls(
            [
                mock.call(
                    treadmill.firewall.DNATRule(
                        'tcp',
                        '1.1.1.1', 10000,
                        '1.1.1.1', '12345'
                    ),
                    chain='ring_0'
                ),
                mock.call(
                    treadmill.firewall.DNATRule(
                        'udp',
                        '1.1.1.1', 11000,
                        '1.1.1.1', '23456'
                    ),
                    chain='ring_0'
                ),
            ],
            any_order=True
        )


if __name__ == '__main__':
    unittest.main()
