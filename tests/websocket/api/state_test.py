"""
Unit test for endpoint websocket API.
"""

import unittest

import jsonschema

from treadmill.websocket.api import state


class WSRunningAPITest(unittest.TestCase):
    """Tests for running websocket API."""

    def test_subscribe(self):
        """Test subscription registration."""
        api = state.RunningAPI()
        self.assertEquals(
            [('/running', 'foo.bar#*')],
            api.subscribe({'topic': '/running',
                           'filter': 'foo.bar'})
        )

        self.assertEquals(
            [('/running', '*#*')],
            api.subscribe({'topic': '/running',
                           'filter': '*'})
        )

    def test_on_event(self):
        """Tests payload generation."""
        api = state.RunningAPI()
        self.assertEquals(
            {'host': 'xxx',
             'topic': '/running',
             'name': 'foo.bar#1234'},
            api.on_event(
                '/running/foo.bar#1234',
                None,
                'xxx'
            )
        )

        self.assertEquals(
            {'host': None,
             'topic': '/running',
             'name': 'foo.bar#1234'},
            api.on_event(
                '/running/foo.bar#1234',
                'd',
                None
            )
        )


class WSScheduledAPITest(unittest.TestCase):
    """Tests for scheduled websocket API."""

    def test_subscribe(self):
        """Test subscription registration."""
        api = state.ScheduledAPI()
        self.assertEquals(
            [('/scheduled', 'foo.bar#*')],
            api.subscribe({'topic': '/scheduled',
                           'filter': 'foo.bar'})
        )

        self.assertEquals(
            [('/scheduled', '*#*')],
            api.subscribe({'topic': '/scheduled',
                           'filter': '*'})
        )

        with self.assertRaisesRegexp(
            jsonschema.exceptions.ValidationError,
            "'foo!' does not match"
        ):
            api.subscribe({'topic': '/scheduled',
                           'filter': 'foo!'})


if __name__ == '__main__':
    unittest.main()
