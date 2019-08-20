"""Unit test for traits.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from treadmill import traits


def _transform(codes, trait_list, use_invalid=False, add_new=False):
    """Encode then decode traitz"""
    result, new_codes = traits.encode(codes, trait_list, use_invalid, add_new)
    return traits.format_traits(new_codes, result)


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
            _transform(code, ['a', 'x', 'b'], use_invalid=True),
            'a,b,invalid'
        )
        self.assertEqual(
            _transform(traits.create_code([]), ['a', 'x', 'b']),
            ''
        )
        self.assertEqual(
            _transform(
                traits.create_code([]),
                ['a', 'x', 'b'],
                use_invalid=True
            ),
            'invalid'
        )

    def test_adding_traits(self):
        """Adding traits test."""
        code = traits.create_code([])

        self.assertEqual(
            _transform(code, ['a']),
            ''
        )

        self.assertEqual(
            _transform(code, ['a'], add_new=True),
            'a'
        )


if __name__ == '__main__':
    unittest.main()
