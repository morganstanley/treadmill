"""
Unit test for endpoint websocket API.
"""

import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

from treadmill.websocket.api import state


class WSRunningAPITest(unittest.TestCase):
    """Tests for running websocket API."""

    def test_subscribe(self):
        """Test subscription registration."""
        api = state.RunningAPI()
        self.assertEquals(
            [('/running', 'foo.bar#*')],
            api.subscribe({'filter': 'foo.bar'})
        )

        self.assertEquals(
            [('/running', '*#*')],
            api.subscribe({'filter': '*'})
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


if __name__ == '__main__':
    unittest.main()
