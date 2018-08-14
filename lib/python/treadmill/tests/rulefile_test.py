"""Unit test for rulefile - rule manager.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import io
import os
import shutil
import tempfile
import unittest

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import firewall
from treadmill import rulefile


class RulefileTest(unittest.TestCase):
    """Tests for teadmill.rulefile."""

    def setUp(self):
        # Pylint warning re accessing protected class member.
        # pylint: disable=W0212

        self.root = tempfile.mkdtemp()
        self.rules_dir = os.path.join(self.root, 'rules')
        self.apps_dir = os.path.join(self.root, 'apps')
        os.makedirs(self.rules_dir)
        os.makedirs(self.apps_dir)
        self.rules = rulefile.RuleMgr(self.rules_dir, self.apps_dir)

        self.tcpdnatrule = firewall.DNATRule(
            proto='tcp',
            dst_ip='1.1.1.1', dst_port=123,
            new_ip='2.2.2.2', new_port=234
        )
        self.tcpdnatfile = rulefile.RuleMgr._filenameify(
            'SOME_CHAIN',
            self.tcpdnatrule
        )
        self.tcpdnatuid = '1234'
        with io.open(os.path.join(self.apps_dir, self.tcpdnatuid), 'w'):
            pass

        self.udpdnatrule = firewall.DNATRule(
            proto='udp',
            dst_ip='1.1.1.1', dst_port=123,
            new_ip='2.2.2.2', new_port=234
        )
        self.udpdnatfile = rulefile.RuleMgr._filenameify(
            'SOME_CHAIN',
            self.udpdnatrule
        )
        self.udpdnatuid = '2345'
        with io.open(os.path.join(self.apps_dir, self.udpdnatuid), 'w'):
            pass

        self.udpsnatrule = firewall.SNATRule(
            proto='udp',
            src_ip='1.1.1.1', src_port=123,
            new_ip='2.2.2.2', new_port=234
        )
        self.udpsnatfile = rulefile.RuleMgr._filenameify(
            'SOME_CHAIN',
            self.udpsnatrule
        )
        self.udpsnatuid = '3456'
        with io.open(os.path.join(self.apps_dir, self.udpsnatuid), 'w'):
            pass

        self.passthroughrule = firewall.PassThroughRule('3.3.3.3', '4.4.4.4')
        self.passthroughfile = rulefile.RuleMgr._filenameify(
            'SOME_CHAIN',
            self.passthroughrule,
        )
        self.passthroughuid = '4321'
        with io.open(os.path.join(self.apps_dir, self.passthroughuid), 'w'):
            pass

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test__filenameify(self):
        """Test the output of _filenameify is as expected.
        """
        # Pylint warning re accessing protected class member.
        # pylint: disable=W0212

        self.assertEqual(
            rulefile.RuleMgr._filenameify(
                'SOME_CHAIN', self.tcpdnatrule
            ),
            'SOME_CHAIN:dnat:tcp:*:*:1.1.1.1:123-2.2.2.2:234'
        )
        self.assertEqual(
            rulefile.RuleMgr._filenameify(
                'SOME_CHAIN', self.udpdnatrule
            ),
            'SOME_CHAIN:dnat:udp:*:*:1.1.1.1:123-2.2.2.2:234'
        )
        self.assertEqual(
            rulefile.RuleMgr._filenameify(
                'SOME_CHAIN', self.udpsnatrule
            ),
            'SOME_CHAIN:snat:udp:1.1.1.1:123:*:*-2.2.2.2:234'
        )
        self.assertEqual(
            rulefile.RuleMgr._filenameify(
                'SOME_CHAIN', self.passthroughrule
            ),
            'SOME_CHAIN:passthrough:3.3.3.3-4.4.4.4'
        )

    def test_get_rule(self):
        """Test parsing a given rule specs.
        """
        self.assertEqual(
            self.rules.get_rule(
                'TEST_CHAIN:dnat:tcp:*:*:1.1.1.1:123-2.2.2.2:234'
            ),
            ('TEST_CHAIN', self.tcpdnatrule),
        )
        self.assertEqual(
            self.rules.get_rule(
                'TEST_CHAIN:dnat:udp:*:*:1.1.1.1:123-2.2.2.2:234'
            ),
            ('TEST_CHAIN', self.udpdnatrule),
        )
        self.assertEqual(
            self.rules.get_rule(
                'TEST_CHAIN:snat:udp:1.1.1.1:123:*:*-2.2.2.2:234'
            ),
            ('TEST_CHAIN', self.udpsnatrule),
        )
        self.assertEqual(
            self.rules.get_rule('TEST_CHAIN:passthrough:3.3.3.3-4.4.4.4'),
            ('TEST_CHAIN', self.passthroughrule),
        )
        self.assertEqual(
            self.rules.get_rule('not_a_rule'),
            None,
        )

    def test_create_rule(self):
        """Test rule creation.
        """
        self.rules.create_rule('SOME_CHAIN', self.tcpdnatrule, self.tcpdnatuid)
        self.assertTrue(
            os.path.exists(
                os.path.join(self.rules_dir, self.tcpdnatfile)
            )
        )
        # Ensure the rule link points to its owner app
        self.assertEqual(
            os.path.realpath(
                os.path.join(
                    self.rules_dir,
                    os.readlink(
                        os.path.join(self.rules_dir, self.tcpdnatfile)
                    )
                )
            ),
            os.path.join(self.apps_dir, self.tcpdnatuid)
        )

        # Create rule is idempotent.
        self.rules.create_rule('SOME_CHAIN', self.tcpdnatrule, self.tcpdnatuid)
        self.assertTrue(
            os.path.exists(
                os.path.join(self.rules_dir, self.tcpdnatfile)
            )
        )
        self.assertEqual(
            os.path.realpath(
                os.path.join(
                    self.rules_dir,
                    os.readlink(
                        os.path.join(self.rules_dir, self.tcpdnatfile)
                    )
                )
            ),
            os.path.join(self.apps_dir, self.tcpdnatuid)
        )

    def test_create_rule_conflict(self):
        """Test rule creation conflict handling.
        """
        self.rules.create_rule('SOME_CHAIN', self.tcpdnatrule, self.tcpdnatuid)

        self.assertRaises(
            OSError,
            self.rules.create_rule,
            'SOME_CHAIN', self.tcpdnatrule, self.passthroughuid
        )

    def test_gc_rules(self):
        """Test auto-cleanup of rules without owner.
        """
        self.rules.create_rule('SOME_CHAIN', self.tcpdnatrule, self.tcpdnatuid)
        self.rules.create_rule('SOME_CHAIN', self.passthroughrule, 'not_here')

        self.rules.garbage_collect()
        self.assertTrue(
            os.path.islink(
                os.path.join(self.rules_dir, self.tcpdnatfile)
            )
        )
        self.assertFalse(
            os.path.islink(
                os.path.join(self.rules_dir, self.passthroughfile)
            )
        )

    def test_unlink_rule(self):
        """Test rule cleanup.
        """
        self.rules.create_rule('SOME_CHAIN', self.tcpdnatrule, self.tcpdnatuid)

        self.rules.unlink_rule('SOME_CHAIN', self.tcpdnatrule, self.tcpdnatuid)
        self.assertFalse(
            os.path.exists(
                os.path.join(self.rules_dir, self.tcpdnatfile)
            )
        )

        # Check invoking unlink on non-existing rule is not an error.
        self.rules.unlink_rule('SOME_CHAIN', self.tcpdnatrule, self.tcpdnatuid)

    def test_unlink_rule_not_owner(self):
        """Test rule cleanup fails when not rule's owner.
        """
        self.rules.create_rule('SOME_CHAIN', self.tcpdnatrule, self.tcpdnatuid)

        self.rules.unlink_rule('SOME_CHAIN', self.tcpdnatrule,
                               self.passthroughuid)
        self.assertTrue(
            os.path.exists(
                os.path.join(self.rules_dir, self.tcpdnatfile)
            )
        )

    def test_get_rules(self):
        """Test get rules for list of files.
        """
        for filename in [self.tcpdnatfile,
                         self.udpsnatfile,
                         self.passthroughfile,
                         'not_a_rule']:
            with io.open(os.path.join(self.rules_dir, filename), 'w'):
                pass

        rules = self.rules.get_rules()
        self.assertIn(('SOME_CHAIN', self.tcpdnatrule), rules)
        self.assertIn(('SOME_CHAIN', self.udpsnatrule), rules)
        self.assertEqual(3, len(rules))


if __name__ == '__main__':
    unittest.main()
