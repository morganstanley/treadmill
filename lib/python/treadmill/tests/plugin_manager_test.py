"""Unit test for plugin manager.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import collections
import unittest

import mock
import pkg_resources

from treadmill import plugin_manager

# pylint: disable=protected-access


_EntryPoint = collections.namedtuple('EntryPoint', ['name'])


class PluginManagerTest(unittest.TestCase):
    """Tests plugin manager."""

    def setUp(self):
        self.saved = plugin_manager._FILTER

    def tearDown(self):
        plugin_manager._FILTER = self.saved

    @mock.patch('pkg_resources.iter_entry_points', mock.Mock())
    def test_whitelist(self):
        """Tests plugin manager whitelist."""
        pkg_resources.iter_entry_points.return_value = [
            _EntryPoint(x) for x in [
                'aaa',
                'bbb',
                'aaa.foo'
            ]
        ]

        # No whitelist - load all.
        plugin_manager._FILTER = {}
        self.assertEqual(
            set(['aaa', 'bbb', 'aaa.foo']),
            set(plugin_manager.names('foo.bar'))
        )

        plugin_manager._FILTER = {
            'x': ['aaa*']
        }
        # Section in the whitelist, will be filtered.
        self.assertEqual(
            set(['aaa', 'aaa.foo']),
            set(plugin_manager.names('x'))
        )
        # Section not in the whitelist, will load all.
        self.assertEqual(
            set(['aaa', 'bbb', 'aaa.foo']),
            set(plugin_manager.names('y'))
        )

    def test_load(self):
        """Test parsing filter string."""
        self.assertEqual(
            {
                'x': ['aaa'],
                'y': ['bbb'],
            },
            plugin_manager._load_filter('x=aaa:y=bbb')
        )
        self.assertEqual(
            {
                'x': ['aaa', 'ccc'],
                'y': ['bbb'],
            },
            plugin_manager._load_filter('x=aaa,ccc:y=bbb')
        )


if __name__ == '__main__':
    unittest.main()
