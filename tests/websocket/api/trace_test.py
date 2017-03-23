"""
Unit test for trace websocket API.
"""

import unittest

import mock

from treadmill.apptrace import events
from treadmill.websocket.api import trace


class WSRunningAPITest(unittest.TestCase):
    """Tests for running websocket API."""

    def setUp(self):
        self.api = trace.TraceAPI()

    def test_subscribe(self):
        """Test subscription registration."""
        self.assertEquals(
            self.api.subscribe({'filter': 'foo.bar#1234'}),
            [('/tasks/foo.bar/1234', '*')]
        )

    @mock.patch('treadmill.apptrace.events.AppTraceEvent',
                mock.Mock(set_spec=True))
    def test_on_event(self):
        """Tests payload generation."""
        mock_event = events.AppTraceEvent.from_data.return_value
        self.assertEquals(
            self.api.on_event(
                '/tasks/foo.bar/1234/a,b,c,d',
                None,
                'xxx'
            ),
            {
                'topic': '/trace',
                'event': mock_event.to_dict.return_value
            }
        )
        events.AppTraceEvent.from_data.assert_called_with(
            timestamp='a',
            source='b',
            instanceid='foo.bar#1234',
            event_type='c',
            event_data='d',
            payload='xxx'
        )


if __name__ == '__main__':
    unittest.main()
