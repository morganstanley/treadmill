"""Unit test for iptables - manipulating iptables rules.
"""

import socket
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

import treadmill
from treadmill import vring


class VRingTest(unittest.TestCase):
    """Mock test for treadmill.vring."""

    @mock.patch('treadmill.iptables.add_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.configure_dnat_rules', mock.Mock())
    @mock.patch('treadmill.discovery.Discovery.iteritems', mock.Mock())
    @mock.patch('socket.gethostbyname', mock.Mock())
    def test_run(self):
        """Test vring."""
        dns = {
            'xxx.xx.com': '1.1.1.1',
            'yyy.xx.com': '2.2.2.2'
        }

        socket.gethostbyname.side_effect = lambda hostname: dns[hostname]

        mock_discovery = treadmill.discovery.Discovery(None, 'a.a', None)
        treadmill.discovery.Discovery.iteritems.return_value = [
            ('foo:tcp0', 'xxx.xx.com:12345'),
            ('foo:tcp1', 'xxx.xx.com:23456'),
            ('foo:tcp2', 'xxx.xx.com:34567'),
            ('bla:tcp0', 'yyy.xx.com:54321'),
        ]
        vring.run('ring_0', {'tcp0': 10000, 'tcp1': 11000}, ['tcp0'],
                  mock_discovery)

        # Ignore all but tcp0 endpoints.
        #
        # Ignore tcp2 as it is not listed in the port map.
        treadmill.iptables.add_dnat_rule.assert_has_calls([
            mock.call(('1.1.1.1', 10000, '1.1.1.1', '12345'), chain='ring_0'),
            mock.call(('2.2.2.2', 10000, '2.2.2.2', '54321'), chain='ring_0'),
        ])

        treadmill.iptables.add_dnat_rule.reset()
        treadmill.discovery.Discovery.iteritems.return_value = [
            ('foo:tcp0', 'xxx.xx.com:12345'),
            ('foo:tcp1', 'xxx.xx.com:23456'),
            ('foo:tcp2', 'xxx.xx.com:34567'),
            ('bla:tcp0', 'yyy.xx.com:54321'),
            ('foo:tcp0', None),
        ]
        vring.run('ring_0', {'tcp0': 10000, 'tcp1': 11000}, ['tcp0'],
                  mock_discovery)

        treadmill.iptables.add_dnat_rule.assert_has_calls([
            mock.call(('1.1.1.1', 10000, '1.1.1.1', '12345'), chain='ring_0'),
            mock.call(('2.2.2.2', 10000, '2.2.2.2', '54321'), chain='ring_0'),
        ])
        # Check the rule is removed for foo:tcp0 endpoint.
        treadmill.iptables.delete_dnat_rule.assert_has_calls([
            mock.call(('1.1.1.1', 10000, '1.1.1.1', '12345'), chain='ring_0')
        ])


if __name__ == '__main__':
    unittest.main()
