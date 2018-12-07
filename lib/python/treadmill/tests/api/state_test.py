"""State API tests.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import json
import zlib

import mock

import treadmill.utils
from treadmill.api import state


def _create_zkclient_mock(placement_data):
    data_watch_mock = mock.Mock(
        side_effect=lambda func: func(placement_data, None, None)
    )
    zkclient_mock = mock.Mock()
    zkclient_mock.DataWatch.return_value = data_watch_mock
    return zkclient_mock


class ApiStateTest(unittest.TestCase):
    """treadmill.api.state tests."""

    def setUp(self):
        self.cell_state = state.CellState()
        self.cell_state.scheduled = set(['foo.bar#0000000001'])
        self.cell_state.running = set(['foo.bar#0000000001'])
        self.cell_state.placement = {
            'foo.bar#0000000001': {
                'expires': 1234567890.1, 'host': 'baz1'
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
        # Disable the exit on exception hack for tests
        self.old_exit_on_unhandled = treadmill.utils.exit_on_unhandled
        treadmill.utils.exit_on_unhandled = mock.Mock(side_effect=lambda x: x)

    def tearDown(self):
        # Restore the exit on exception hack for tests
        treadmill.utils.exit_on_unhandled = self.old_exit_on_unhandled

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
             'name': 'foo.bar#0000000007', 'state': 'aborted',
             'aborted_reason': 'TypeError'}
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
                 'name': 'foo.bar#0000000001', 'expires': 1234567890.1}
            ]
        )
        self.assertEqual(
            state_api.list('foo.bar#000000000[12]', True),
            [
                {'host': 'baz1', 'state': 'running',
                 'name': 'foo.bar#0000000001', 'expires': 1234567890.1},
                {'host': 'baz1', 'name': 'foo.bar#0000000002', 'oom': False,
                 'when': '123456789.2', 'state': 'finished', 'exitcode': 0}
            ]
        )

    @mock.patch('treadmill.context.AdminContext.server')
    @mock.patch('treadmill.context.Context.cell', mock.Mock())
    @mock.patch('treadmill.context.Context.zk', mock.Mock())
    @mock.patch('treadmill.api.state.watch_running', mock.Mock())
    @mock.patch('treadmill.api.state.watch_placement', mock.Mock())
    @mock.patch('treadmill.api.state.watch_finished', mock.Mock())
    @mock.patch('treadmill.api.state.watch_finished_history', mock.Mock())
    @mock.patch('treadmill.api.state.CellState')
    def test_list_partition(self, cell_state_cls_mock, server_factory):
        """Tests for treadmill.api.state.list() with partition"""
        cell_state_cls_mock.return_value = self.cell_state
        admin_srv = server_factory.return_value
        admin_srv.list.return_value = [
            {'cell': 'x', 'traits': [], '_id': 'baz1', 'partition': 'part1'},
            {'cell': 'x', 'traits': [], '_id': 'baz2', 'partition': 'part2'}
        ]

        state_api = state.API()

        self.assertEqual(
            state_api.list('foo.bar#000000000[1234567]', True, 'part1'),
            [
                {'host': 'baz1', 'state': 'running',
                 'name': 'foo.bar#0000000001', 'expires': 1234567890.1},
                {'host': 'baz1', 'name': 'foo.bar#0000000002', 'oom': False,
                 'when': '123456789.2', 'state': 'finished', 'exitcode': 0},
                {'host': 'baz1', 'name': 'foo.bar#0000000003', 'oom': False,
                 'when': '123456789.3', 'state': 'finished', 'exitcode': 255},
                {'host': 'baz1', 'name': 'foo.bar#0000000004', 'oom': False,
                 'signal': 11, 'when': '1234567890.4', 'state': 'finished'}
            ]
        )

    def test_watch_placement(self):
        """Test loading placement.
        """
        cell_state = state.CellState()
        cell_state.running = ['foo.bar#0000000001']
        zkclient_mock = _create_zkclient_mock(
            zlib.compress(
                json.dumps([
                    [
                        'foo.bar#0000000001',
                        'baz', 12345.67890,
                        'baz', 12345.67890
                    ],
                    [
                        'foo.bar#0000000002',
                        'baz', 12345.67890,
                        'baz', 12345.67890
                    ],
                    [
                        'foo.bar#0000000003',
                        None, None,
                        None, None
                    ],
                ]).encode()  # compress needs bytes
            )
        )

        state.watch_placement(zkclient_mock, cell_state)

        self.assertEqual(
            cell_state.placement,
            {
                'foo.bar#0000000001': {
                    'expires': 12345.6789, 'host': 'baz'
                },
                'foo.bar#0000000002': {
                    'expires': 12345.6789, 'host': 'baz'
                },
            }
        )


if __name__ == '__main__':
    unittest.main()
