"""Unit test for treadmill.websocketutils.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill import websocketutils as wsu


def _ret_event(event):
    """Noop, just return the positional args that it was invoked with."""
    return event


# don't compain about protected member access
# pylint: disable=W0212
class WebsocketutilsTest(unittest.TestCase):
    """Mock test for treadmill.websocketutils"""

    @mock.patch('treadmill.trace.app.events.AppTraceEvent.from_dict',
                mock.Mock(side_effect=_ret_event))
    def test_helper_funcs(self):
        """Test the logs() command handler."""
        out = []
        self.assertEqual(wsu._filter_by_uniq({'event': None}, out), True)
        self.assertEqual(out, [])

        event = mock.Mock()
        event.uniqueid = 'uniq_A'
        self.assertEqual(wsu._filter_by_uniq({'event': event}, out, 'uniq_B'),
                         True)
        self.assertEqual(out, [])

        self.assertEqual(wsu._filter_by_uniq({'event': event}, out, 'uniq_A'),
                         True)
        self.assertEqual(out, [event])

    def test_instance_to_host(self):
        """Test that the message processing func returns True no matter what.
        """
        self.assertTrue(wsu._instance_to_host({'foo': 'bar'}))
        self.assertFalse(wsu._instance_to_host(dict(name='foo', host='bar'),
                                               {}))


if __name__ == '__main__':
    unittest.main()
