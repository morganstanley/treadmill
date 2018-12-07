"""Unit test for server trace websocket API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import jsonschema
import mock

from treadmill.trace.server import events
from treadmill.websocket.api import server_trace


class WSServerTraceAPITest(unittest.TestCase):
    """Tests for server trace websocket API."""

    def setUp(self):
        self.api = server_trace.ServerTraceAPI()

    def test_subscribe(self):
        """Test subscription registration."""
        self.assertEqual(
            self.api.subscribe({'topic': '/server-trace',
                                'filter': 'test.xx.com'}),
            [('/server-trace/*', 'test.xx.com,*')]
        )

        with self.assertRaisesRegex(jsonschema.exceptions.ValidationError,
                                    "None is not of type 'string'"):
            self.api.subscribe({'topic': '/server-trace',
                                'filter': None})

    @mock.patch('treadmill.trace.server.events.ServerTraceEvent',
                mock.Mock(set_spec=True))
    def test_on_event(self):
        """Tests payload generation."""
        mock_event = events.ServerTraceEvent.from_data.return_value
        self.assertEqual(
            self.api.on_event(
                '/server-trace/005D/test.xx.com,100.00,tests,server_blackout,',
                None,
                'xxx'
            ),
            {
                'topic': '/server-trace',
                'event': mock_event.to_dict.return_value
            }
        )
        events.ServerTraceEvent.from_data.assert_called_with(
            timestamp=100.00,
            source='tests',
            servername='test.xx.com',
            event_type='server_blackout',
            event_data='',
            payload='xxx'
        )


if __name__ == '__main__':
    unittest.main()
