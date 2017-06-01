"""Unit test for treadmill.dnsutils
"""

import time
import unittest

import mock

from treadmill.sproc import appmonitor


class AppMonitorTest(unittest.TestCase):
    """Test treadmill.sproc.appmonitor"""

    @mock.patch('time.time', mock.Mock())
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
                    'available': 4,
                    'rate': 1.0,
                    'last_update': 100,
                },
                'foo.baz': {
                    'count': 2,
                    'available': 2,
                    'rate': 1.0,
                    'last_update': 100,
                },
            }
        }

        time.time.return_value = 101

        instance_api = mock.MagicMock()
        appmonitor.reevaluate(instance_api, state)
        self.assertFalse(instance_api.create.called)
        self.assertFalse(instance_api.delete.called)

        state['scheduled']['foo.baz'].append('foo.baz#5')
        appmonitor.reevaluate(instance_api, state)
        instance_api.delete.assert_called_with('foo.baz#3')

        self.assertEquals(101, state['monitors']['foo.bar']['last_update'])
        self.assertEquals(101, state['monitors']['foo.baz']['last_update'])

        # Two missing.
        time.time.return_value = 102
        state['scheduled']['foo.bar'] = []
        appmonitor.reevaluate(instance_api, state)
        self.assertEquals(102, state['monitors']['foo.bar']['last_update'])
        self.assertEquals(2.0, state['monitors']['foo.bar']['available'])

        # Instance match count, after 1 sec with rate of 1/s, available will
        # be 3.0
        time.time.return_value = 103
        state['scheduled']['foo.bar'] = ['foo.bar#5', 'foo.bar#6']
        appmonitor.reevaluate(instance_api, state)
        self.assertEquals(103, state['monitors']['foo.bar']['last_update'])
        self.assertEquals(3.0, state['monitors']['foo.bar']['available'])

        # Need to create two instance, 3 available.
        instance_api.create.reset_mock()
        state['scheduled']['foo.bar'] = []

        appmonitor.reevaluate(instance_api, state)
        instance_api.create.assert_called_with('foo.bar', {}, count=2)
        self.assertEquals(1.0, state['monitors']['foo.bar']['available'])

        instance_api.create.reset_mock()
        appmonitor.reevaluate(instance_api, state)
        instance_api.create.assert_called_with('foo.bar', {}, count=1)
        self.assertEquals(0.0, state['monitors']['foo.bar']['available'])

        # No available, create not called.
        instance_api.create.reset_mock()
        appmonitor.reevaluate(instance_api, state)
        self.assertFalse(instance_api.create.called)

        time.time.return_value = 104
        appmonitor.reevaluate(instance_api, state)
        instance_api.create.assert_called_with('foo.bar', {}, count=1)
        self.assertEquals(0.0, state['monitors']['foo.bar']['available'])


if __name__ == '__main__':
    unittest.main()
