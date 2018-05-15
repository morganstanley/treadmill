"""Unit test for traits.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from treadmill import traits


def _transform(code, traitz):
    """Encode then decode traitz"""
    return traits.format_traits(code, traits.encode(code, traitz))


class TraitsTest(unittest.TestCase):
    """treadmill.traits test."""

    def test_traits(self):
        """Basic traits test."""
        traitz = ['a', 'b']
        code = traits.create_code(traitz)

        self.assertEqual(
            _transform(code, ['a']),
            'a'
        )
        self.assertEqual(
            _transform(code, ['a', 'b']),
            'a,b'
        )
        self.assertEqual(
            _transform(code, ['b', 'a']),
            'a,b'
        )
        self.assertEqual(
            _transform(code, ['a', 'x', 'b']),
            'a,b'
        )
        self.assertEqual(
            _transform({}, ['a', 'x', 'b']),
            ''
        )


if __name__ == '__main__':
    unittest.main()
