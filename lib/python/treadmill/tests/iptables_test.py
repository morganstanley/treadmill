"""Unit test for iptables - manipulating iptables rules.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import time
import unittest

import mock
import pkg_resources

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
from treadmill import firewall
from treadmill import iptables
from treadmill import subproc

# Disable C0302: Too many lines
# pylint: disable=C0302


def _test_data(name):
    data_path = os.path.join('data', name)
    with pkg_resources.resource_stream(__name__, data_path) as f:
        return f.read().decode()


class IptablesTest(unittest.TestCase):
    """Mock test for treadmill.iptables."""

    def setUp(self):
        # Note: These two match the content of NAT_TABLE_SAVE
        self.dnat_rules = set([
            firewall.DNATRule(proto='udp',
                              dst_ip='172.31.81.67', dst_port=5002,
                              new_ip='192.168.1.13', new_port=8000),
            firewall.DNATRule(proto='tcp',
                              dst_ip='172.31.81.67', dst_port=5000,
                              new_ip='192.168.0.11', new_port=8000),
            firewall.DNATRule(proto='tcp',
                              dst_ip='172.31.81.67', dst_port=5003,
                              new_ip='192.168.1.13', new_port=22),
            firewall.DNATRule(proto='tcp',
                              dst_ip='172.31.81.67', dst_port=5001,
                              new_ip='192.168.0.11', new_port=22),
        ])
        self.snat_rules = set([
            firewall.SNATRule(proto='udp',
                              src_ip='192.168.0.3', src_port=22,
                              new_ip='172.31.81.67', new_port=5001),
        ])
        self.passthrough_rules = set([
            firewall.PassThroughRule(src_ip='10.197.19.18',
                                     dst_ip='192.168.3.2'),
            firewall.PassThroughRule(src_ip='10.197.19.19',
                                     dst_ip='192.168.2.2'),
        ])

        self.iptables_state = _test_data('iptables_state.save')
        self.iptables_empty_state = _test_data('iptables_empty_state.save')
        self.iptables_filter_state = _test_data('iptables_filter_state.save')
        self.ipset_state = _test_data('ipset_state.save')
        self.nat_table_save = _test_data('iptables_test_nat_table.save')

    @mock.patch('treadmill.iptables.flush_set', mock.Mock(set_spec=True))
    @mock.patch('treadmill.iptables.add_ip_set', mock.Mock(set_spec=True))
    @mock.patch('treadmill.iptables.ipset_restore', mock.Mock(set_spec=True))
    @mock.patch('treadmill.iptables.create_chain', mock.Mock(set_spec=True))
    @mock.patch('treadmill.iptables._iptables_restore',
                mock.Mock(set_spec=True))
    def test_initialize(self):
        """Test iptables initialization"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access

        # NOTE: keep this IP in sync with the tests' state file dumps
        iptables.initialize('1.2.3.4')

        treadmill.iptables.ipset_restore.assert_called_with(
            self.ipset_state
        )
        treadmill.iptables._iptables_restore.assert_called_with(
            self.iptables_state
        )

    @mock.patch('treadmill.iptables.create_chain', mock.Mock(set_spec=True))
    @mock.patch('treadmill.iptables._iptables_restore',
                mock.Mock(set_spec=True))
    def test_filter_table_set(self):
        """Test filter table initialization.
        """
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access

        # NOTE: keep this sync with the tests' filter state file dump.
        iptables.filter_table_set(['one rule', 'two rule'], ['other rule'])

        treadmill.iptables.create_chain.assert_called_with(
            'filter', 'TM_EXCEPTION_FILTER'
        )
        treadmill.iptables._iptables_restore.assert_called_with(
            self.iptables_filter_state, noflush=True
        )

    @mock.patch('treadmill.subproc.invoke', mock.Mock(return_value=(0, '')))
    def test_iptables_restore(self):
        """Test iptables-restore util"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        iptables._iptables_restore('firewall_state', noflush=True)

        treadmill.subproc.invoke.assert_called_with(
            ['iptables_restore', '--noflush'],
            cmd_input='firewall_state',
            use_except=True
        )

    @mock.patch('treadmill.subproc.invoke', mock.Mock(return_value=(0, '')))
    def test_initialize_container(self):
        """Test iptables container initialization"""
        iptables.initialize_container()

        treadmill.subproc.invoke.assert_called_with(
            ['iptables_restore'],
            cmd_input=self.iptables_empty_state,
            use_except=True,
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_add_raw_rule(self):
        """Test adding iptable rule."""
        iptables.add_raw_rule('nat', 'OUTPUT', '-j FOO', safe=False)
        treadmill.subproc.check_call.assert_called_with(
            ['iptables', '-t', 'nat', '-A', 'OUTPUT', '-j', 'FOO']
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_delete_raw_rule(self):
        """Test deleting an iptable rule."""
        iptables.delete_raw_rule('nat', 'OUTPUT', '-j FOO')

        treadmill.subproc.check_call.assert_called_with(
            ['iptables', '-t', 'nat', '-D', 'OUTPUT', '-j', 'FOO']
        )
        treadmill.subproc.check_call.reset_mock()

        treadmill.subproc.check_call.side_effect = (
            treadmill.subproc.CalledProcessError(1, '1.4.7 style')
        )

        # Should not raise
        iptables.delete_raw_rule('nat', 'OUTPUT', '-j FOO')

        treadmill.subproc.check_call.reset_mock()

        # Should not raise
        treadmill.subproc.check_call.side_effect = (
            treadmill.subproc.CalledProcessError(2, '1.4.21 style')
        )

        iptables.delete_raw_rule('nat', 'OUTPUT', '-j FOO')

        treadmill.subproc.check_call.reset_mock()

        treadmill.subproc.check_call.side_effect = (
            treadmill.subproc.CalledProcessError(42, 'other error')
        )

        self.assertRaises(
            treadmill.subproc.CalledProcessError,
            iptables.delete_raw_rule,
            'nat', 'OUTPUT', '-j FOO'
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_add_raw_rule_safe(self):
        """Test adding iptable rule (safe)."""
        treadmill.subproc.check_call.return_value = 0

        iptables.add_raw_rule('nat', 'OUTPUT', '-j FOO', safe=True)

        treadmill.subproc.check_call.assert_called_once_with(
            ['iptables', '-t', 'nat', '-C', 'OUTPUT', '-j', 'FOO']
        )

        # Rule does not exist.
        treadmill.subproc.check_call.reset_mock()

        treadmill.subproc.check_call.side_effect = [
            subproc.CalledProcessError(1, ''),
            0,
        ]

        iptables.add_raw_rule('nat', 'OUTPUT', '-j FOO', safe=True)

        treadmill.subproc.check_call.assert_has_calls([
            mock.call(['iptables', '-t', 'nat', '-C', 'OUTPUT', '-j', 'FOO']),
            mock.call(['iptables', '-t', 'nat', '-A', 'OUTPUT', '-j', 'FOO'])
        ])

        # Unexpected iptables error while checking if the rule already exists.
        treadmill.subproc.check_call.reset_mock()

        treadmill.subproc.check_call.side_effect = \
            subproc.CalledProcessError(3, '')

        with self.assertRaises(subproc.CalledProcessError):
            iptables.add_raw_rule('nat', 'OUTPUT', '-j FOO', safe=True)

    @mock.patch('treadmill.iptables.add_raw_rule', mock.Mock())
    def test_add_dnat_rule(self):
        """Test dnat rule addition."""
        iptables.add_dnat_rule(
            firewall.DNATRule(proto='tcp',
                              dst_ip='1.1.1.1', dst_port=123,
                              new_ip='2.2.2.2', new_port=345),
            'SOME_RULE',
            safe=True
        )

        treadmill.iptables.add_raw_rule.assert_called_with(
            'nat', 'SOME_RULE',
            ('-s 0.0.0.0/0 -d 1.1.1.1 -p tcp -m tcp --dport 123'
             ' -j DNAT --to-destination 2.2.2.2:345'),
            True
        )

    @mock.patch('treadmill.iptables.delete_raw_rule', mock.Mock())
    def test_delete_dnat_rule(self):
        """Test dnat rule deletion."""
        iptables.delete_dnat_rule(
            firewall.DNATRule(proto='tcp',
                              dst_ip='1.1.1.1', dst_port=123,
                              new_ip='2.2.2.2', new_port=345),
            'SOME_RULE'
        )

        treadmill.iptables.delete_raw_rule.assert_called_with(
            'nat', 'SOME_RULE',
            ('-s 0.0.0.0/0 -d 1.1.1.1 -p tcp -m tcp --dport 123'
             ' -j DNAT --to-destination 2.2.2.2:345')
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    def test_delete_dnat_rule_nonexist(self):
        """Test dnat rule deleting when the rule does not exist."""
        treadmill.subproc.check_call.side_effect = \
            subproc.CalledProcessError(returncode=1, output='', cmd='')

        iptables.delete_dnat_rule(
            firewall.DNATRule(proto='tcp',
                              dst_ip='1.1.1.1', dst_port=123,
                              new_ip='2.2.2.2', new_port=345),
            'SOME_RULE',
        )

        treadmill.subproc.check_call.assert_called_with([
            'iptables', '-t', 'nat', '-D', 'SOME_RULE',
            '-s', '0.0.0.0/0', '-d', '1.1.1.1', '-p', 'tcp', '-m', 'tcp',
            '--dport', '123',
            '-j', 'DNAT', '--to-destination', '2.2.2.2:345'])

    @mock.patch('treadmill.iptables.add_raw_rule', mock.Mock())
    def test_add_snat_rule(self):
        """Test snat rule addition."""
        iptables.add_snat_rule(
            firewall.SNATRule(proto='tcp',
                              src_ip='1.1.1.1', src_port=123,
                              new_ip='2.2.2.2', new_port=345),
            'SOME_RULE',
            safe=True
        )

        treadmill.iptables.add_raw_rule.assert_called_with(
            'nat', 'SOME_RULE',
            ('-s 1.1.1.1 -d 0.0.0.0/0 -p tcp -m tcp --sport 123'
             ' -j SNAT --to-source 2.2.2.2:345'),
            True
        )

    @mock.patch('treadmill.iptables.delete_raw_rule', mock.Mock())
    def test_delete_snat_rule(self):
        """Test snat rule deletion."""
        iptables.delete_snat_rule(
            firewall.SNATRule(proto='tcp',
                              src_ip='1.1.1.1', src_port=123,
                              new_ip='2.2.2.2', new_port=345),
            'SOME_RULE'
        )

        treadmill.iptables.delete_raw_rule.assert_called_with(
            'nat', 'SOME_RULE',
            ('-s 1.1.1.1 -d 0.0.0.0/0 -p tcp -m tcp --sport 123'
             ' -j SNAT --to-source 2.2.2.2:345')
        )

    @mock.patch('treadmill.iptables.add_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables._get_current_dnat_rules', mock.Mock())
    def test_dnat_up_to_date(self):
        """Tests DNAT setup when configuration is up to date.
        """
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.iptables._get_current_dnat_rules.return_value = \
            self.dnat_rules

        iptables.configure_dnat_rules(
            self.dnat_rules,
            iptables.PREROUTING_DNAT
        )

        self.assertEqual(0, treadmill.iptables.add_dnat_rule.call_count)
        self.assertEqual(0, treadmill.iptables.delete_dnat_rule.call_count)

    @mock.patch('treadmill.iptables.add_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables._get_current_dnat_rules', mock.Mock())
    def test_dnat_missing_rule(self):
        """Tests DNAT setup when new rule needs to be created.
        """
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.iptables._get_current_dnat_rules.return_value = \
            self.dnat_rules
        desired_rules = (
            self.dnat_rules |
            set([
                firewall.DNATRule('tcp',
                                  '172.31.81.67', 5004,
                                  '192.168.2.15', 22),
            ])
        )

        iptables.configure_dnat_rules(
            desired_rules,
            iptables.PREROUTING_DNAT
        )

        treadmill.iptables.add_dnat_rule.assert_called_with(
            firewall.DNATRule('tcp',
                              '172.31.81.67', 5004,
                              '192.168.2.15', 22),
            chain=iptables.PREROUTING_DNAT
        )
        self.assertEqual(0, treadmill.iptables.delete_dnat_rule.call_count)

    @mock.patch('treadmill.iptables.add_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables._get_current_dnat_rules', mock.Mock())
    def test_dnat_extra_rule(self):
        """Tests DNAT setup when rule needs to be removed."""
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.iptables._get_current_dnat_rules.return_value = (
            self.dnat_rules |
            set([
                firewall.DNATRule('tcp',
                                  '172.31.81.67', 5004,
                                  '192.168.2.15', 22),
            ])
        )
        desired_rules = (
            self.dnat_rules
        )

        iptables.configure_dnat_rules(
            desired_rules,
            iptables.PREROUTING_DNAT
        )

        self.assertEqual(0, treadmill.iptables.add_dnat_rule.call_count)
        treadmill.iptables.delete_dnat_rule.assert_called_with(
            firewall.DNATRule('tcp',
                              '172.31.81.67', 5004,
                              '192.168.2.15', 22),
            chain=iptables.PREROUTING_DNAT,
        )

    @mock.patch('treadmill.subproc.check_output', mock.Mock())
    def test__get_current_dnat_rules(self):
        """Test query DNAT/SNAT rules."""
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.subproc.check_output.return_value = \
            self.nat_table_save

        rules = iptables._get_current_dnat_rules(iptables.PREROUTING_DNAT)

        treadmill.subproc.check_output.assert_called_with(
            ['iptables',
             '-t', 'nat', '-S', iptables.PREROUTING_DNAT]
        )
        self.assertEqual(set(rules), self.dnat_rules)

    @mock.patch('treadmill.iptables.add_snat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_snat_rule', mock.Mock())
    @mock.patch('treadmill.iptables._get_current_snat_rules', mock.Mock())
    def test_snat_up_to_date(self):
        """Tests SNAT setup when configuration is up to date.
        """
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.iptables._get_current_snat_rules.return_value = \
            self.snat_rules

        iptables.configure_snat_rules(
            self.snat_rules,
            iptables.POSTROUTING_SNAT
        )

        self.assertEqual(0, treadmill.iptables.add_snat_rule.call_count)
        self.assertEqual(0, treadmill.iptables.delete_snat_rule.call_count)

    @mock.patch('treadmill.iptables.add_snat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_snat_rule', mock.Mock())
    @mock.patch('treadmill.iptables._get_current_snat_rules', mock.Mock())
    def test_snat_missing_rule(self):
        """Tests DNAT setup when new rule needs to be created.
        """
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.iptables._get_current_snat_rules.return_value = \
            self.snat_rules
        desired_rules = (
            self.snat_rules |
            set([
                firewall.SNATRule('tcp',
                                  '172.31.81.67', 5004,
                                  '192.168.2.15', 22),
            ])
        )

        iptables.configure_snat_rules(
            desired_rules,
            iptables.POSTROUTING_SNAT
        )

        treadmill.iptables.add_snat_rule.assert_called_with(
            firewall.SNATRule('tcp',
                              '172.31.81.67', 5004,
                              '192.168.2.15', 22),
            chain=iptables.POSTROUTING_SNAT
        )
        self.assertEqual(0, treadmill.iptables.delete_snat_rule.call_count)

    @mock.patch('treadmill.iptables.add_snat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_snat_rule', mock.Mock())
    @mock.patch('treadmill.iptables._get_current_snat_rules', mock.Mock())
    def test_snat_extra_rule(self):
        """Tests SNAT setup when rule needs to be removed.
        """
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.iptables._get_current_snat_rules.return_value = (
            self.snat_rules |
            set([
                firewall.SNATRule('tcp',
                                  '172.31.81.67', 5004,
                                  '192.168.2.15', 22),
            ])
        )
        desired_rules = (
            self.snat_rules
        )

        iptables.configure_snat_rules(
            desired_rules,
            iptables.PREROUTING_DNAT
        )

        self.assertEqual(0, treadmill.iptables.add_snat_rule.call_count)
        treadmill.iptables.delete_snat_rule.assert_called_with(
            firewall.SNATRule('tcp',
                              '172.31.81.67', 5004,
                              '192.168.2.15', 22),
            chain=iptables.PREROUTING_DNAT
        )

    @mock.patch('treadmill.subproc.check_output', mock.Mock())
    def test__get_current_snat_rules(self):
        """Test query DNAT/SNAT rules."""
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.subproc.check_output.return_value = \
            self.nat_table_save

        rules = iptables._get_current_snat_rules(iptables.POSTROUTING_SNAT)

        treadmill.subproc.check_output.assert_called_with(
            ['iptables',
             '-t', 'nat', '-S', iptables.POSTROUTING_SNAT]
        )
        self.assertEqual(set(rules), self.snat_rules)

    @mock.patch('treadmill.iptables.add_raw_rule', mock.Mock())
    def test_add_passthrough_rule(self):
        """Test configure_passthrough."""
        iptables.add_passthrough_rule(
            firewall.PassThroughRule(src_ip='4.4.4.4', dst_ip='1.2.3.4'),
            iptables.PREROUTING_PASSTHROUGH
        )

        treadmill.iptables.add_raw_rule.assert_called_with(
            'nat', iptables.PREROUTING_PASSTHROUGH,
            '-s 4.4.4.4 -j DNAT --to-destination 1.2.3.4',
            safe=False
        )

    @mock.patch('treadmill.iptables.delete_raw_rule', mock.Mock())
    def test_delete_passthrough_rule(self):
        """Test deletion of a passthrough rule"""
        iptables.delete_passthrough_rule(
            firewall.PassThroughRule(src_ip='4.4.4.4', dst_ip='1.2.3.4'),
            iptables.PREROUTING_PASSTHROUGH
        )

        treadmill.iptables.delete_raw_rule.assert_called_with(
            'nat', iptables.PREROUTING_PASSTHROUGH,
            '-s 4.4.4.4 -j DNAT --to-destination 1.2.3.4'
        )

    @mock.patch('treadmill.iptables.delete_raw_rule', mock.Mock())
    def test_delete_passthrough_rule2(self):
        """Test deletion of a passthrough rule (no conntrack data)"""
        # Check that ret_code 1 from conntrack -D is treated as success.
        iptables.delete_passthrough_rule(
            firewall.PassThroughRule(src_ip='5.5.5.5', dst_ip='1.2.3.4'),
            iptables.PREROUTING_PASSTHROUGH
        )

        treadmill.iptables.delete_raw_rule.assert_called_with(
            'nat', iptables.PREROUTING_PASSTHROUGH,
            '-s 5.5.5.5 -j DNAT --to-destination 1.2.3.4'
        )

    @mock.patch('treadmill.iptables.add_passthrough_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_passthrough_rule', mock.Mock())
    @mock.patch('treadmill.iptables._get_current_passthrough_rules',
                mock.Mock())
    def test_passthrough_up_to_date(self):
        """Tests PassThrough setup when configuration is up to date."""
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.iptables._get_current_passthrough_rules.return_value = \
            self.passthrough_rules
        passthroughs = self.passthrough_rules

        iptables.configure_passthrough_rules(
            passthroughs,
            iptables.PREROUTING_PASSTHROUGH
        )

        self.assertEqual(
            0, treadmill.iptables.add_passthrough_rule.call_count
        )
        self.assertEqual(
            0, treadmill.iptables.delete_passthrough_rule.call_count
        )

    @mock.patch('treadmill.iptables.add_passthrough_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_passthrough_rule', mock.Mock())
    @mock.patch('treadmill.iptables._get_current_passthrough_rules',
                mock.Mock())
    def test_passthrough_missing_rule(self):
        """Tests PassThrough setup when new rule needs to be created."""
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.iptables._get_current_passthrough_rules.return_value = \
            self.passthrough_rules
        missing_rule = firewall.PassThroughRule(src_ip='10.197.19.20',
                                                dst_ip='192.168.2.2')
        passthroughs = self.passthrough_rules | set([missing_rule, ])

        iptables.configure_passthrough_rules(
            passthroughs,
            iptables.PREROUTING_PASSTHROUGH
        )

        treadmill.iptables.add_passthrough_rule.assert_called_with(
            missing_rule,
            chain=iptables.PREROUTING_PASSTHROUGH
        )
        self.assertEqual(
            0, treadmill.iptables.delete_passthrough_rule.call_count
        )

    @mock.patch('treadmill.iptables.add_passthrough_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_passthrough_rule', mock.Mock())
    @mock.patch('treadmill.iptables._get_current_passthrough_rules',
                mock.Mock())
    def test_passthrough_extra_rule(self):
        """Tests PassThrough setup when rule needs to be removed."""
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.iptables._get_current_passthrough_rules.return_value = \
            self.passthrough_rules
        extra_rule = firewall.PassThroughRule(src_ip='10.197.19.19',
                                              dst_ip='192.168.2.2')

        passthroughs = self.passthrough_rules - set([extra_rule, ])

        iptables.configure_passthrough_rules(
            passthroughs,
            iptables.PREROUTING_PASSTHROUGH
        )

        self.assertEqual(
            0, treadmill.iptables.add_passthrough_rule.call_count
        )
        treadmill.iptables.delete_passthrough_rule.assert_called_with(
            extra_rule,
            chain=iptables.PREROUTING_PASSTHROUGH
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(autospec=True))
    def test_flush_cnt_conntrack_table(self):
        """Test flushing container conntrack rules.
        """
        treadmill.subproc.check_call.return_value = 0

        treadmill.iptables.flush_cnt_conntrack_table(vip='5.5.5.5')

        treadmill.subproc.check_call.assert_has_calls(
            [
                mock.call(
                    [
                        'conntrack',
                        '-D',
                        '--protonum', 'udp',
                        '--src-nat', '5.5.5.5'
                    ]
                ),
                mock.call(
                    [
                        'conntrack',
                        '-D',
                        '--protonum', 'udp',
                        '--dst-nat', '5.5.5.5'
                    ]
                ),
            ],
            any_order=True
        )

        treadmill.subproc.check_call.reset_mock()
        treadmill.subproc.check_call.return_value = 1
        treadmill.subproc.check_call.side_effect = \
            subproc.CalledProcessError(returncode=1, cmd='failed conntrack')

        treadmill.iptables.flush_cnt_conntrack_table('4.4.4.4')

        treadmill.subproc.check_call.assert_has_calls(
            [
                mock.call(
                    [
                        'conntrack',
                        '-D',
                        '--protonum', 'udp',
                        '--src-nat', '4.4.4.4'
                    ]
                ),
                mock.call(
                    [
                        'conntrack',
                        '-D',
                        '--protonum', 'udp',
                        '--dst-nat', '4.4.4.4'
                    ]
                ),
            ],
            any_order=True
        )

    @mock.patch('treadmill.subproc.check_call', mock.Mock(autospec=True))
    def test_flush_pt_conntrack_table(self):
        """Test flushing Passthrough conntrack rules.
        """
        treadmill.subproc.check_call.return_value = 0

        treadmill.iptables.flush_pt_conntrack_table('5.5.5.5')

        treadmill.subproc.check_call.assert_has_calls(
            [
                mock.call(
                    [
                        'conntrack',
                        '-D',
                        '--protonum', 'udp',
                        '--orig-src', '5.5.5.5'
                    ]
                ),
                mock.call(
                    [
                        'conntrack',
                        '-D',
                        '--protonum', 'udp',
                        '--orig-dst', '5.5.5.5'
                    ]
                ),
            ],
            any_order=True
        )

        treadmill.subproc.check_call.reset_mock()
        treadmill.subproc.check_call.return_value = 1
        treadmill.subproc.check_call.side_effect = \
            subproc.CalledProcessError(returncode=1, cmd='failed conntrack')

        treadmill.iptables.flush_pt_conntrack_table('4.4.4.4')

        treadmill.subproc.check_call.assert_has_calls(
            [
                mock.call(
                    [
                        'conntrack',
                        '-D',
                        '--protonum', 'udp',
                        '--orig-src', '4.4.4.4'
                    ]
                ),
                mock.call(
                    [
                        'conntrack',
                        '-D',
                        '--protonum', 'udp',
                        '--orig-dst', '4.4.4.4'
                    ]
                ),
            ],
            any_order=True
        )

    @mock.patch('treadmill.subproc.check_output', mock.Mock())
    def test__get_current_pt_rules(self):
        """Test query passthrough rules."""
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.subproc.check_output.return_value = \
            self.nat_table_save

        rules = iptables._get_current_passthrough_rules(
            iptables.PREROUTING_PASSTHROUGH
        )

        treadmill.subproc.check_output.assert_called_with(
            ['iptables',
             '-t', 'nat', '-S', iptables.PREROUTING_PASSTHROUGH]
        )
        self.assertEqual(set(rules), self.passthrough_rules)

    @mock.patch('treadmill.iptables.add_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.add_passthrough_rule', mock.Mock())
    def test_add_rule(self):
        """Test generic addition of a rule"""
        dnat_rule = self.dnat_rules.pop()
        passthrough_rule = self.passthrough_rules.pop()

        iptables.add_rule(dnat_rule, chain='TEST_CHAIN')

        self.assertEqual(
            0, treadmill.iptables.add_passthrough_rule.call_count
        )
        treadmill.iptables.add_dnat_rule.assert_called_with(
            dnat_rule,
            chain='TEST_CHAIN'
        )

        treadmill.iptables.add_passthrough_rule.reset_mock()
        treadmill.iptables.add_dnat_rule.reset_mock()

        iptables.add_rule(passthrough_rule, chain='TEST_CHAIN')

        treadmill.iptables.add_passthrough_rule.assert_called_with(
            passthrough_rule,
            chain='TEST_CHAIN'
        )
        self.assertEqual(
            0, treadmill.iptables.add_dnat_rule.call_count
        )

    @mock.patch('treadmill.iptables.delete_dnat_rule', mock.Mock())
    @mock.patch('treadmill.iptables.delete_passthrough_rule', mock.Mock())
    def test_delete_rule(self):
        """Test generic removal of a rule"""
        dnat_rule = self.dnat_rules.pop()
        passthrough_rule = self.passthrough_rules.pop()

        iptables.delete_rule(dnat_rule, chain='TEST_CHAIN')

        self.assertEqual(
            0, treadmill.iptables.delete_passthrough_rule.call_count
        )
        treadmill.iptables.delete_dnat_rule.assert_called_with(
            dnat_rule,
            chain='TEST_CHAIN'
        )

        treadmill.iptables.delete_passthrough_rule.reset_mock()
        treadmill.iptables.delete_dnat_rule.reset_mock()

        iptables.delete_rule(passthrough_rule, chain='TEST_CHAIN')

        treadmill.iptables.delete_passthrough_rule.assert_called_with(
            passthrough_rule,
            chain='TEST_CHAIN'
        )
        self.assertEqual(
            0, treadmill.iptables.delete_dnat_rule.call_count
        )

    @mock.patch('time.sleep', mock.Mock(spec_set=True))
    @mock.patch('treadmill.subproc.check_call', mock.Mock(spec_set=True))
    def test__iptables(self):
        """Test iptables command invocation.
        """
        # pylint: disable=protected-access

        res = iptables._iptables('foo', 'bar', 'baz')

        treadmill.subproc.check_call.assert_called_with(
            ['iptables', '-t', 'foo', 'bar', 'baz']
        )
        self.assertEqual(res, treadmill.subproc.check_call.return_value)
        treadmill.subproc.check_call.reset_mock()

        res = iptables._iptables(
            'foo', 'bar', 'baz',
            ['-d', 'some_host', '-p', 'tcp']
        )
        treadmill.subproc.check_call.assert_called_with(
            [
                'iptables', '-t', 'foo', 'bar', 'baz',
                '-d', 'some_host', '-p', 'tcp'
            ]
        )
        self.assertEqual(res, treadmill.subproc.check_call.return_value)
        treadmill.subproc.check_call.reset_mock()

        mock_res = mock.Mock(name='finally!')
        treadmill.subproc.check_call.side_effect = [
            treadmill.subproc.CalledProcessError(4, 'locked'),
            mock_res,
        ]

        res = iptables._iptables('foo', 'bar', 'baz')

        treadmill.subproc.check_call.assert_called_with(
            ['iptables', '-t', 'foo', 'bar', 'baz']
        )
        time.sleep.assert_has_calls(
            [mock.ANY] * 1
        )
        self.assertEqual(time.sleep.call_count, 1)
        self.assertEqual(res, mock_res)
        treadmill.subproc.check_call.reset_mock()

        treadmill.subproc.check_call.side_effect = (
            treadmill.subproc.CalledProcessError('not 4', 'something else')
        )

        self.assertRaises(
            treadmill.subproc.CalledProcessError,
            iptables._iptables,
            'foo', 'bar', 'baz'
        )

    @mock.patch('time.sleep', mock.Mock(spec_set=True))
    @mock.patch('treadmill.subproc.check_output', mock.Mock(spec_set=True))
    def test__iptables_output(self):
        """Test iptables command invocation.
        """
        # pylint: disable=protected-access

        res = iptables._iptables_output('foo', 'bar', 'baz')

        treadmill.subproc.check_output.assert_called_with(
            ['iptables', '-t', 'foo', 'bar', 'baz']
        )
        self.assertEqual(res, treadmill.subproc.check_output.return_value)
        treadmill.subproc.check_output.reset_mock()

        mock_res = mock.Mock(name='finally!')
        treadmill.subproc.check_output.side_effect = [
            treadmill.subproc.CalledProcessError(4, 'locked'),
            treadmill.subproc.CalledProcessError(4, 'locked'),
            mock_res,
        ]

        res = iptables._iptables_output('foo', 'bar', 'baz')

        treadmill.subproc.check_output.assert_called_with(
            ['iptables', '-t', 'foo', 'bar', 'baz']
        )
        time.sleep.assert_has_calls(
            [mock.ANY] * 2
        )
        self.assertEqual(time.sleep.call_count, 2)
        self.assertEqual(res, mock_res)
        treadmill.subproc.check_output.reset_mock()

        treadmill.subproc.check_output.side_effect = (
            treadmill.subproc.CalledProcessError('not 4', 'something else')
        )

        self.assertRaises(
            treadmill.subproc.CalledProcessError,
            iptables._iptables_output,
            'foo', 'bar', 'baz'
        )

    @mock.patch('treadmill.subproc.invoke', mock.Mock(return_value=(0, '')))
    def test__ipset(self):
        """Test ipset tool invocation.
        """
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access

        treadmill.subproc.invoke.return_value = (123, 'test data')

        res = iptables._ipset('foo', 'bar', cmd_input='test')

        treadmill.subproc.invoke.assert_called_with(
            ['ipset', 'foo', 'bar'],

            cmd_input='test',
            use_except=True
        )
        self.assertEqual(
            res,
            (123, 'test data')
        )

    @mock.patch('treadmill.iptables._ipset', mock.Mock())
    def test_list_set(self):
        """Test listing set membership.
        """
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        iptables._ipset.return_value = (
            42,
            """
<ipset name="tm:prod-containers">
  <type>hash:ip</type>
  <header>
    <family>inet</family>
    <hashsize>1024</hashsize>
    <maxelem>65536</maxelem>
    <memsize>16520</memsize>
    <references>3</references>
  </header>
  <members>
    <member>192.168.0.2</member>
    <member>192.168.0.7</member>
  </members>
</ipset>
            """
        )

        res = iptables.list_set('tm:prod-containers')
        iptables._ipset.assert_called_with(
            'list', '-o', 'xml', 'tm:prod-containers'
        )
        self.assertAlmostEqual(
            res,
            ['192.168.0.2', '192.168.0.7']
        )

    @mock.patch('treadmill.iptables._ipset', mock.Mock())
    def test_init_set(self):
        """Test set initialization"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        iptables.init_set('foo')

        treadmill.iptables._ipset.assert_has_calls([
            mock.call('-exist', 'create', 'foo', 'hash:ip'),
            mock.call('flush', 'foo'),
        ])

    @mock.patch('treadmill.iptables._ipset', mock.Mock())
    def test_test_ip_set(self):
        """Test testing of IP in a given set"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        iptables._ipset.return_value = (42, 'foo')

        res = iptables.test_ip_set('foo', '1.2.3.4')

        treadmill.iptables._ipset.assert_called_with(
            'test', 'foo', '1.2.3.4', use_except=False,
        )
        self.assertFalse(res)
        # Try with success now
        iptables._ipset.reset_mock()
        iptables._ipset.return_value = (0, 'bar')

        res = iptables.test_ip_set('foo', '1.2.3.4')
        self.assertTrue(res)

    @mock.patch('treadmill.iptables._ipset', mock.Mock())
    def test_add_ip_set(self):
        """Test addition of IP to a given set"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        iptables.add_ip_set('foo', '1.2.3.4')

        treadmill.iptables._ipset.assert_called_with(
            '-exist', 'add', 'foo', '1.2.3.4'
        )

    @mock.patch('treadmill.iptables._ipset', mock.Mock())
    def test_rm_ip_set(self):
        """Test removal of IP from a given set"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        iptables.rm_ip_set('foo', '1.2.3.4')

        treadmill.iptables._ipset.assert_called_with(
            '-exist', 'del', 'foo', '1.2.3.4'
        )

    @mock.patch('treadmill.iptables._ipset', mock.Mock())
    def test_swap_set(self):
        """Test swapping of two IPSets.
        """
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        iptables.swap_set('from', 'to')

        treadmill.iptables._ipset.assert_called_with(
            'swap', 'from', 'to'
        )

    @mock.patch('treadmill.iptables._ipset', mock.Mock())
    def test_ipset_restore(self):
        """Test the state restore functionality of IPSet"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        iptables.ipset_restore('Initial IPSet state')

        treadmill.iptables._ipset.assert_called_with(
            '-exist', 'restore', cmd_input='Initial IPSet state'
        )

    @mock.patch('treadmill.iptables.create_set', mock.Mock())
    @mock.patch('treadmill.iptables.destroy_set', mock.Mock())
    @mock.patch('treadmill.iptables.flush_set', mock.Mock())
    @mock.patch('treadmill.iptables.ipset_restore', mock.Mock())
    @mock.patch('treadmill.iptables.swap_set', mock.Mock())
    def test_atomic_set(self):
        """Test atomic replacement of IPSet content.
        """
        test_content = (x for x in ['a', 'b', 'c'])
        iptables.atomic_set('target', test_content,
                            'some:type', foo='bar')

        iptables.create_set.assert_called_with(
            mock.ANY, set_type='some:type', foo='bar'
        )
        tmp_set = iptables.create_set.call_args[0][0]

        iptables.ipset_restore.assert_called_with(
            (
                "add {tmp_set} a\n"
                "add {tmp_set} b\n"
                "add {tmp_set} c"
            ).format(tmp_set=tmp_set)
        )
        iptables.swap_set.assert_called_with(
            'target', tmp_set
        )
        iptables.destroy_set.assert_called_with(
            tmp_set
        )


if __name__ == '__main__':
    unittest.main()
