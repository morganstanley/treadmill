"""
Unit test for endpoint websocket API.
"""

import unittest

from treadmill.websocket.api import endpoint


class WSEndpointAPITest(unittest.TestCase):
    """Tests for endpoint websocket API."""

    def test_subscribe(self):
        """Test subscription registration."""
        api = endpoint.EndpointAPI()
        self.assertEquals(
            [('/endpoints/foo', 'bar#*:tcp:http')],
            api.subscribe({'filter': 'foo.bar',
                           'proto': 'tcp',
                           'endpoint': 'http'})
        )

        self.assertEquals(
            [('/endpoints/foo', '*#*:*:*')],
            api.subscribe({'filter': 'foo.*',
                           'proto': '*',
                           'endpoint': '*'})
        )

        self.assertEquals(
            [('/endpoints/foo', '*#*:*:*')],
            api.subscribe({'filter': 'foo.*',
                           'proto': None,
                           'endpoint': None})
        )

    def test_on_event(self):
        """Tests payload generation."""
        api = endpoint.EndpointAPI()
        self.assertEquals(
            {'endpoint': 'http',
             'name': 'foo.bar#1234',
             'proto': 'tcp',
             'topic': '/endpoints',
             'host': 'xxx',
             'sow': True,
             'port': '1234'},
            api.on_event(
                '/endpoints/foo/bar#1234:tcp:http',
                None,
                'xxx:1234'
            )
        )

        self.assertEquals(
            {'endpoint': 'http',
             'name': 'foo.bar#1234',
             'proto': 'tcp',
             'topic': '/endpoints',
             'host': 'xxx',
             'sow': False,
             'port': '1234'},
            api.on_event(
                '/endpoints/foo/bar#1234:tcp:http',
                'm',
                'xxx:1234'
            )
        )

        self.assertEquals(
            {'endpoint': 'http',
             'name': 'foo.bar#1234',
             'proto': 'tcp',
             'topic': '/endpoints',
             'host': None,
             'sow': False,
             'port': None},
            api.on_event(
                '/endpoints/foo/bar#1234:tcp:http',
                'd',
                None
            )
        )

        # IGnore create event.
        self.assertIsNone(
            api.on_event(
                '/endpoints/foo/bar#1234:tcp:http',
                'c',
                'xxx:1234'
            )
        )


if __name__ == '__main__':
    unittest.main()
