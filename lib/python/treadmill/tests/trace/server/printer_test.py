"""Unit test for Treadmill server trace printer module.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import io

import mock

from treadmill.trace.server import events
from treadmill.trace.server import printer


class ServerTracePrinterTest(unittest.TestCase):
    """Test printing trace events.
    """

    def setUp(self):
        self.trace_printer = printer.ServerTracePrinter()

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_server_state(self, stdout_mock):
        """Test printing ServerState event.
        """
        event = events.ServerStateTraceEvent(
            timestamp=1,
            source='tests',
            servername='test.xx.com',
            state='up',
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:01+0000 - '
            'test.xx.com up\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_server_blackout(self, stdout_mock):
        """Test printing ServerBlackout event.
        """
        event = events.ServerBlackoutTraceEvent(
            timestamp=2,
            source='tests',
            servername='test.xx.com',
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:02+0000 - '
            'test.xx.com blackout\n'
        )

    @mock.patch('sys.stdout', new_callable=io.StringIO)
    def test_server_blackout_cleared(self, stdout_mock):
        """Test printing ServerBlackoutCleared event.
        """
        event = events.ServerBlackoutClearedTraceEvent(
            timestamp=3,
            source='tests',
            servername='test.xx.com',
            payload={'foo': 'bar'}
        )

        self.trace_printer.process(event)

        self.assertEqual(
            stdout_mock.getvalue(),
            'Thu, 01 Jan 1970 00:00:03+0000 - '
            'test.xx.com cleared\n'
        )


if __name__ == '__main__':
    unittest.main()
