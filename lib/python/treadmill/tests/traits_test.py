"""Unit test for traits.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

from treadmill import traits


def _transform(code, traitz, use_invalid=False):
    """Encode then decode traitz"""
    return traits.format_traits(code, traits.encode(code, traitz, use_invalid))


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


if __name__ == '__main__':
    unittest.main()
