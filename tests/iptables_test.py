"""Unit test for iptables - manipulating iptables rules.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import unittest

import mock
import six

if six.PY2 and os.name == 'posix':
    import subprocess32 as subprocess  # pylint: disable=import-error
else:
    import subprocess  # pylint: disable=wrong-import-order

import treadmill
from treadmill import firewall
from treadmill import iptables


class IptablesTest(unittest.TestCase):
    """Mock test for treadmill.iptables."""

    IPTABLES_STATE = os.path.join(
        os.path.dirname(__file__),
        'iptables_state.save'
    )

    IPTABLES_EMPTY_STATE = os.path.join(
        os.path.dirname(__file__),
        'iptables_empty_state.save'
    )

    IPTABLES_FILTER_STATE = os.path.join(
        os.path.dirname(__file__),
        'iptables_filter_state.save'
    )

    IPTABLES_FILTER_DROP_STATE = os.path.join(
        os.path.dirname(__file__),
        'iptables_filter_drop_state.save'
    )

    IPSET_STATE = os.path.join(
        os.path.dirname(__file__),
        'ipset_state.save'
    )

    NAT_TABLE_SAVE = os.path.join(
        os.path.dirname(__file__),
        'iptables_test_nat_table.save'
    )

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

    @mock.patch('treadmill.iptables.ipset_restore', mock.Mock())
    @mock.patch('treadmill.iptables._iptables_restore', mock.Mock())
    def test_initialize(self):
        """Test iptables initialization"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        treadmill.iptables._iptables_restore.side_effect = [
            None,
            subprocess.CalledProcessError(2, 'failed'),
            None,
        ]

        # NOTE(boysson): keep this IP in sync with the tests' states
        iptables.initialize('1.2.3.4')

        treadmill.iptables.ipset_restore.assert_called_with(
            io.open(self.IPSET_STATE).read(),
        )

        treadmill.iptables._iptables_restore.assert_has_calls([
            mock.call(io.open(self.IPTABLES_STATE).read()),
            mock.call(io.open(self.IPTABLES_FILTER_STATE).read(),
                      noflush=True),
            mock.call(io.open(self.IPTABLES_FILTER_DROP_STATE).read(),
                      noflush=True),
        ])

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
            cmd_input=io.open(self.IPTABLES_EMPTY_STATE).read(),
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

    @mock.patch('treadmill.subproc.check_call', mock.Mock())
    @mock.patch('treadmill.subproc.check_output', mock.Mock())
    def test_add_raw_rule_safe(self):
        """Test adding iptable rule (safe)."""
        treadmill.subproc.check_output.return_value = ''

        iptables.add_raw_rule('nat', 'OUTPUT', '-j FOO', safe=True)

        treadmill.subproc.check_output.assert_called_with(
            ['iptables', '-t', 'nat', '-S', 'OUTPUT']
        )
        treadmill.subproc.check_call.assert_called_with(
            ['iptables', '-t', 'nat', '-A', 'OUTPUT', '-j', 'FOO']
        )
        treadmill.subproc.check_output.reset_mock()
        treadmill.subproc.check_call.reset_mock()
        ##
        treadmill.subproc.check_output.return_value = '-A OUTPUT -j FOO'

        iptables.add_raw_rule('nat', 'OUTPUT', '-j FOO', safe=True)

        treadmill.subproc.check_output.assert_called_with(
            ['iptables', '-t', 'nat', '-S', 'OUTPUT']
        )
        self.assertEqual(0, treadmill.subproc.check_call.call_count)

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
            subprocess.CalledProcessError(returncode=1, output='', cmd='')

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

    @mock.patch('treadmill.iptables.add_ip_set', mock.Mock())
    @mock.patch('treadmill.iptables.test_ip_set',
                mock.Mock(return_value=False))
    def test_add_mark_rule(self):
        """Test mark rule addition"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        # Called with the NONPROD interface
        iptables.add_mark_rule('2.2.2.2', 'dev')

        treadmill.iptables.add_ip_set.assert_called_with(
            iptables.SET_NONPROD_CONTAINERS, '2.2.2.2'
        )
        treadmill.iptables.test_ip_set.assert_called_with(
            iptables.SET_PROD_CONTAINERS, '2.2.2.2'
        )

        treadmill.iptables.add_ip_set.reset_mock()
        treadmill.iptables.test_ip_set.reset_mock()
        # Called with the PROD interface
        iptables.add_mark_rule('3.3.3.3', 'prod')

        treadmill.iptables.add_ip_set.assert_called_with(
            iptables.SET_PROD_CONTAINERS, '3.3.3.3'
        )
        treadmill.iptables.test_ip_set.assert_called_with(
            iptables.SET_NONPROD_CONTAINERS, '3.3.3.3'
        )

    @mock.patch('treadmill.iptables.add_ip_set', mock.Mock())
    @mock.patch('treadmill.iptables.test_ip_set',
                mock.Mock(return_value=True))
    def test_add_mark_rule_dup(self):
        """Test mark rule addition (integrity error)"""
        self.assertRaises(
            Exception,
            iptables.add_mark_rule,
            '2.2.2.2', 'dev'
        )

    @mock.patch('treadmill.iptables.rm_ip_set', mock.Mock())
    def test_delete_mark_rule(self):
        """Test mark rule deletion."""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access

        # Called with the NONPROD interface
        iptables.delete_mark_rule('2.2.2.2', 'dev')

        treadmill.iptables.rm_ip_set.assert_called_with(
            iptables.SET_NONPROD_CONTAINERS, '2.2.2.2'
        )
        treadmill.iptables.rm_ip_set.reset_mock()

        # Called with the PROD interface
        iptables.delete_mark_rule('4.4.4.4', 'prod')

        treadmill.iptables.rm_ip_set.assert_called_with(
            iptables.SET_PROD_CONTAINERS, '4.4.4.4'
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
            io.open(self.NAT_TABLE_SAVE).read()

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
            io.open(self.NAT_TABLE_SAVE).read()

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
                                                dst_ip='192.168.2.2'),
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
    def test_flush_conntrack_table(self):
        """Test flushing on conntrack tules.
        """
        treadmill.subproc.check_call.return_value = 0

        treadmill.iptables.flush_conntrack_table('5.5.5.5')

        treadmill.subproc.check_call.assert_called_with(
            ['conntrack', '-D', '-g', '5.5.5.5']
        )

        treadmill.subproc.check_call.reset_mock()
        treadmill.subproc.check_call.return_value = 1
        treadmill.subproc.check_call.side_effect = \
            subprocess.CalledProcessError(returncode=1, cmd='failed conntrack')

        treadmill.iptables.flush_conntrack_table('4.4.4.4')

        treadmill.subproc.check_call.assert_called_with(
            ['conntrack', '-D', '-g', '4.4.4.4']
        )

    @mock.patch('treadmill.subproc.check_output', mock.Mock())
    def test__get_current_pt_rules(self):
        """Test query passthrough rules."""
        # Disable protected-access: Test access protected members.
        # pylint: disable=protected-access
        treadmill.subproc.check_output.return_value = \
            io.open(self.NAT_TABLE_SAVE).read()

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

    @mock.patch('treadmill.subproc.invoke', mock.Mock(return_value=(0, '')))
    def test_ipset(self):
        """Test ipset tool invocation"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access

        treadmill.subproc.invoke.return_value = (123, "test data")

        res = iptables._ipset('foo', 'bar', cmd_input='test')

        treadmill.subproc.invoke.assert_called_with(
            ['ipset', 'foo', 'bar'],

            cmd_input='test',
            use_except=True
        )
        self.assertEqual(
            res,
            (123, "test data")
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
        iptables._ipset.return_value = (42, "foo")

        res = iptables.test_ip_set('foo', '1.2.3.4')

        treadmill.iptables._ipset.assert_called_with(
            'test', 'foo', '1.2.3.4', use_except=False,
        )
        self.assertFalse(res)
        # Try with success now
        iptables._ipset.reset_mock()
        iptables._ipset.return_value = (0, "bar")

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
    def test_ipset_restore(self):
        """Test the state restore functionality of IPSet"""
        # Disable protected-access: Test access protected members .
        # pylint: disable=protected-access
        iptables.ipset_restore('Initial IPSet state')

        treadmill.iptables._ipset.assert_called_with(
            '-exist', 'restore', cmd_input='Initial IPSet state'
        )


if __name__ == '__main__':
    unittest.main()
