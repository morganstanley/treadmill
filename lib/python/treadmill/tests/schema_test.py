"""Unit test for treadmill.schema.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import jsonschema

from treadmill import schema


class SchemaTest(unittest.TestCase):
    """treadmill.schema tests."""

    def test_schema_decorator(self):
        """schema decorator test."""

        @schema.schema({'type': 'number'}, {'type': 'string'})
        def _simple(_number, _string):
            """sample function.
            """

        _simple(1, '1')
        self.assertRaises(
            jsonschema.exceptions.ValidationError,
            _simple, '1', '1')

        @schema.schema({'type': 'number'}, {'type': 'string'},
                       num_arg={'type': 'number'},
                       str_arg={'type': 'string'})
        def _kwargs(_number, _string, num_arg=None, str_arg=None):
            """sample function with default args."""
            return num_arg, str_arg

        self.assertEqual((None, None), _kwargs(1, '1'))
        self.assertEqual((1, None), _kwargs(1, '1', num_arg=1))
        self.assertEqual((None, '1'), _kwargs(1, '1', str_arg='1'))
        self.assertRaises(
            jsonschema.exceptions.ValidationError,
            _kwargs, '1', '1', str_arg=1)


if __name__ == '__main__':
    unittest.main()
