"""Unit test for Treadmill server trace events module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill.trace.server import events


class ServerTraceEventsTest(unittest.TestCase):
    """Test all event classes operations.
    """

    @mock.patch(('treadmill.trace.server.events'
                 '.ServerStateTraceEvent.from_data'),
                mock.Mock(set_spec=True))
    @mock.patch(('treadmill.trace.server.events'
                 '.ServerBlackoutTraceEvent.from_data'),
                mock.Mock(set_spec=True))
    @mock.patch(('treadmill.trace.server.events'
                 '.ServerBlackoutClearedTraceEvent.from_data'),
                mock.Mock(set_spec=True))
    def test_factory(self):
        """Test class factory operations.
        """
        events.ServerTraceEvent.from_data(
            timestamp=1,
            source='tests',
            servername='test.xx.com',
            event_type='server_state',
            event_data='up',
            payload={'foo': 'bar'}
        )
        events.ServerStateTraceEvent.from_data.assert_called_with(
            timestamp=1,
            source='tests',
            servername='test.xx.com',
            event_type='server_state',
            event_data='up',
            payload={'foo': 'bar'}
        )

        events.ServerTraceEvent.from_data(
            timestamp=2,
            source='tests',
            servername='test.xx.com',
            event_type='server_blackout',
            event_data=None,
            payload={'foo': 'bar'}
        )
        events.ServerBlackoutTraceEvent.from_data.assert_called_with(
            timestamp=2,
            source='tests',
            servername='test.xx.com',
            event_type='server_blackout',
            event_data=None,
            payload={'foo': 'bar'}
        )

        events.ServerTraceEvent.from_data(
            timestamp=3,
            source='tests',
            servername='test.xx.com',
            event_type='server_blackout_cleared',
            event_data=None,
            payload={'foo': 'bar'}
        )
        events.ServerBlackoutClearedTraceEvent.from_data.assert_called_with(
            timestamp=3,
            source='tests',
            servername='test.xx.com',
            event_type='server_blackout_cleared',
            event_data=None,
            payload={'foo': 'bar'}
        )

    def test_factory_bad_event(self):
        """Tests that failure to parse the event returns None.
        """
        res = events.ServerTraceEvent.from_data(
            timestamp=2,
            source='tests',
            servername='test.xx.com',
            event_type='does_not_exists',
            event_data=None,
            payload={'foo': 'bar'}
        )
        self.assertIsNone(res)

    def test_server_state(self):
        """ServerState event operations.
        """
        event = events.ServerStateTraceEvent(
            state='up',
            timestamp=1,
            source='tests',
            servername='test.xx.com',
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'server_state',
                'timestamp': 1,
                'source': 'tests',
                'servername': 'test.xx.com',
                'payload': {'foo': 'bar'},
                'state': 'up',
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                1,
                'tests',
                'test.xx.com',
                'server_state',
                'up',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.ServerStateTraceEvent.from_data(
                timestamp=1,
                source='tests',
                servername='test.xx.com',
                event_type='server_state',
                event_data='up',
                payload={'foo': 'bar'}
            )
        )

    def test_server_blackout(self):
        """ServerBlackout event operations.
        """
        event = events.ServerBlackoutTraceEvent(
            timestamp=2,
            source='tests',
            servername='test.xx.com',
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'server_blackout',
                'timestamp': 2,
                'source': 'tests',
                'servername': 'test.xx.com',
                'payload': {'foo': 'bar'},
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                2,
                'tests',
                'test.xx.com',
                'server_blackout',
                '',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.ServerBlackoutTraceEvent.from_data(
                timestamp=2,
                source='tests',
                servername='test.xx.com',
                event_type='server_blackout',
                event_data='not used',
                payload={'foo': 'bar'}
            )
        )

    def test_server_blackout_cleared(self):
        """ServerBlackoutCleared event operations.
        """
        event = events.ServerBlackoutClearedTraceEvent(
            timestamp=3,
            source='tests',
            servername='test.xx.com',
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'server_blackout_cleared',
                'timestamp': 3,
                'source': 'tests',
                'servername': 'test.xx.com',
                'payload': {'foo': 'bar'},
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                3,
                'tests',
                'test.xx.com',
                'server_blackout_cleared',
                '',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.ServerBlackoutClearedTraceEvent.from_data(
                timestamp=3,
                source='tests',
                servername='test.xx.com',
                event_type='server_blackout_cleared',
                event_data='not used',
                payload={'foo': 'bar'}
            )
        )


if __name__ == '__main__':
    unittest.main()
