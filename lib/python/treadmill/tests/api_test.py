"""Unit test for treadmill.api input validation.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from treadmill import api


class ApiTest(unittest.TestCase):
    """treadmill.schema tests."""

    def test_normalize(self):
        """Test input validation for app.get."""
        self.assertEqual({'a': 1}, api.normalize({'a': 1}))
        self.assertEqual({'a': 0}, api.normalize({'a': 0}))

        self.assertEqual({}, api.normalize({'a': None}))
        self.assertEqual({}, api.normalize({'a': {}}))
        self.assertEqual({}, api.normalize({'a': []}))
        self.assertEqual({}, api.normalize({'a': False}))

        self.assertEqual({'a': [1]}, api.normalize({'a': [1]}))
        self.assertEqual({'a': [1]}, api.normalize({'a': [1, None]}))
        self.assertEqual({'a': [1]}, api.normalize({'a': [[], 1, {}]}))

        self.assertEqual(
            {'a': {'b': 1}},
            api.normalize({'a': {'b': 1}})
        )
        self.assertEqual(
            {'a': {'b': 1}},
            api.normalize({'a': {'b': 1, 'c': None}})
        )
        self.assertEqual(
            {'a': [{'b': 1}]},
            api.normalize({'a': [{'b': 1}]})
        )
        self.assertEqual(
            {'a': [{'b': 1}]},
            api.normalize({'a': [{'b': 1, 'c': None}]})
        )


if __name__ == '__main__':
    unittest.main()
