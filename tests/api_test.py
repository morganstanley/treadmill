"""
Unit test for treadmill.api input validation.
"""

import unittest

from treadmill import api


class ApiTest(unittest.TestCase):
    """treadmill.schema tests."""

    def test_normalize(self):
        """Test input validation for app.get."""
        self.assertEquals({'a': 1}, api.normalize({'a': 1}))
        self.assertEquals({'a': 0}, api.normalize({'a': 0}))

        self.assertEquals({}, api.normalize({'a': None}))
        self.assertEquals({}, api.normalize({'a': {}}))
        self.assertEquals({}, api.normalize({'a': []}))
        self.assertEquals({}, api.normalize({'a': False}))

        self.assertEquals({'a': [1]}, api.normalize({'a': [1]}))
        self.assertEquals({'a': [1]}, api.normalize({'a': [1, None]}))
        self.assertEquals({'a': [1]}, api.normalize({'a': [[], 1, {}]}))

        self.assertEquals({'a': {'b': 1}},
                          api.normalize({'a': {'b': 1}}))
        self.assertEquals({'a': {'b': 1}},
                          api.normalize({'a': {'b': 1, 'c': None}}))
        self.assertEquals({'a': [{'b': 1}]},
                          api.normalize({'a': [{'b': 1}]}))
        self.assertEquals({'a': [{'b': 1}]},
                          api.normalize({'a': [{'b': 1, 'c': None}]}))


if __name__ == '__main__':
    unittest.main()
