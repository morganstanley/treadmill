"""Unit test for Treadmill app trace events module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill.trace.app import events


class AppTraceEventsTest(unittest.TestCase):
    """Test all event classes operations.
    """

    @mock.patch('treadmill.trace.app.events.AbortedTraceEvent.from_data',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.trace.app.events.ConfiguredTraceEvent.from_data',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.trace.app.events.DeletedTraceEvent.from_data',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.trace.app.events.FinishedTraceEvent.from_data',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.trace.app.events.KilledTraceEvent.from_data',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.trace.app.events.PendingTraceEvent.from_data',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.trace.app.events.PendingDeleteTraceEvent.from_data',
                mock.Mock(set_spec=True))
    @mock.patch('treadmill.trace.app.events.ScheduledTraceEvent.from_data',
                mock.Mock(set_spec=True))
    @mock.patch(('treadmill.trace.app.events'
                 '.ServiceExitedTraceEvent.from_data'),
                mock.Mock(set_spec=True))
    @mock.patch(('treadmill.trace.app.events'
                 '.ServiceRunningTraceEvent.from_data'),
                mock.Mock(set_spec=True))
    def test_factory(self):
        """Test class factory operations.
        """
        events.AppTraceEvent.from_data(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            event_type='scheduled',
            event_data='here',
            payload={'foo': 'bar'}
        )
        events.ScheduledTraceEvent.from_data.assert_called_with(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            event_type='scheduled',
            event_data='here',
            payload={'foo': 'bar'}
        )

        events.AppTraceEvent.from_data(
            timestamp=2,
            source='tests',
            instanceid='proid.foo#123',
            event_type='pending',
            event_data=None,
            payload={'foo': 'bar'}
        )
        events.PendingTraceEvent.from_data.assert_called_with(
            timestamp=2,
            source='tests',
            instanceid='proid.foo#123',
            event_type='pending',
            event_data=None,
            payload={'foo': 'bar'}
        )

    def test_factory_bad_event(self):
        """Tests that failure to parse the event returns None.
        """
        res = events.AppTraceEvent.from_data(
            timestamp=2,
            source='tests',
            instanceid='proid.foo#123',
            event_type='does_not_exists',
            event_data=None,
            payload={'foo': 'bar'}
        )
        self.assertIsNone(res)

        res = events.AppTraceEvent.from_data(
            timestamp=2,
            source='tests',
            instanceid='proid.foo#123',
            event_type='service_running',
            event_data=None,
            payload={'foo': 'bar'}
        )
        self.assertIsNone(res)

    def test_scheduled(self):
        """Scheduled event operations.
        """
        event = events.ScheduledTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            where='here',
            why='because',
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'scheduled',
                'timestamp': 1,
                'source': 'tests',
                'instanceid': 'proid.foo#123',
                'where': 'here',
                'why': 'because',
                'payload': {'foo': 'bar'},
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                1,
                'tests',
                'proid.foo#123',
                'scheduled',
                'here:because',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.ScheduledTraceEvent.from_data(
                timestamp=1,
                source='tests',
                instanceid='proid.foo#123',
                event_type='scheduled',
                event_data='here:because',
                payload={'foo': 'bar'}
            )
        )

    def test_pending(self):
        """Pending event operations.
        """
        event = events.PendingTraceEvent(
            why='created',
            timestamp=2,
            source='tests',
            instanceid='proid.foo#123',
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'pending',
                'timestamp': 2,
                'source': 'tests',
                'instanceid': 'proid.foo#123',
                'payload': {'foo': 'bar'},
                'why': 'created',
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                2,
                'tests',
                'proid.foo#123',
                'pending',
                'created',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.PendingTraceEvent.from_data(
                timestamp=2,
                source='tests',
                instanceid='proid.foo#123',
                event_type='pending',
                event_data='created',
                payload={'foo': 'bar'}
            )
        )

    def test_pending_delete(self):
        """PendingDelete event operations.
        """
        event = events.PendingDeleteTraceEvent(
            why='deleted',
            timestamp=2,
            source='tests',
            instanceid='proid.foo#123',
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'pending_delete',
                'timestamp': 2,
                'source': 'tests',
                'instanceid': 'proid.foo#123',
                'payload': {'foo': 'bar'},
                'why': 'deleted',
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                2,
                'tests',
                'proid.foo#123',
                'pending_delete',
                'deleted',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.PendingDeleteTraceEvent.from_data(
                timestamp=2,
                source='tests',
                instanceid='proid.foo#123',
                event_type='pending_delete',
                event_data='deleted',
                payload={'foo': 'bar'}
            )
        )

    def test_configured(self):
        """Configured event operations.
        """
        event = events.ConfiguredTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            uniqueid='AAAA',
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'configured',
                'timestamp': 1,
                'source': 'tests',
                'instanceid': 'proid.foo#123',
                'uniqueid': 'AAAA',
                'payload': {'foo': 'bar'},
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                1,
                'tests',
                'proid.foo#123',
                'configured',
                'AAAA',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.ConfiguredTraceEvent.from_data(
                timestamp=1,
                source='tests',
                instanceid='proid.foo#123',
                event_type='configured',
                event_data='AAAA',
                payload={'foo': 'bar'}
            )
        )

    def test_deleted(self):
        """Deleted event operations.
        """
        event = events.DeletedTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'deleted',
                'timestamp': 1,
                'source': 'tests',
                'instanceid': 'proid.foo#123',
                'payload': {'foo': 'bar'},
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                1,
                'tests',
                'proid.foo#123',
                'deleted',
                '',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.DeletedTraceEvent.from_data(
                timestamp=1,
                source='tests',
                instanceid='proid.foo#123',
                event_type='deleted',
                event_data='not used',
                payload={'foo': 'bar'}
            )
        )

    def test_finished(self):
        """Finished event operations.
        """
        event = events.FinishedTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            rc=1,
            signal=2,
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'finished',
                'timestamp': 1,
                'source': 'tests',
                'instanceid': 'proid.foo#123',
                'rc': 1,
                'signal': 2,
                'payload': {'foo': 'bar'},
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                1,
                'tests',
                'proid.foo#123',
                'finished',
                '1.2',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.FinishedTraceEvent.from_data(
                timestamp=1,
                source='tests',
                instanceid='proid.foo#123',
                event_type='finished',
                event_data='1.2',
                payload={'foo': 'bar'}
            )
        )

    def test_aborted(self):
        """Aborted event operations.
        """
        event = events.AbortedTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            why='reason',
            payload='test'
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'aborted',
                'timestamp': 1,
                'source': 'tests',
                'instanceid': 'proid.foo#123',
                'why': 'reason',
                'payload': 'test',
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                1,
                'tests',
                'proid.foo#123',
                'aborted',
                'reason',
                'test',
            )
        )
        self.assertEqual(
            event,
            events.AbortedTraceEvent.from_data(
                timestamp=1,
                source='tests',
                instanceid='proid.foo#123',
                event_type='aborted',
                event_data='reason',
                payload='test'
            )
        )

    def test_killed(self):
        """Killed event operations.
        """
        event = events.KilledTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            is_oom=True,
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'killed',
                'timestamp': 1,
                'source': 'tests',
                'instanceid': 'proid.foo#123',
                'is_oom': True,
                'payload': {'foo': 'bar'},
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                1,
                'tests',
                'proid.foo#123',
                'killed',
                'oom',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.KilledTraceEvent.from_data(
                timestamp=1,
                source='tests',
                instanceid='proid.foo#123',
                event_type='killed',
                event_data='oom',
                payload={'foo': 'bar'}
            )
        )

    def test_service_running(self):
        """ServiceRunning event operations.
        """
        event = events.ServiceRunningTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            uniqueid='AAAA',
            service='web.web',
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'service_running',
                'timestamp': 1,
                'source': 'tests',
                'instanceid': 'proid.foo#123',
                'uniqueid': 'AAAA',
                'service': 'web.web',
                'payload': {'foo': 'bar'},
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                1,
                'tests',
                'proid.foo#123',
                'service_running',
                'AAAA.web.web',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.ServiceRunningTraceEvent.from_data(
                timestamp=1,
                source='tests',
                instanceid='proid.foo#123',
                event_type='service_running',
                event_data='AAAA.web.web',
                payload={'foo': 'bar'}
            )
        )

    def test_service_exited(self):
        """ServiceExited event operations.
        """
        event = events.ServiceExitedTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            uniqueid='AAAA',
            service='web.x',
            rc=1,
            signal=2,
            payload={'foo': 'bar'}
        )
        self.assertEqual(
            event.to_dict(),
            {
                'event_type': 'service_exited',
                'timestamp': 1,
                'source': 'tests',
                'instanceid': 'proid.foo#123',
                'uniqueid': 'AAAA',
                'service': 'web.x',
                'rc': 1,
                'signal': 2,
                'payload': {'foo': 'bar'},
            }
        )
        self.assertEqual(
            event.to_data(),
            (
                1,
                'tests',
                'proid.foo#123',
                'service_exited',
                'AAAA.web.x.1.2',
                {'foo': 'bar'},
            )
        )
        self.assertEqual(
            event,
            events.ServiceExitedTraceEvent.from_data(
                timestamp=1,
                source='tests',
                instanceid='proid.foo#123',
                event_type='service_exited',
                event_data='AAAA.web.x.1.2',
                payload={'foo': 'bar'}
            )
        )


if __name__ == '__main__':
    unittest.main()
