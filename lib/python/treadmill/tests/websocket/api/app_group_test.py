"""Unit test for app_group websocket API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import jsonschema
import six

from treadmill.websocket.api import app_group


class WSAppGroupAPITest(unittest.TestCase):
    """Tests for app group websocket API."""

    def test_subscribe(self):
        """Test subscription registration."""
        api = app_group.AppGroupAPI()
        self.assertEqual(
            [('/app-groups', 'foo.bar')],
            api.subscribe({'topic': '/app-groups',
                           'app-group': 'foo.bar'})
        )

        self.assertEqual(
            [('/app-groups', 'foo.*')],
            api.subscribe({'topic': '/app-groups',
                           'app-group': 'foo.*'})
        )

        self.assertEqual(
            [('/app-groups', '*')],
            api.subscribe({'topic': '/app-groups'})
        )

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   '\'filter\' was unexpected'):
            api.subscribe({'topic': '/app-groups',
                           'filter': 'foo!'})

        with six.assertRaisesRegex(self,
                                   jsonschema.exceptions.ValidationError,
                                   'None is not of type u?\'string\''):
            api.subscribe({'topic': '/app-groups',
                           'app-group': None})

    def test_on_event(self):
        """Tests payload generation."""
        api = app_group.AppGroupAPI()
        self.assertEqual(
            {'topic': '/app-groups',
             'app-group': 'foo.bar',
             'cells': ['mycell'],
             'endpoints': [],
             'group-type': 'event',
             'pattern': 'foo.wsapi',
             'data': {
                 'exit': 'aborted',
                 'pending': '10',
             },
             'sow': True},
            api.on_event(
                '/app-groups/foo.bar',
                None,
                """
                {"cells": ["mycell"], "data": ["exit=aborted", "pending=10"],
                "endpoints": [], "group-type": "event",
                "pattern": "foo.wsapi"}
                """
            )
        )
        self.assertEqual(
            {'topic': '/app-groups',
             'app-group': 'foo.bar',
             'sow': False},
            api.on_event(
                '/app-groups/foo.bar',
                'd',
                None
            )
        )


if __name__ == '__main__':
    unittest.main()
