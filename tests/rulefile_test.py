"""Unit test for rulefile - rule manager.
"""

import os
import shutil
import tempfile
import unittest

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

        self.tcpnatrule = firewall.DNATRule(
            'tcp',
            '1.1.1.1', 123, '2.2.2.2', 234
        )
        self.tcpnatfile = rulefile.RuleMgr._filenameify(self.tcpnatrule)
        self.tcpnatuid = '1234'
        with open(os.path.join(self.apps_dir, self.tcpnatuid), 'w'):
            pass

        self.udpnatrule = firewall.DNATRule(
            'udp',
            '1.1.1.1', 123, '2.2.2.2', 234
        )
        self.udpnatfile = rulefile.RuleMgr._filenameify(self.udpnatrule)
        self.udpnatuid = '2345'
        with open(os.path.join(self.apps_dir, self.udpnatuid), 'w'):
            pass

        self.passthroughrule = firewall.PassThroughRule('3.3.3.3', '4.4.4.4')
        self.passthroughfile = rulefile.RuleMgr._filenameify(
            self.passthroughrule,
        )
        self.passthroughuid = '4321'
        with open(os.path.join(self.apps_dir, self.passthroughuid), 'w'):
            pass

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def test_filename(self):
        """Test the output of _filenameify is as expected.
        """
        # Pylint warning re accessing protected class member.
        # pylint: disable=W0212

        self.assertEqual(
            rulefile.RuleMgr._filenameify(self.tcpnatrule),
            "dnat:tcp:1.1.1.1:123-2.2.2.2:234"
        )
        self.assertEqual(
            rulefile.RuleMgr._filenameify(self.udpnatrule),
            "dnat:udp:1.1.1.1:123-2.2.2.2:234"
        )
        self.assertEqual(
            rulefile.RuleMgr._filenameify(self.passthroughrule),
            "passthrough:3.3.3.3-4.4.4.4"
        )

    def test_get_rule(self):
        """Test parsing a given rule specs.
        """
        self.assertEqual(
            self.rules.get_rule("dnat:tcp:1.1.1.1:123-2.2.2.2:234"),
            self.tcpnatrule,
        )
        self.assertEqual(
            self.rules.get_rule("dnat:udp:1.1.1.1:123-2.2.2.2:234"),
            self.udpnatrule,
        )
        self.assertEqual(
            self.rules.get_rule("passthrough:3.3.3.3-4.4.4.4"),
            self.passthroughrule,
        )
        self.assertEqual(
            self.rules.get_rule('not_a_rule'),
            None,
        )

    def test_unlink_rule(self):
        """Test rule cleanup.
        """
        self.rules.create_rule(self.tcpnatrule, self.tcpnatuid)

        self.rules.unlink_rule(self.tcpnatrule, self.tcpnatuid)
        self.assertFalse(
            os.path.exists(
                os.path.join(self.rules_dir, self.tcpnatfile)
            )
        )

        # Check invoking unlink on non-existing rule is not an error.
        self.rules.unlink_rule(self.tcpnatrule, self.tcpnatuid)

    def test_unlink_rule_not_owner(self):
        """Test rule cleanup fails when not rule's owner.
        """
        self.rules.create_rule(self.tcpnatrule, self.tcpnatuid)

        self.rules.unlink_rule(self.tcpnatrule, self.passthroughuid)
        self.assertTrue(
            os.path.exists(
                os.path.join(self.rules_dir, self.tcpnatfile)
            )
        )

    def test_create_rule(self):
        """Test rule creation.
        """
        self.rules.create_rule(self.tcpnatrule, self.tcpnatuid)
        self.assertTrue(
            os.path.exists(
                os.path.join(self.rules_dir, self.tcpnatfile)
            )
        )
        # Ensure the rule link points to its owner app
        self.assertEqual(
            os.path.realpath(
                os.path.join(
                    self.rules_dir,
                    os.readlink(
                        os.path.join(self.rules_dir, self.tcpnatfile)
                    )
                )
            ),
            os.path.join(self.apps_dir, self.tcpnatuid)
        )

        # Create rule is idempotent.
        self.rules.create_rule(self.tcpnatrule, self.tcpnatuid)
        self.assertTrue(
            os.path.exists(
                os.path.join(self.rules_dir, self.tcpnatfile)
            )
        )
        self.assertEqual(
            os.path.realpath(
                os.path.join(
                    self.rules_dir,
                    os.readlink(
                        os.path.join(self.rules_dir, self.tcpnatfile)
                    )
                )
            ),
            os.path.join(self.apps_dir, self.tcpnatuid)
        )

    def test_create_rule_conflict(self):
        """Test rule creation conflict handling.
        """
        self.rules.create_rule(self.tcpnatrule, self.tcpnatuid)

        self.assertRaises(
            OSError,
            self.rules.create_rule,
            self.tcpnatrule, self.passthroughuid
        )

    def test_gc_rules(self):
        """Test auto-cleanup of rules without owner.
        """
        self.rules.create_rule(self.tcpnatrule, self.tcpnatuid)
        self.rules.create_rule(self.passthroughrule, 'does_not_exists')

        self.rules.garbage_collect()
        self.assertTrue(
            os.path.islink(
                os.path.join(self.rules_dir, self.tcpnatfile)
            )
        )
        self.assertFalse(
            os.path.islink(
                os.path.join(self.rules_dir, self.passthroughfile)
            )
        )

    def test_get_rules(self):
        """Test get rules for list of files.
        """
        for filename in [self.tcpnatfile, self.passthroughfile, 'not_a_rule']:
            with open(os.path.join(self.rules_dir, filename), 'w+'):
                pass

        rules = self.rules.get_rules()
        self.assertIn(self.tcpnatrule, rules)
        self.assertIn(self.passthroughrule, rules)
        self.assertEqual(2, len(rules))


if __name__ == '__main__':
    unittest.main()
