"""State API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest

import mock

from treadmill.api import state


class ApiStateTest(unittest.TestCase):
    """treadmill.api.state tests."""

    def setUp(self):
        self.cell_state = state.CellState()
        self.cell_state.placement = {
            'foo.bar#0000000001': {
                'state': 'running', 'expires': 1234567890.1, 'host': 'baz1'
            }
        }
        self.cell_state.finished = {
            'foo.bar#0000000002': {
                'data': '0.0', 'host': 'baz1',
                'when': '123456789.2', 'state': 'finished'
            },
            'foo.bar#0000000003': {
                'data': '255.0', 'host': 'baz1',
                'when': '123456789.3', 'state': 'finished'
            },
            'foo.bar#0000000004': {
                'data': '256.11', 'host': 'baz1',
                'when': '1234567890.4', 'state': 'finished'
            },
            'foo.bar#0000000005': {
                'data': 'oom', 'host': 'baz2',
                'when': '1234567890.5', 'state': 'killed'
            },
            'foo.bar#0000000006': {
                'data': None, 'host': 'baz2',
                'when': 1234567890.6, 'state': 'terminated'
            },
            'foo.bar#0000000007': {
                'data': 'TypeError', 'host': 'baz2',
                'when': '1234567890.7', 'state': 'aborted'
            }
        }

    def tearDown(self):
        pass

    @mock.patch('treadmill.context.GLOBAL', mock.Mock())
    @mock.patch('treadmill.api.state.watch_running', mock.Mock())
    @mock.patch('treadmill.api.state.watch_placement', mock.Mock())
    @mock.patch('treadmill.api.state.watch_finished', mock.Mock())
    @mock.patch('treadmill.api.state.watch_finished_history', mock.Mock())
    @mock.patch('treadmill.api.state.CellState')
    def test_get(self, cell_state_cls_mock):
        """Tests for treadmill.api.state.get()"""
        cell_state_cls_mock.return_value = self.cell_state

        state_api = state.API()

        self.assertEqual(
            state_api.get('foo.bar#0000000001'),
            {'host': 'baz1', 'state': 'running',
             'expires': 1234567890.1, 'name': 'foo.bar#0000000001'}
        )
        self.assertEqual(
            state_api.get('foo.bar#0000000002'),
            {'host': 'baz1', 'name': 'foo.bar#0000000002', 'oom': False,
             'when': '123456789.2', 'state': 'finished', 'exitcode': 0}
        )
        self.assertEqual(
            state_api.get('foo.bar#0000000003'),
            {'host': 'baz1', 'name': 'foo.bar#0000000003', 'oom': False,
             'when': '123456789.3', 'state': 'finished', 'exitcode': 255}
        )
        self.assertEqual(
            state_api.get('foo.bar#0000000004'),
            {'host': 'baz1', 'name': 'foo.bar#0000000004', 'oom': False,
             'signal': 11, 'when': '1234567890.4', 'state': 'finished'}
        )
        self.assertEqual(
            state_api.get('foo.bar#0000000005'),
            {'oom': True, 'host': 'baz2', 'when': '1234567890.5',
             'name': 'foo.bar#0000000005', 'state': 'killed'}
        )
        self.assertEqual(
            state_api.get('foo.bar#0000000006'),
            {'oom': False, 'host': 'baz2', 'when': 1234567890.6,
             'name': 'foo.bar#0000000006', 'state': 'terminated'}
        )
        self.assertEqual(
            state_api.get('foo.bar#0000000007'),
            {'oom': False, 'host': 'baz2', 'when': '1234567890.7',
             'name': 'foo.bar#0000000007', 'state': 'aborted'}
        )

    @mock.patch('treadmill.context.GLOBAL', mock.Mock())
    @mock.patch('treadmill.api.state.watch_running', mock.Mock())
    @mock.patch('treadmill.api.state.watch_placement', mock.Mock())
    @mock.patch('treadmill.api.state.watch_finished', mock.Mock())
    @mock.patch('treadmill.api.state.watch_finished_history', mock.Mock())
    @mock.patch('treadmill.api.state.CellState')
    def test_list(self, cell_state_cls_mock):
        """Tests for treadmill.api.state.list()"""
        cell_state_cls_mock.return_value = self.cell_state

        state_api = state.API()

        self.assertEqual(
            state_api.list(),
            [
                {'host': 'baz1', 'state': 'running',
                 'name': 'foo.bar#0000000001'}
            ]
        )
        self.assertEqual(
            state_api.list('foo.bar#000000000[12]', True),
            [
                {'host': 'baz1', 'state': 'running',
                 'name': 'foo.bar#0000000001'},
                {'host': 'baz1', 'name': 'foo.bar#0000000002', 'oom': False,
                 'when': '123456789.2', 'state': 'finished', 'exitcode': 0}
            ]
        )

    @mock.patch('treadmill.admin.Server.list', mock.Mock(
        return_value=[
            {'cell': 'x', 'traits': [], '_id': 'baz1', 'partition': 'part1'},
            {'cell': 'x', 'traits': [], '_id': 'baz2', 'partition': 'part2'}
        ]
    ))
    @mock.patch('treadmill.context.GLOBAL', mock.Mock())
    @mock.patch('treadmill.api.state.watch_running', mock.Mock())
    @mock.patch('treadmill.api.state.watch_placement', mock.Mock())
    @mock.patch('treadmill.api.state.watch_finished', mock.Mock())
    @mock.patch('treadmill.api.state.watch_finished_history', mock.Mock())
    @mock.patch('treadmill.api.state.CellState')
    def test_list_partition(self, cell_state_cls_mock):
        """Tests for treadmill.api.state.list() with partition"""
        cell_state_cls_mock.return_value = self.cell_state

        state_api = state.API()

        self.assertEqual(
            state_api.list('foo.bar#000000000[1234567]', True, 'part1'),
            [
                {'host': 'baz1', 'state': 'running',
                 'name': 'foo.bar#0000000001'},
                {'host': 'baz1', 'name': 'foo.bar#0000000002', 'oom': False,
                 'when': '123456789.2', 'state': 'finished', 'exitcode': 0},
                {'host': 'baz1', 'name': 'foo.bar#0000000003', 'oom': False,
                 'when': '123456789.3', 'state': 'finished', 'exitcode': 255},
                {'host': 'baz1', 'name': 'foo.bar#0000000004', 'oom': False,
                 'signal': 11, 'when': '1234567890.4', 'state': 'finished'}
            ]
        )


if __name__ == '__main__':
    unittest.main()
