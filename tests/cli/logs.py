"""Unit test for treadmill.cli.logs.
"""

import importlib
import unittest

import click
import click.testing
import mock


def _ret_event(event):
    """Noop, just return the positional args that it was invoked with."""
    return event


# don't compain about protected member access
# pylint: disable=W0212
class LogsTest(unittest.TestCase):
    """Mock test for treadmill.cli.logs"""

    def setUp(self):
        """Setup common test variables"""
        self.runner = click.testing.CliRunner()
        self.log_mod = importlib.import_module('treadmill.cli.logs')
        self.log_cli = self.log_mod.init()

    @mock.patch('treadmill.apptrace.events.AppTraceEvent.from_dict',
                mock.Mock(side_effect=_ret_event))
    def test_helper_funcs(self):
        """Test the logs() command handler."""
        out = []
        self.assertEqual(
            self.log_mod._filter_by_uniq(
                {'event': None}, out), True)
        self.assertEqual(out, [])

        event = mock.Mock()
        event.uniqueid = 'uniq_A'
        self.assertEqual(
            self.log_mod._filter_by_uniq(
                {'event': event}, out, 'uniq_B'), True)
        self.assertEqual(out, [])

        self.assertEqual(
            self.log_mod._filter_by_uniq(
                {'event': event}, out, 'uniq_A'), True)
        self.assertEqual(out, [event])


if __name__ == '__main__':
    unittest.main()
