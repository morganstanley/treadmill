"""Unit test for treadmill.cli.logs."""

import importlib
import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import click
import click.testing
import mock

from treadmill import restclient


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

    @mock.patch('treadmill.cli.logs._find_running_instance',
                mock.Mock(return_value={'host': 'host', 'uniq': 'uniq'}))
    @mock.patch('treadmill.cli.logs._find_endpoints',
                mock.Mock(return_value=[{'host': 'host', 'port': 1234}]))
    @mock.patch('treadmill.restclient.get',
                side_effect=restclient.NotFoundError('foobar'))
    def test_no_logfile_found(self, _):
        """Test the output if no log file can be found."""
        result = self.runner.invoke(self.log_cli,
                                    ['--cell', 'foo',
                                     'proid.app#123/running/service/foo'])

        # let's check that NotFoundError is handled
        self.assertEqual(str(result.exception).find('foobar'), -1)


if __name__ == '__main__':
    unittest.main()
