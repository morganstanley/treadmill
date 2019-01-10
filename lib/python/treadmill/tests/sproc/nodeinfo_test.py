"""Unit test for treadmill.sproc.nodeinfo."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import click

from treadmill.sproc import nodeinfo


class NodeinfoTest(unittest.TestCase):
    """Test treadmill.sproc.nodeinfo."""

    def test_validate_rate_limit(self):
        """Test nodeinfo._validate_rate_limit."""
        # pylint: disable=W0212
        self.assertIsNone(nodeinfo._validate_rate_limit(None, None, None))

        valid_rules = [
            '1/second', '2/minute;3/hour', '4/day,5/month', '6 per second',
            '7 per hour|8/day',
        ]
        for rule in valid_rules:
            actual = nodeinfo._validate_rate_limit(None, None, rule)
            self.assertEqual(rule, actual)

        invalid_rules = [
            '', 'x/second', '/hour', 'per day', 'permonth', '1 second',
            '-2/hour', '3/day;4 hour',
        ]
        for rule in invalid_rules:
            with self.assertRaises(click.BadParameter):
                nodeinfo._validate_rate_limit(None, None, rule)


if __name__ == '__main__':
    unittest.main()
