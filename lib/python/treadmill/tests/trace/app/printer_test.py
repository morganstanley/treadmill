"""Unit test for Treadmill app trace printer module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import io

import mock

from treadmill.trace.app import events
from treadmill.trace.app import printer


class AppTracePrinterTest(unittest.TestCase):
    """Test printing trace events.
    """

    def setUp(self):
        self.trace_printer = printer.AppTracePrinter()

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_scheduled(self, stdout_mock):
        """Test printing Scheduled event.
        """
        event = events.ScheduledTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            where='here',
            why='because',
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:01+0000 - '
            'proid.foo#123 scheduled on here: because\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_pending(self, stdout_mock):
        """Test printing Pending event.
        """
        event = events.PendingTraceEvent(
            why='created',
            timestamp=2,
            source='tests',
            instanceid='proid.foo#123',
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:02+0000 - '
            'proid.foo#123 pending: created\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_pending_delete(self, stdout_mock):
        """Test printing PendingDelete event.
        """
        event = events.PendingDeleteTraceEvent(
            why='deleted',
            timestamp=2,
            source='tests',
            instanceid='proid.foo#123',
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:02+0000 - '
            'proid.foo#123 pending delete: deleted\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_configured(self, stdout_mock):
        """Test printing Configured event.
        """
        event = events.ConfiguredTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            uniqueid='AAAA',
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:01+0000 - '
            'proid.foo#123/AAAA configured on tests\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_deleted(self, stdout_mock):
        """Test printing Deleted event.
        """
        event = events.DeletedTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:01+0000 - '
            'proid.foo#123 deleted\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_finished(self, stdout_mock):
        """Test printing Finished event.
        """
        event = events.FinishedTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            rc=1,
            signal=2,
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:01+0000 - '
            'proid.foo#123 finished on tests\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_aborted(self, stdout_mock):
        """Test printing Aborted event.
        """
        event = events.AbortedTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            why='unknown',
            payload='test'
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:01+0000 - '
            'proid.foo#123 aborted on tests [reason: unknown]\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_killed(self, stdout_mock):
        """Test printing Killed event.
        """
        event = events.KilledTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            is_oom=True,
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:01+0000 - '
            'proid.foo#123 killed, out of memory\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_service_running(self, stdout_mock):
        """Test printing ServiceRunning event.
        """
        event = events.ServiceRunningTraceEvent(
            timestamp=1,
            source='tests',
            instanceid='proid.foo#123',
            uniqueid='AAAA',
            service='web.web',
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:01+0000 - '
            'proid.foo#123/AAAA/service/web.web running\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_service_exited(self, stdout_mock):
        """Test printing ServiceExited event.
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

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:01+0000 - '
            'proid.foo#123/AAAA/service/web.x exited, return code: 1\n'
        )


if __name__ == '__main__':
    unittest.main()
