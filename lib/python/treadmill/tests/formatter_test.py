"""Unit test for treadmill.formatter
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from treadmill import formatter


class FormatterTest(unittest.TestCase):
    """Tests for teadmill.formatter"""

    def test_sanitize(self):
        """Test sanitize.
        """
        self.assertEqual(
            {},
            formatter.sanitize({'x': None})
        )
        self.assertEqual(
            {'y': 1},
            formatter.sanitize({'x': None, 'y': 1})
        )
        self.assertEqual(
            [{'y': 1}],
            formatter.sanitize([{'x': None, 'y': 1}])
        )
        self.assertEqual(1, formatter.sanitize(1))
        self.assertEqual('1', formatter.sanitize('1'))
        self.assertEqual(
            {'x': 1},
            formatter.sanitize({'x': 1, 'vring': {'cell': None, 'rules': []}})
        )

    def test_sanitize_environ(self):
        """Test sanitize.
        """
        environ = {'environ': [
            {'name': '1', 'value': '1'},
            {'name': '2', 'value': None}
        ]}
        self.assertEqual(
            {'environ': [
                {'name': '1', 'value': '1'},
                {'name': '2', 'value': None}
            ]},
            formatter.sanitize(environ)
        )
