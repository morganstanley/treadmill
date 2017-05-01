"""Unit test for treadmill.dnsutils
"""

import unittest

# Disable W0611: Unused import
import tests.treadmill_test_deps  # pylint: disable=W0611

import mock

from treadmill.sproc import appmonitor


class AppMonitorTest(unittest.TestCase):
    """Test treadmill.sproc.appmonitor"""

    def test_reevaluate(self):
        """Test state reevaluation."""

        state = {
            'scheduled': {
                'foo.bar': ['foo.bar#1', 'foo.bar.#2'],
                'foo.baz': ['foo.baz#3', 'foo.baz.#4'],
            },
            'monitors': {
                'foo.bar': {
                    'count': 2,
                    'next_tick': 0,
                },
                'foo.baz': {
                    'count': 2,
                    'next_tick': 0,
                },
            }
        }

        instance_api = mock.MagicMock()
        appmonitor.reevaluate(instance_api, state)
        self.assertFalse(instance_api.create.called)
        self.assertFalse(instance_api.delete.called)

        state['monitors']['foo.bar'] = {
            'count': 3,
            'next_tick': 0
        }
        appmonitor.reevaluate(instance_api, state)
        instance_api.create.assert_called_with('foo.bar', {}, count=1)

        state['scheduled']['foo.baz'].append('foo.baz#5')
        appmonitor.reevaluate(instance_api, state)
        instance_api.delete.assert_called_with('foo.baz#3')


if __name__ == '__main__':
    unittest.main()
