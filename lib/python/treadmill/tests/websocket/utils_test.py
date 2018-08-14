"""Unit test for websocket utilities.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from treadmill.websocket import _utils


class UtilsTest(unittest.TestCase):
    """Test websocket utilities.
    """

    def test_parse_message_filter(self):
        """Test parsing message filter.
        """
        parsed_filter = _utils.parse_message_filter('*')
        self.assertEqual(parsed_filter.filter, '*#*')
        self.assertEqual(parsed_filter.appname, '*')
        self.assertEqual(parsed_filter.instanceid, '*')

        parsed_filter = _utils.parse_message_filter('treadmld.cellapi')
        self.assertEqual(parsed_filter.filter, 'treadmld.cellapi#*')
        self.assertEqual(parsed_filter.appname, 'treadmld.cellapi')
        self.assertEqual(parsed_filter.instanceid, '*')

        parsed_filter = _utils.parse_message_filter('treadmld.cellapi#12345')
        self.assertEqual(parsed_filter.filter, 'treadmld.cellapi#12345')
        self.assertEqual(parsed_filter.appname, 'treadmld.cellapi')
        self.assertEqual(parsed_filter.instanceid, '12345')


if __name__ == '__main__':
    unittest.main()
