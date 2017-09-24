"""Unit test for trace websocket API.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock
import jsonschema

from treadmill.apptrace import events
from treadmill.websocket.api import trace


class WSRunningAPITest(unittest.TestCase):
    """Tests for running websocket API."""

    def setUp(self):
        self.api = trace.TraceAPI()

    def test_subscribe(self):
        """Test subscription registration."""
        self.assertEqual(
            self.api.subscribe({'topic': '/trace',
                                'filter': 'foo.bar#1234'}),
            [('/trace/*', 'foo.bar#1234,*')]
        )

        self.assertEqual(
            self.api.subscribe({'topic': '/trace',
                                'filter': 'foo.bar'}),
            [('/trace/*', 'foo.bar#*,*')]
        )

        self.assertEqual(
            self.api.subscribe({'topic': '/trace',
                                'filter': 'foo.bar*'}),
            [('/trace/*', 'foo.bar*#*,*')]
        )

        self.assertEqual(
            self.api.subscribe({'topic': '/trace',
                                'filter': 'foo.*'}),
            [('/trace/*', 'foo.*#*,*')]
        )

        with self.assertRaisesRegexp(  # pylint: disable=deprecated-method
            jsonschema.exceptions.ValidationError,
            "'*' does not match"
        ):
            self.api.subscribe({'topic': '/trace',
                                'filter': '*'})

    @mock.patch('treadmill.apptrace.events.AppTraceEvent',
                mock.Mock(set_spec=True))
    def test_on_event(self):
        """Tests payload generation."""
        mock_event = events.AppTraceEvent.from_data.return_value
        self.assertEqual(
            self.api.on_event(
                '/trace/00C2/foo.bar#1234,123.04,b,c,d',
                None,
                'xxx'
            ),
            {
                'topic': '/trace',
                'event': mock_event.to_dict.return_value
            }
        )
        events.AppTraceEvent.from_data.assert_called_with(
            timestamp=123.04,
            source='b',
            instanceid='foo.bar#1234',
            event_type='c',
            event_data='d',
            payload='xxx'
        )


if __name__ == '__main__':
    unittest.main()
