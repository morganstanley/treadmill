"""Unit test for iptables - manipulating iptables rules.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import socket
import unittest

import mock

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import vring


class VRingTest(unittest.TestCase):
    """Mock test for treadmill.vring."""

    @mock.patch('treadmill.sysinfo.hostname', mock.Mock())
    @mock.patch('treadmill.rulefile.RuleMgr', mock.Mock(set_spec=True))
    @mock.patch('socket.gethostbyname', mock.Mock())
    @mock.patch('treadmill.discovery.Discovery.iteritems', mock.Mock())
    def test_run(self):
        """Test vring."""
        dns = {
            'xxx.xx.com': '1.1.1.1',
            'yyy.xx.com': '2.2.2.2',
            'zzz.xx.com': '3.3.3.3',
        }

        def _mock_gethostbyname(hostname):
            res = dns.get(hostname, None)
            if res is not None:
                return res
            raise socket.gaierror(-2, 'Name or service not known')
        socket.gethostbyname.side_effect = _mock_gethostbyname

        treadmill.sysinfo.hostname.return_value = 'zzz.xx.com'
        mock_discovery = treadmill.discovery.Discovery(None, 'a.a', None)
        mock_rulemgr = treadmill.rulefile.RuleMgr('/test', '/owners')
        treadmill.discovery.Discovery.iteritems.return_value = [
            ('proid.foo#123:tcp:tcp_ep', 'xxx.xx.com:12345'),
            ('proid.foo#123:udp:udp_ep', 'xxx.xx.com:23456'),
            ('proid.foo#123:tcp:other_tcp_ep', 'xxx.xx.com:34567'),
            ('proid.foo#124:tcp:tcp_ep', 'zzz.xx.com:12345'),
            ('proid.foo#124:udp:udp_ep', 'zzz.xx.com:23456'),
            ('proid.foo#124:tcp:other_tcp_ep', 'zzz.xx.com:34567'),
            ('proid.foo#666:tcp:tcp_ep', 'bad:12345'),
            ('proid.foo#666:udp:udp_ep', 'bad:23456'),
            ('proid.foo#666:tcp:other_tcp_ep', 'zzz.xx.com:34567'),
            ('proid.foo#125:tcp:tcp_ep', 'yyy.xx.com:45678'),
            ('proid.foo#125:udp:udp_ep', 'yyy.xx.com:56789'),
            ('proid.foo#125:tcp:other_tcp_ep', 'yyy.xx.com:34567'),
        ]

        vring.run(
            {
                'tcp_ep': {
                    'port': 10000,
                    'proto': 'tcp',
                },
                'udp_ep': {
                    'port': 11000,
                    'proto': 'udp'
                },
            },
            ['tcp_ep', 'udp_ep'],
            mock_discovery,
            mock_rulemgr,
            '192.168.7.7',
            'proid.foo#124'
        )

        # Ignore all but tcp0 endpoints.
        #
        # Ignore tcp2 as it is not listed in the port map.
        mock_rulemgr.create_rule.assert_has_calls(
            [
                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='tcp',
                        src_ip='192.168.7.7',
                        dst_ip='3.3.3.3', dst_port=10000,
                        new_ip='192.168.7.7', new_port=10000
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='udp',
                        src_ip='192.168.7.7',
                        dst_ip='3.3.3.3', dst_port=11000,
                        new_ip='192.168.7.7', new_port=11000
                    ),
                    owner='proid.foo#124'
                ),

                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='tcp',
                        src_ip='192.168.7.7',
                        dst_ip='1.1.1.1', dst_port=10000,
                        new_ip='1.1.1.1', new_port=12345
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_SNAT,
                    rule=treadmill.firewall.SNATRule(
                        proto='tcp',
                        src_ip='1.1.1.1', src_port=12345,
                        dst_ip='192.168.7.7',
                        new_ip='1.1.1.1', new_port=10000
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='udp',
                        src_ip='192.168.7.7',
                        dst_ip='1.1.1.1', dst_port=11000,
                        new_ip='1.1.1.1', new_port=23456
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_SNAT,
                    rule=treadmill.firewall.SNATRule(
                        proto='udp',
                        src_ip='1.1.1.1', src_port=23456,
                        dst_ip='192.168.7.7',
                        new_ip='1.1.1.1', new_port=11000
                    ),
                    owner='proid.foo#124'
                ),

                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='tcp',
                        src_ip='192.168.7.7',
                        dst_ip='2.2.2.2', dst_port=10000,
                        new_ip='2.2.2.2', new_port=45678,
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_SNAT,
                    rule=treadmill.firewall.SNATRule(
                        proto='tcp',
                        src_ip='2.2.2.2', src_port=45678,
                        dst_ip='192.168.7.7',
                        new_ip='2.2.2.2', new_port=10000
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='udp',
                        src_ip='192.168.7.7',
                        dst_ip='2.2.2.2', dst_port=11000,
                        new_ip='2.2.2.2', new_port=56789,
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_SNAT,
                    rule=treadmill.firewall.SNATRule(
                        proto='udp',
                        src_ip='2.2.2.2', src_port=56789,
                        dst_ip='192.168.7.7',
                        new_ip='2.2.2.2', new_port=11000
                    ),
                    owner='proid.foo#124'
                ),
            ],
            any_order=True
        )
        self.assertEqual(mock_rulemgr.create_rule.call_count, 10)

        mock_rulemgr.create_rule.reset_mock()
        ############
        treadmill.discovery.Discovery.iteritems.return_value = [
            ('proid.foo#123:tcp:tcp_ep', 'xxx.xx.com:12345'),
            ('proid.foo#123:udp:udp_ep', 'xxx.xx.com:23456'),
            ('proid.foo#123:tcp:other_tcp_ep', 'xxx.xx.com:34567'),
            ('proid.foo#124:tcp:tcp_ep', 'zzz.xx.com:12345'),
            ('proid.foo#124:udp:udp_ep', 'zzz.xx.com:23456'),
            ('proid.foo#124:tcp:other_tcp_ep', 'zzz.xx.com:34567'),
            ('proid.foo#123:tcp:tcp_ep', None),
            ('proid.foo#123:udp:udp_ep', None),
            ('proid.foo#123:tcp:other_tcp_ep', None),
            ('proid.foo#125:tcp:tcp_ep', None),
            ('proid.foo#125:udp:udp_ep', None),
            ('proid.foo#125:tcp:other_tcp_ep', None),
        ]

        vring.run(
            {
                'tcp_ep': {
                    'port': 10000,
                    'proto': 'tcp',
                },
                'udp_ep': {
                    'port': 11000,
                    'proto': 'udp'
                },
            },
            ['tcp_ep', 'udp_ep'],
            mock_discovery,
            mock_rulemgr,
            '192.168.7.7',
            'proid.foo#124'
        )

        mock_rulemgr.create_rule.assert_has_calls(
            [
                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='tcp',
                        src_ip='192.168.7.7',
                        dst_ip='3.3.3.3', dst_port=10000,
                        new_ip='192.168.7.7', new_port=10000
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='udp',
                        src_ip='192.168.7.7',
                        dst_ip='3.3.3.3', dst_port=11000,
                        new_ip='192.168.7.7', new_port=11000
                    ),
                    owner='proid.foo#124'
                ),

                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='tcp',
                        src_ip='192.168.7.7',
                        dst_ip='1.1.1.1', dst_port=10000,
                        new_ip='1.1.1.1', new_port=12345
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_SNAT,
                    rule=treadmill.firewall.SNATRule(
                        proto='tcp',
                        src_ip='1.1.1.1', src_port=12345,
                        dst_ip='192.168.7.7',
                        new_ip='1.1.1.1', new_port=10000
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='udp',
                        src_ip='192.168.7.7',
                        dst_ip='1.1.1.1', dst_port=11000,
                        new_ip='1.1.1.1', new_port=23456
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_SNAT,
                    rule=treadmill.firewall.SNATRule(
                        proto='udp',
                        src_ip='1.1.1.1', src_port=23456,
                        dst_ip='192.168.7.7',
                        new_ip='1.1.1.1', new_port=11000
                    ),
                    owner='proid.foo#124'
                ),
            ],
            any_order=True
        )
        self.assertEqual(mock_rulemgr.create_rule.call_count, 6)
        # Check the rule is removed for foo#123 but not foo#125.
        mock_rulemgr.unlink_rule.assert_has_calls(
            [
                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='tcp',
                        src_ip='192.168.7.7',
                        dst_ip='1.1.1.1', dst_port=10000,
                        new_ip='1.1.1.1', new_port=12345
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_SNAT,
                    rule=treadmill.firewall.SNATRule(
                        proto='tcp',
                        src_ip='1.1.1.1', src_port=12345,
                        dst_ip='192.168.7.7',
                        new_ip='1.1.1.1', new_port=10000
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_DNAT,
                    rule=treadmill.firewall.DNATRule(
                        proto='udp',
                        src_ip='192.168.7.7',
                        dst_ip='1.1.1.1', dst_port=11000,
                        new_ip='1.1.1.1', new_port=23456
                    ),
                    owner='proid.foo#124'
                ),
                mock.call(
                    chain=treadmill.iptables.VRING_SNAT,
                    rule=treadmill.firewall.SNATRule(
                        proto='udp',
                        src_ip='1.1.1.1', src_port=23456,
                        dst_ip='192.168.7.7',
                        new_ip='1.1.1.1', new_port=11000
                    ),
                    owner='proid.foo#124'
                ),
            ],
            any_order=True
        )
        self.assertEqual(mock_rulemgr.unlink_rule.call_count, 4)


if __name__ == '__main__':
    unittest.main()
