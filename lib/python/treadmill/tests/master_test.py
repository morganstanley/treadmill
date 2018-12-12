"""Unit test for treadmill master.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import json
import os
import shutil
import tempfile
import time
import unittest
import zlib

import kazoo
import mock
import numpy as np

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

import treadmill
import treadmill.exc
from treadmill import scheduler
from treadmill.scheduler import loader
from treadmill.scheduler import master
from treadmill.scheduler import masterapi
from treadmill.scheduler import zkbackend

from treadmill.tests.testutils import mockzk

# Disable C0302: Too many lines in the module
# pylint: disable=C0302


class MasterTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.master."""

    def setUp(self):
        super(MasterTest, self).setUp()

        scheduler.DIMENSION_COUNT = 3

        self.events_dir = tempfile.mkdtemp()
        self.app_events_dir = tempfile.mkdtemp(dir=self.events_dir)
        self.server_events_dir = tempfile.mkdtemp(dir=self.events_dir)

        backend = zkbackend.ZkBackend(treadmill.zkutils.ZkClient())
        self.master = master.Master(
            backend,
            'test-cell',
            self.app_events_dir,
            self.server_events_dir
        )
        # Use 111 to assert on zkhandle value.
        # Disable the exit on exception hack for tests
        self.old_exit_on_unhandled = treadmill.utils.exit_on_unhandled
        treadmill.utils.exit_on_unhandled = mock.Mock(side_effect=lambda x: x)

    def tearDown(self):
        if self.events_dir and os.path.isdir(self.events_dir):
            shutil.rmtree(self.events_dir)
        # Restore the exit on exception hack for tests
        treadmill.utils.exit_on_unhandled = self.old_exit_on_unhandled
        super(MasterTest, self).tearDown()

    def test_resource_parsing(self):
        """Tests parsing resources."""
        self.assertEqual([0, 0, 0], loader.resources({}))
        self.assertEqual([1, 0, 0], loader.resources({'memory': '1M'}))
        self.assertEqual(
            [1, 10, 1024],
            loader.resources(
                {'memory': '1M',
                 'cpu': '10%',
                 'disk': '1G'}
            )
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_load_servers(self):
        """Tests load of server and bucket data."""
        zk_content = {
            'placement': {},
            'server.presence': {},
            'cell': {
                'pod:pod1': {},
                'pod:pod2': {},
            },
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'pod:pod2': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
                'rack:2345': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
            'servers': {
                'test.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
            },
        }
        self.make_mock_zk(zk_content)
        self.master.load_buckets()
        self.master.load_cell()

        self.assertIn(
            'pod:pod1',
            self.master.cell.children_by_name
        )
        self.assertIn(
            'rack:1234',
            self.master.cell.children_by_name['pod:pod1'].children_by_name
        )

        self.master.load_servers()
        rack_1234 = self.master.cell \
            .children_by_name['pod:pod1'].children_by_name['rack:1234']
        self.assertIn('test.xx.com', rack_1234.children_by_name)
        self.assertIn('test.xx.com', self.master.servers)

        # Check capacity - (memory, cpu, disk) vector.
        self.assertTrue(
            np.all(np.isclose(
                [16. * 1024, 400, 128. * 1024],
                rack_1234.children_by_name['test.xx.com'].init_capacity)))

        # Server has presence -> valid_until should be set when (re)loading it.
        zk_content['server.presence']['test.xx.com'] = {}

        # Modify server parent, make sure it is reloaded.
        zk_content['servers']['test.xx.com']['parent'] = 'rack:2345'
        self.master.reload_servers(['test.xx.com'])

        rack_2345 = self.master.cell \
            .children_by_name['pod:pod1'].children_by_name['rack:2345']
        self.assertNotIn('test.xx.com', rack_1234.children_by_name)
        self.assertIn('test.xx.com', rack_2345.children_by_name)
        self.assertTrue(self.master.servers['test.xx.com'].valid_until > 0)

        # Modify server capacity, make sure it is refreshed.
        server_obj1 = self.master.servers['test.xx.com']
        zk_content['servers']['test.xx.com']['memory'] = '32G'
        self.master.reload_servers(['test.xx.com'])
        server_obj2 = self.master.servers['test.xx.com']
        self.assertTrue(server_obj2.valid_until > 0)

        self.assertIn('test.xx.com', rack_2345.children_by_name)
        self.assertNotEqual(id(server_obj1), id(server_obj2))

        # If server is removed, make sure it is remove from the model.
        del zk_content['servers']['test.xx.com']
        self.master.reload_servers(['test.xx.com'])
        self.assertNotIn('test.xx.com', rack_2345.children_by_name)
        self.assertNotIn('test.xx.com', self.master.servers)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=0))
    def test_adjust_server_state(self):
        """Tests load of server and bucket data."""
        zk_content = {
            'placement': {},
            'server.presence': {},
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'pod:pod2': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
            'servers': {
                'test.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
            },
        }

        time.time.return_value = 100
        self.make_mock_zk(zk_content)
        self.master.load_buckets()
        self.master.load_servers()

        self.assertEqual(
            (scheduler.State.down, 100),
            self.master.servers['test.xx.com'].get_state()
        )

        zk_content['server.presence']['test.xx.com'] = {}

        time.time.return_value = 200
        self.master.adjust_server_state('test.xx.com')
        self.assertEqual(
            (scheduler.State.up, 200),
            self.master.servers['test.xx.com'].get_state()
        )
        treadmill.zkutils.put.assert_called_with(
            mock.ANY,
            '/placement/test.xx.com',
            {'state': 'up', 'since': 200},
            acl=mock.ANY
        )
        event = os.path.join(
            self.server_events_dir,
            '200,test.xx.com,server_state,up'
        )
        self.assertTrue(os.path.exists(event))

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    def test_load_allocations(self):
        """Tests loading allocation from serialized db data."""
        kazoo.client.KazooClient.get.return_value = ("""
---
- name: treadmill/dev
  assignments:
  - pattern: treadmlx.*
    priority: 10
  - pattern: "*@treadmill-users.test"
    priority: 42
  rank: 100
  cpu: 100%
  disk: 1G
  memory: 1G
""", None)

        self.master.load_allocations()

        root = self.master.cell.partitions[None].allocation
        self.assertIn('treadmill', root.sub_allocations)
        leaf_alloc = root.get_sub_alloc('treadmill').get_sub_alloc('dev')
        self.assertEqual(100, leaf_alloc.rank)
        self.assertEqual(1024, leaf_alloc.reserved[0])
        self.assertEqual(100, leaf_alloc.reserved[1])
        self.assertEqual(1024, leaf_alloc.reserved[2])

        assignments = self.master.assignments
        self.assertEqual(
            [(mock.ANY, 10, leaf_alloc)],
            assignments['treadmlx']
        )
        self.assertEqual(
            [(mock.ANY, 42, leaf_alloc)],
            assignments['treadmill-users']
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_load_apps_blacklist(self):
        """Tests loading application blacklist."""
        zk_content = {
            'blackedout.apps': {
                '.data': """
                    xxx.*: {reason: test, when: 1234567890.0}
                    yyy.app3: {reason: test, when: 1234567890.0}
                """,
            },
            'scheduled': {
                'xxx.app1#1234': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app2#2345': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'yyy.app3#3456': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'yyy.app4#4567': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'zzz.app5#5678': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
            },
        }
        self.make_mock_zk(zk_content)

        self.master.load_apps_blacklist()
        self.assertEqual(
            sorted(self.master.apps_blacklist),
            ['xxx.*', 'yyy.app3']
        )

        self.master.load_apps()
        self.assertTrue(self.master.cell.apps['xxx.app1#1234'].blacklisted)
        self.assertTrue(self.master.cell.apps['xxx.app2#2345'].blacklisted)
        self.assertTrue(self.master.cell.apps['yyy.app3#3456'].blacklisted)
        self.assertFalse(self.master.cell.apps['yyy.app4#4567'].blacklisted)
        self.assertFalse(self.master.cell.apps['zzz.app5#5678'].blacklisted)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    def test_load_apps(self):
        """Tests loading application data."""
        zk_content = {
            'scheduled': {
                'foo.bar#1234': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'affinity': 'foo.bar',
                    'data_retention_timeout': None,
                },
            },
        }
        self.make_mock_zk(zk_content)
        self.master.load_apps()

        self.assertIn('foo.bar#1234', self.master.cell.apps)
        self.assertEqual(self.master.cell.apps['foo.bar#1234'].priority, 1)

        zk_content['scheduled']['foo.bar#1234']['priority'] = 5
        self.master.load_apps()
        self.assertEqual(len(self.master.cell.apps), 1)
        self.assertEqual(self.master.cell.apps['foo.bar#1234'].priority, 5)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.update', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=123.34))
    def test_remove_app(self):
        """Tests removing application from scheduler."""
        zk_content = {
            'placement': {
                'test.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.metadata': {'created': 100},
                    },
                    'xxx.app2#2345': {
                        '.metadata': {'created': 101},
                    },
                }
            },
            'server.presence': {
                'test.xx.com': {
                    '.metadata': {'created': 100},
                },
            },
            'cell': {
                'pod:pod1': {},
                'pod:pod2': {},
            },
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'pod:pod2': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
            'servers': {
                'test.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
            },
            'scheduled': {
                'xxx.app1#1234': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app2#2345': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app3#3456': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app4#4567': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
            },
            'finished': {
                'xxx.app2#2345': {},
            },
        }
        self.make_mock_zk(zk_content)

        self.master.load_buckets()
        self.master.load_cell()
        self.master.load_servers()
        self.master.load_apps()
        self.master.restore_placements()

        # Not loaded, ignore.
        self.master.remove_app('xxx.app0#0123')

        # Delete placement, create finished node.
        self.master.remove_app('xxx.app1#1234')

        treadmill.zkutils.ensure_deleted.assert_called_with(
            mock.ANY,
            '/placement/test.xx.com/xxx.app1#1234'
        )
        event = os.path.join(
            self.app_events_dir,
            '123.34,xxx.app1#1234,deleted,'
        )
        self.assertTrue(os.path.exists(event))
        treadmill.zkutils.put.assert_called_with(
            mock.ANY,
            '/finished/xxx.app1#1234',
            {
                'state': 'terminated',
                'when': 123.34,
                'host': 'test.xx.com',
                'data': None,
            },
            acl=mock.ANY
        )
        self.assertNotIn('xxx.app1#1234', self.master.cell.apps)

        # Delete placement, finished node already exists.
        treadmill.zkutils.put.reset_mock()

        self.master.remove_app('xxx.app2#2345')

        treadmill.zkutils.ensure_deleted.assert_called_with(
            mock.ANY,
            '/placement/test.xx.com/xxx.app2#2345'
        )
        event = os.path.join(
            self.app_events_dir,
            '123.34,xxx.app2#2345,deleted,'
        )
        self.assertTrue(os.path.exists(event))
        treadmill.zkutils.put.assert_not_called()
        self.assertNotIn('xxx.app2#2345', self.master.cell.apps)

        # No placement, create finished node without host.
        treadmill.zkutils.ensure_deleted.reset_mock()

        self.master.remove_app('xxx.app3#3456')

        treadmill.zkutils.ensure_deleted.assert_not_called()
        event = os.path.join(
            self.app_events_dir,
            '123.34,xxx.app3#3456,deleted,'
        )
        self.assertTrue(os.path.exists(event))
        treadmill.zkutils.put.assert_called_with(
            mock.ANY,
            '/finished/xxx.app3#3456',
            {
                'state': 'terminated',
                'when': 123.34,
                'host': None,
                'data': None,
            },
            acl=mock.ANY
        )
        self.assertNotIn('xxx.app3#3456', self.master.cell.apps)

        self.assertEqual(list(self.master.cell.apps), ['xxx.app4#4567'])

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.update', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=500))
    def test_reschedule(self):
        """Tests application placement."""
        srv_1 = scheduler.Server('1', [10, 10, 10],
                                 valid_until=1000, traits=0)
        srv_2 = scheduler.Server('2', [10, 10, 10],
                                 valid_until=1000, traits=0)
        srv_3 = scheduler.Server('3', [10, 10, 10],
                                 valid_until=1000, traits=0)
        srv_4 = scheduler.Server('4', [10, 10, 10],
                                 valid_until=1000, traits=0)
        cell = self.master.cell
        cell.add_node(srv_1)
        cell.add_node(srv_2)
        cell.add_node(srv_3)
        cell.add_node(srv_4)

        app1 = scheduler.Application('app1', 4, [1, 1, 1], 'app')
        app2 = scheduler.Application('app2', 3, [2, 2, 2], 'app')

        cell.add_app(cell.partitions[None].allocation, app1)
        cell.add_app(cell.partitions[None].allocation, app2)

        # At this point app1 is on server 1, app2 on server 2.
        self.master.reschedule()
        treadmill.zkutils.put.assert_has_calls([
            mock.call(mock.ANY, '/placement/1/app1',
                      {'expires': 500, 'identity': None}, acl=mock.ANY),
            mock.call(mock.ANY, '/placement/2/app2',
                      {'expires': 500, 'identity': None}, acl=mock.ANY),
        ], any_order=True)

        treadmill.zkutils.ensure_deleted.reset_mock()
        treadmill.zkutils.put.reset_mock()
        srv_1.state = scheduler.State.down
        self.master.reschedule()

        treadmill.zkutils.ensure_deleted.assert_has_calls([
            mock.call(mock.ANY, '/placement/1/app1'),
        ])
        treadmill.zkutils.put.assert_has_calls([
            mock.call(mock.ANY, '/placement/3/app1',
                      {'expires': 500, 'identity': None}, acl=mock.ANY),
            mock.call(mock.ANY, '/placement', mock.ANY, acl=mock.ANY),
        ])
        # Verify that placement data was properly saved as a compressed json.
        args, _kwargs = treadmill.zkutils.put.call_args_list[1]
        placement_data = args[2]
        placement = json.loads(
            zlib.decompress(placement_data).decode()
        )
        self.assertIn(['app1', '1', 500, '3', 500], placement)
        self.assertIn(['app2', '2', 500, '2', 500], placement)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.update', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=500))
    def test_reschedule_maxutil(self):
        """Tests application placement."""
        srv_1 = scheduler.Server('1', [10, 10, 10],
                                 valid_until=1000, traits=0)
        srv_2 = scheduler.Server('2', [10, 10, 10],
                                 valid_until=1000, traits=0)
        srv_3 = scheduler.Server('3', [10, 10, 10],
                                 valid_until=1000, traits=0)
        srv_4 = scheduler.Server('4', [10, 10, 10],
                                 valid_until=1000, traits=0)
        cell = self.master.cell
        cell.add_node(srv_1)
        cell.add_node(srv_2)
        cell.add_node(srv_3)
        cell.add_node(srv_4)

        app1 = scheduler.Application('app1', 4, [1, 1, 1], 'app')
        app2 = scheduler.Application('app2', 3, [2, 2, 2], 'app')

        cell.partitions[None].allocation.set_reserved([1, 1, 1])
        cell.partitions[None].allocation.set_max_utilization(2)
        cell.add_app(cell.partitions[None].allocation, app1)
        cell.add_app(cell.partitions[None].allocation, app2)

        self.master.reschedule()
        treadmill.zkutils.put.assert_has_calls([
            mock.call(mock.ANY, '/placement/1/app1',
                      {'expires': 500, 'identity': None}, acl=mock.ANY),
        ])

        app2.priority = 5
        self.master.reschedule()

        treadmill.zkutils.ensure_deleted.assert_has_calls([
            mock.call(mock.ANY, '/placement/1/app1'),
        ])
        treadmill.zkutils.put.assert_has_calls([
            mock.call(mock.ANY, '/placement/2/app2',
                      {'expires': 500, 'identity': None}, acl=mock.ANY),
        ])

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.update', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=500))
    def test_reschedule_once(self):
        """Tests application placement."""
        srv_1 = scheduler.Server('1', [10, 10, 10],
                                 valid_until=1000, traits=0)
        srv_2 = scheduler.Server('2', [10, 10, 10],
                                 valid_until=1000, traits=0)
        srv_3 = scheduler.Server('3', [10, 10, 10],
                                 valid_until=1000, traits=0)
        srv_4 = scheduler.Server('4', [10, 10, 10],
                                 valid_until=1000, traits=0)
        cell = self.master.cell
        cell.add_node(srv_1)
        cell.add_node(srv_2)
        cell.add_node(srv_3)
        cell.add_node(srv_4)

        app1 = scheduler.Application('app1', 4, [1, 1, 1], 'app',
                                     schedule_once=True)
        app2 = scheduler.Application('app2', 3, [2, 2, 2], 'app')

        cell.add_app(cell.partitions[None].allocation, app1)
        cell.add_app(cell.partitions[None].allocation, app2)

        # At this point app1 is on server 1, app2 on server 2.
        self.master.reschedule()
        treadmill.zkutils.put.assert_has_calls([
            mock.call(mock.ANY, '/placement/1/app1',
                      {'expires': 500, 'identity': None}, acl=mock.ANY),
            mock.call(mock.ANY, '/placement/2/app2',
                      {'expires': 500, 'identity': None}, acl=mock.ANY),
        ], any_order=True)

        srv_1.state = scheduler.State.down
        self.master.reschedule()

        treadmill.zkutils.ensure_deleted.assert_has_calls([
            mock.call(mock.ANY, '/placement/1/app1'),
            mock.call(mock.ANY, '/scheduled/app1'),
        ])

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    def test_load_allocation(self):
        """Tests loading allocation."""
        zk_content = {
            'allocations': {
                '.data': """
                    - name: foo
                      partition: p
                      rank: 100
                      rank_adjustment: 10
                      max_utilization: 1.1
                """
            }
        }

        self.make_mock_zk(zk_content)
        self.master.load_allocations()

        partition = self.master.cell.partitions['p']
        alloc = partition.allocation.get_sub_alloc('foo')
        self.assertEqual(alloc.rank, 100)
        self.assertEqual(alloc.rank_adjustment, 10)
        self.assertEqual(alloc.max_utilization, 1.1)

    @unittest.skip('Randomly fails with "AssertionError: 21 != 22" line 660')
    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    def test_load_partition(self):
        """Tests loading partition."""
        # Access to protected member warning.
        #
        # pylint: disable=W0212
        zk_content = {
            'partitions': {
                'test': {
                    '.data': """
                        partition: test
                        cell: foo
                        memory: 10G
                        cpu: 300%
                        disk: 10G
                        reboot-schedule:
                            5: [23, 59, 59]
                            6: [23, 59, 59]
                    """
                }
            }
        }

        self.make_mock_zk(zk_content)
        self.master.load_partitions()

        partition = self.master.cell.partitions['test']
        # 2 days a week times 3 weeks plus one as a sentinel
        self.assertEqual(len(partition._reboot_buckets), 2 * 3 + 1)

        zk_content = {
            'partitions': {
                'test': {
                    '.data': """
                        partition: test
                        cell: foo
                        memory: 10G
                        cpu: 300%
                        disk: 10G
                    """
                }
            }
        }

        self.make_mock_zk(zk_content)
        self.master.load_partitions()

        partition = self.master.cell.partitions['test']
        # 7 days a week times 3 weeks plus one as a sentinel
        self.assertEqual(len(partition._reboot_buckets), 7 * 3 + 1)

        zk_content = {
            'partitions': {
                'test': {
                    '.data': """
                        partition: test
                        cell: foo
                        memory: 10G
                        cpu: 300%
                        disk: 10G
                        reboot-schedule:
                            1: [10, 0, 0]
                    """
                }
            }
        }

        self.make_mock_zk(zk_content)
        self.master.load_partitions()

        partition = self.master.cell.partitions['test']
        # 1 day a week times 3 weeks plus one as a sentinel
        self.assertEqual(len(partition._reboot_buckets), 1 * 3 + 1)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.update', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=123.34))
    def test_restore_placement(self):
        """Tests application placement."""
        zk_content = {
            'placement': {
                'test1.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.metadata': {'created': 100},
                        '.data': """
                            expires: 300
                            identity: 1
                        """,
                    },
                    'xxx.app2#2345': {
                        '.metadata': {'created': 101},
                        '.data': """
                            expires: 300
                        """,
                    },
                },
                'test2.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app3#3456': {
                        '.metadata': {'created': 100},
                        '.data': """
                            expires: 300
                        """,
                    },
                    'xxx.app4#4567': {
                        '.metadata': {'created': 101},
                        '.data': """
                            expires: 300
                        """,
                    },
                },
                'test3.xx.com': {
                    '.data': """
                        state: down
                        since: 100
                    """,
                    'xxx.app5#5678': {
                        '.metadata': {'created': 100},
                        '.data': """
                            expires: 300
                        """,
                    },
                },
            },
            'server.presence': {
                'test1.xx.com': {
                    '.metadata': {'created': 100},
                },
                'test2.xx.com': {
                    '.metadata': {'created': 200},
                },
            },
            'cell': {
                'pod:pod1': {},
                'pod:pod2': {},
            },
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'pod:pod2': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
            'servers': {
                'test1.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
                'test2.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
                'test3.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
            },
            'scheduled': {
                'xxx.app1#1234': {
                    'affinity': 'app1',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                    'identity_group': 'xxx.app1',
                },
                'xxx.app2#2345': {
                    'affinity': 'app2',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                    'schedule_once': True,
                },
                'xxx.app3#3456': {
                    'affinity': 'app3',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app4#4567': {
                    'affinity': 'app4',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                    'schedule_once': True,
                },
                'xxx.app5#5678': {
                    'affinity': 'app5',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                    'schedule_once': True,
                },
            },
            'identity-groups': {
                'xxx.app1': {
                    'count': 5,
                }
            }
        }

        self.make_mock_zk(zk_content)
        self.master.load_buckets()
        self.master.load_cell()
        self.master.load_servers()
        self.master.load_apps()
        self.master.load_identity_groups()
        self.master.restore_placements()

        # Severs test1.xx.com and test2.xx.com are up, test3.xx.com is down.
        self.assertTrue(
            self.master.servers['test1.xx.com'].state is scheduler.State.up
        )
        self.assertTrue(
            self.master.servers['test2.xx.com'].state is scheduler.State.up
        )
        self.assertTrue(
            self.master.servers['test3.xx.com'].state is scheduler.State.down
        )

        # xxx.app1#1234 restored on test1.xx.com with the same placement expiry
        self.assertEqual(
            self.master.cell.apps['xxx.app1#1234'].server, 'test1.xx.com'
        )
        self.assertEqual(
            self.master.cell.apps['xxx.app1#1234'].placement_expiry, 300
        )

        # xxx.app2#2345 restored on test2.xx.com with the same placement expiry
        self.assertEqual(
            self.master.cell.apps['xxx.app2#2345'].server, 'test1.xx.com'
        )
        self.assertEqual(
            self.master.cell.apps['xxx.app2#2345'].placement_expiry, 300
        )

        # xxx.app3#3456 restored on test2.xx.com with new placement expiry
        self.assertEqual(
            self.master.cell.apps['xxx.app3#3456'].server, 'test2.xx.com'
        )
        self.assertEqual(
            self.master.cell.apps['xxx.app3#3456'].placement_expiry, 123.34
        )

        # xxx.app4#4567 removed (server presence changed, schedule once app)
        self.assertNotIn('xxx.app4#4567', self.master.cell.apps)
        treadmill.zkutils.ensure_deleted.assert_any_call(
            mock.ANY,
            '/placement/test2.xx.com/xxx.app4#4567'
        )
        treadmill.zkutils.put.assert_any_call(
            mock.ANY,
            '/finished/xxx.app4#4567',
            {
                'state': 'terminated',
                'host': 'test2.xx.com',
                'when': 123.34,
                'data': 'schedule_once',
            },
            acl=mock.ANY
        )
        treadmill.zkutils.ensure_deleted.assert_any_call(
            mock.ANY,
            '/scheduled/xxx.app4#4567'
        )

        # xxx.app5#5678 removed (server down, schedule once app)
        self.assertNotIn('xxx.app5#5678', self.master.cell.apps)
        treadmill.zkutils.ensure_deleted.assert_any_call(
            mock.ANY,
            '/placement/test3.xx.com/xxx.app5#5678'
        )
        treadmill.zkutils.put.assert_any_call(
            mock.ANY,
            '/finished/xxx.app5#5678',
            {
                'state': 'terminated',
                'host': 'test3.xx.com',
                'when': 123.34,
                'data': 'schedule_once',
            },
            acl=mock.ANY
        )
        treadmill.zkutils.ensure_deleted.assert_any_call(
            mock.ANY,
            '/scheduled/xxx.app5#5678'
        )

        # Reschedule should produce no events.
        treadmill.zkutils.ensure_deleted.reset_mock()
        treadmill.zkutils.ensure_exists.reset_mock()
        self.master.reschedule()
        self.assertFalse(treadmill.zkutils.ensure_deleted.called)
        self.assertFalse(treadmill.zkutils.ensure_exists.called)

        # Restore identity
        self.assertEqual(self.master.cell.apps['xxx.app1#1234'].identity, 1)
        self.assertEqual(
            self.master.cell.apps['xxx.app1#1234'].identity_group, 'xxx.app1'
        )
        self.assertEqual(
            self.master.cell.identity_groups['xxx.app1'].available,
            set([0, 2, 3, 4])
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.update', mock.Mock())
    def test_restore_with_integrity_err(self):
        """Tests application placement."""
        zk_content = {
            'placement': {
                'test1.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.metadata': {'created': 100},
                    },
                    'xxx.app2#2345': {
                        '.metadata': {'created': 101},
                    },
                },
                'test2.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.metadata': {'created': 100},
                    },
                }
            },
            'server.presence': {
                'test1.xx.com': {
                    '.metadata': {'created': 100},
                },
                'test2.xx.com': {
                    '.metadata': {'created': 100},
                },
            },
            'cell': {
                'pod:pod1': {},
                'pod:pod2': {},
            },
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'pod:pod2': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
            'servers': {
                'test1.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
                'test2.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
            },
            'scheduled': {
                'xxx.app1#1234': {
                    'affinity': 'app1',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app2#2345': {
                    'affinity': 'app2',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
            }
        }

        self.make_mock_zk(zk_content)
        self.master.load_buckets()
        self.master.load_cell()
        self.master.load_servers()
        self.master.load_apps()
        self.master.restore_placements()

        self.assertIn('xxx.app2#2345',
                      self.master.servers['test1.xx.com'].apps)
        self.assertIsNone(self.master.cell.apps['xxx.app1#1234'].server)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=100))
    def test_apps_blacklist_events(self):
        """Tests apps_blacklist events."""
        zk_content = {
            'scheduled': {
                'xxx.app1#1234': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app2#2345': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'yyy.app3#3456': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'yyy.app4#4567': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'zzz.app5#5678': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
            },
            'events': {
                '000-apps_blacklist-12345': None,
            },
        }

        self.make_mock_zk(zk_content)

        self.master.load_apps()
        self.assertFalse(self.master.cell.apps['xxx.app1#1234'].blacklisted)
        self.assertFalse(self.master.cell.apps['xxx.app2#2345'].blacklisted)
        self.assertFalse(self.master.cell.apps['yyy.app3#3456'].blacklisted)
        self.assertFalse(self.master.cell.apps['yyy.app4#4567'].blacklisted)
        self.assertFalse(self.master.cell.apps['zzz.app5#5678'].blacklisted)

        zk_content['blackedout.apps'] = {
            '.data': """
                xxx.*: {reason: test, when: 1234567890.0}
                yyy.app3: {reason: test, when: 1234567890.0}
            """
        }
        self.master.process_events(['000-apps_blacklist-12345'])
        self.assertTrue(self.master.cell.apps['xxx.app1#1234'].blacklisted)
        self.assertTrue(self.master.cell.apps['xxx.app2#2345'].blacklisted)
        self.assertTrue(self.master.cell.apps['yyy.app3#3456'].blacklisted)
        self.assertFalse(self.master.cell.apps['yyy.app4#4567'].blacklisted)
        self.assertFalse(self.master.cell.apps['zzz.app5#5678'].blacklisted)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.scheduler.master.Master.load_allocations',
                mock.Mock())
    @mock.patch('treadmill.scheduler.master.Master.load_apps', mock.Mock())
    @mock.patch('treadmill.scheduler.master.Master.load_app', mock.Mock())
    def test_app_events(self):
        """Tests application placement."""
        zk_content = {
            'events': {
                '001-allocations-12345': {},
                '000-apps-12346': {
                    '.data': """
                        - xxx.app1#1234
                        - xxx.app2#2345
                    """
                },
            },
        }

        self.make_mock_zk(zk_content)
        self.master.watch('/events')
        while True:
            try:
                event = self.master.queue.popleft()
                self.master.process(event)
            except IndexError:
                break

        self.assertTrue(master.Master.load_allocations.called)
        self.assertTrue(master.Master.load_apps.called)
        master.Master.load_app.assert_has_calls([
            mock.call('xxx.app1#1234'),
            mock.call('xxx.app2#2345'),
        ])

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.scheduler.master.Master.load_allocations',
                mock.Mock())
    @mock.patch('treadmill.scheduler.master.Master.load_apps', mock.Mock())
    @mock.patch('treadmill.scheduler.master.Master.load_app', mock.Mock())
    def test_alloc_events(self):
        """Tests allocation events."""
        zk_content = {
            'events': {
                '001-allocations-12345': {},
            },
        }

        self.make_mock_zk(zk_content)
        self.master.watch('/events')
        while True:
            try:
                event = self.master.queue.popleft()
                self.master.process(event)
            except IndexError:
                break

        self.assertTrue(master.Master.load_allocations.called)
        self.assertTrue(master.Master.load_apps.called)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=100))
    def test_server_state_events(self):
        """Tests server_state events."""
        zk_content = {
            'placement': {
                'test.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.metadata': {'created': 100},
                    },
                    'xxx.app2#2345': {
                        '.metadata': {'created': 101},
                    },
                },
            },
            'server.presence': {
                'test.xx.com': {
                    '.metadata': {'created': 100},
                },
            },
            'cell': {
                'pod:pod1': {},
            },
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
            'servers': {
                'test.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
            },
            'scheduled': {
                'xxx.app1#1234': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app2#2345': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
            },
            'events': {
                '000-server_state-12345': {
                    '.data': """
                        - test.xx.com
                        - frozen
                        - [xxx.app1#1234]
                    """
                },
            },
        }

        self.make_mock_zk(zk_content)

        self.master.load_buckets()
        self.master.load_cell()
        self.master.load_servers()
        self.master.load_apps()
        self.master.restore_placements()

        # Set server state to frozen and unschedule app.
        time.time.return_value = 200

        self.master.process_events(['000-server_state-12345'])

        self.assertEqual(
            self.master.servers['test.xx.com'].get_state(),
            (scheduler.State.frozen, 200),
        )
        self.assertTrue(self.master.cell.apps['xxx.app1#1234'].unschedule)
        self.assertFalse(self.master.cell.apps['xxx.app2#2345'].unschedule)
        treadmill.zkutils.put.assert_called_with(
            mock.ANY,
            '/placement/test.xx.com',
            {'state': 'frozen', 'since': 200},
            acl=mock.ANY
        )
        event = os.path.join(
            self.server_events_dir,
            '200,test.xx.com,server_state,frozen'
        )
        self.assertTrue(os.path.exists(event))

        # Reschedule, remove app from the server, delete placement, post event.
        # App becomes pending, there is no other server where it can be placed.
        self.master.reschedule()
        self.assertEqual(
            self.master.cell.apps['xxx.app1#1234'].server,
            None
        )
        self.assertEqual(
            self.master.cell.apps['xxx.app2#2345'].server,
            'test.xx.com'
        )
        treadmill.zkutils.ensure_deleted.assert_called_with(
            mock.ANY,
            '/placement/test.xx.com/xxx.app1#1234'
        )
        event = os.path.join(
            self.app_events_dir,
            '200,xxx.app1#1234,pending,test.xx.com:frozen'
        )
        self.assertTrue(os.path.exists(event))

        # Set server state to up.
        time.time.return_value = 300
        zk_content['events']['000-server_state-12345']['.data'] = """
            - test.xx.com
            - up
            - []
        """

        self.master.process_events(['000-server_state-12345'])

        self.assertEqual(
            self.master.servers['test.xx.com'].get_state(),
            (scheduler.State.up, 300),
        )
        treadmill.zkutils.put.assert_called_with(
            mock.ANY,
            '/placement/test.xx.com',
            {'state': 'up', 'since': 300},
            acl=mock.ANY
        )
        event = os.path.join(
            self.server_events_dir,
            '300,test.xx.com,server_state,up'
        )
        self.assertTrue(os.path.exists(event))

        # Set server state to down.
        time.time.return_value = 400
        zk_content['events']['000-server_state-12345']['.data'] = """
            - test.xx.com
            - down
            - []
        """

        self.master.process_events(['000-server_state-12345'])

        self.assertEqual(
            self.master.servers['test.xx.com'].get_state(),
            (scheduler.State.down, 400),
        )
        treadmill.zkutils.put.assert_called_with(
            mock.ANY,
            '/placement/test.xx.com',
            {'state': 'down', 'since': 400},
            acl=mock.ANY
        )
        event = os.path.join(
            self.server_events_dir,
            '400,test.xx.com,server_state,down'
        )
        self.assertTrue(os.path.exists(event))

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=123.34))
    @mock.patch('treadmill.trace.app.zk._HOSTNAME', 'xxx')
    def test_create_apps(self):
        """Tests app api."""
        zkclient = treadmill.zkutils.ZkClient()
        kazoo.client.KazooClient.create.return_value = '/scheduled/foo.bar#12'

        masterapi.create_apps(zkclient, 'foo.bar', {}, 2)

        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call(
                '/scheduled/foo.bar#',
                value=b'{}\n',
                makepath=True,
                sequence=True,
                ephemeral=False,
                acl=mock.ANY
            ),
            mock.call(
                '/trace/000C/foo.bar#12,123.34,xxx,pending,created',
                value=b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            ),
            # Mock call returns same instance (#12), so same task is created
            # twice.
            mock.call('/scheduled/foo.bar#',
                      value=b'{}\n',
                      makepath=True,
                      sequence=True,
                      ephemeral=False,
                      acl=mock.ANY),
            mock.call('/trace/000C/foo.bar#12,123.34,xxx,pending,created',
                      value=b'',
                      ephemeral=False, makepath=True, sequence=False,
                      acl=mock.ANY)
        ])

        kazoo.client.KazooClient.create.reset_mock()
        masterapi.create_apps(zkclient, 'foo.bar', {}, 1, 'monitor')
        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call('/scheduled/foo.bar#',
                      value=b'{}\n',
                      makepath=True,
                      sequence=True,
                      ephemeral=False,
                      acl=mock.ANY),
            mock.call(
                '/trace/000C/foo.bar#12,123.34,xxx,pending,monitor:created',
                value=b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            )
        ])

    @mock.patch('kazoo.client.KazooClient.get_children',
                mock.Mock(return_value=[]))
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=123.34))
    @mock.patch('treadmill.trace.app.zk._HOSTNAME', 'xxx')
    def test_delete_apps(self):
        """Tests app api."""
        zkclient = treadmill.zkutils.ZkClient()

        masterapi.delete_apps(zkclient, ['foo.bar#12', 'foo.bar#22'])
        kazoo.client.KazooClient.delete.assert_has_calls([
            mock.call('/scheduled/foo.bar#12'),
            mock.call('/scheduled/foo.bar#22')
        ])
        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call(
                '/trace/000C/foo.bar#12,123.34,xxx,pending_delete,deleted',
                value=b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            ),
            mock.call(
                '/trace/0016/foo.bar#22,123.34,xxx,pending_delete,deleted',
                value=b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            )
        ])

        kazoo.client.KazooClient.delete.reset_mock()
        kazoo.client.KazooClient.create.reset_mock()
        masterapi.delete_apps(zkclient, ['foo.bar#12'], 'monitor')
        kazoo.client.KazooClient.delete.assert_has_calls([
            mock.call('/scheduled/foo.bar#12')
        ])
        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call(
                (
                    '/trace/000C/foo.bar#12,123.34,xxx,'
                    'pending_delete,monitor:deleted'
                ),
                value=b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            )
        ])

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock(
        return_value=('{}', None)))
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    def test_update_app_priority(self):
        """Tests app api."""
        zkclient = treadmill.zkutils.ZkClient()

        kazoo.client.KazooClient.create.return_value = '/events/001-apps-1'
        masterapi.update_app_priorities(zkclient, {'foo.bar#1': 10,
                                                   'foo.bar#2': 20})
        kazoo.client.KazooClient.set.assert_has_calls(
            [
                mock.call('/scheduled/foo.bar#1', b'{priority: 10}\n'),
                mock.call('/scheduled/foo.bar#2', b'{priority: 20}\n'),
            ],
            any_order=True
        )

        # Verify that event is placed correctly.
        kazoo.client.KazooClient.create.assert_called_with(
            '/events/001-apps-', value=mock.ANY,
            makepath=True, acl=mock.ANY, sequence=True, ephemeral=False
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock(
        return_value=('{}', None)))
    @mock.patch('treadmill.zkutils.update', mock.Mock(return_value=None))
    @mock.patch('treadmill.scheduler.masterapi.create_event',
                mock.Mock(return_value=None))
    def test_update_app_priority_noop(self):
        """Tests app api."""
        zkclient = treadmill.zkutils.ZkClient()

        # kazoo.client.KazooClient.create.return_value = '/events/001-apps-1'
        masterapi.update_app_priorities(zkclient, {'foo.bar#1': 10,
                                                   'foo.bar#2': 20})
        treadmill.zkutils.update.assert_has_calls(
            [
                mock.call(mock.ANY, '/scheduled/foo.bar#1', {'priority': 10},
                          check_content=True),
                mock.call(mock.ANY, '/scheduled/foo.bar#2', {'priority': 20},
                          check_content=True),
            ],
            any_order=True
        )

        # Verify that event is placed correctly.
        self.assertFalse(treadmill.scheduler.masterapi.create_event.called)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock(
        return_value=('{}', None)))
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists',
                mock.Mock(return_value=False))
    def test_cell_insert_bucket(self):
        """Tests inserting bucket into cell."""
        zkclient = treadmill.zkutils.ZkClient()
        kazoo.client.KazooClient.create.return_value = '/events/000-cell-1'
        masterapi.cell_insert_bucket(zkclient, 'pod:pod1')

        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call('/cell/pod:pod1', value=b'',
                      makepath=True, acl=mock.ANY,
                      ephemeral=False,
                      sequence=False),
            mock.call('/events/000-cell-', value=b'',
                      makepath=True, acl=mock.ANY,
                      sequence=True, ephemeral=False)
        ])

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=0))
    def test_load_buckets(self):
        """Test adding new buckets to the topology.
        """
        zk_content = {
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'pod:pod2': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
        }
        time.time.return_value = 100
        self.make_mock_zk(zk_content)
        self.master.load_buckets()

        # Add a new server in a new bucket, make sure it is properly added.
        zk_content['buckets']['rack:4321'] = {
            'traits': None,
            'parent': 'pod:pod2',
        }
        self.master.load_buckets()
        self.assertIn('rack:4321', self.master.buckets)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('treadmill.zkutils.update', mock.Mock())
    @mock.patch('time.time', mock.Mock())
    def test_check_reboot(self):
        """Tests reboot checks."""
        # Access to protected member warning.
        #
        # pylint: disable=W0212
        zk_content = {
            'placement': {
                'test1.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.metadata': {'created': 100},
                    },
                    'xxx.app2#2345': {
                        '.metadata': {'created': 101},
                    },
                },
                'test2.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.metadata': {'created': 100},
                    },
                }
            },
            'server.presence': {
                'test1.xx.com': {
                    '.metadata': {'created': 100},
                },
                'test2.xx.com': {
                    '.metadata': {'created': 100},
                },
            },
            'cell': {
                'pod:pod1': {},
            },
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
            'servers': {
                'test1.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                    'up_since': 100,
                },
                'test2.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                    'up_since': 200,
                },
            },
            'scheduled': {
                'xxx.app1#1234': {
                    'affinity': 'app1',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
            },
        }

        time.time.return_value = 500
        self.make_mock_zk(zk_content)
        self.master.load_buckets()
        self.master.load_cell()
        self.master.load_servers()
        self.master.load_apps()
        self.master.restore_placements()
        self.master.init_schedule()

        expired_at = self.master.servers['test1.xx.com'].valid_until
        time.time.return_value = expired_at - 500

        app_server = self.master.cell.apps['xxx.app1#1234'].server
        free_server = [s for s in ['test1.xx.com', 'test2.xx.com']
                       if s != app_server][0]

        # Run check before app expires.
        self.master.cell.apps['xxx.app1#1234'].placement_expiry = (
            expired_at - 500
        )

        time.time.return_value = expired_at - 600
        self.master.check_reboot()

        treadmill.zkutils.ensure_exists.assert_called_with(
            mock.ANY,
            '/reboots/' + free_server,
            acl=[self.master.backend.zkclient.make_servers_del_acl()]
        )

        # Run check after app expires, shouldn't affect reboot of app server.
        time.time.return_value = expired_at - 400
        self.master.check_reboot()

        for call in treadmill.zkutils.ensure_exists.call_args_list:
            args, _kwargs = call
            _zkclient, path = args
            if '/reboots/' in path:
                self.assertEqual(path, '/reboots/' + free_server)
                self.assertNotEqual(path, '/reboots/' + app_server)

    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    def test_placement_integrity(self):
        """Tests placement integrity."""

        def mock_get_children(zkpath, watch=None):
            """Mock get_children."""
            self.assertIsNone(watch)

            mock_children = {
                '/placement': ['test1.xx.com', 'test2.xx.com', 'test3.xx.com'],
                '/placement/test1.xx.com': ['xxx.app1#1234', 'xxx.app2#2345'],
                '/placement/test2.xx.com': ['xxx.app1#1234'],
            }

            if zkpath == '/placement/test3.xx.com':
                # Node deleted during check.
                raise kazoo.exceptions.NoNodeError

            return mock_children[zkpath]

        kazoo.client.KazooClient.get_children.side_effect = mock_get_children

        self.master.cell.apps['xxx.app1#1234'] = scheduler.Application(
            'xxx.app1#1234', 100, [1, 1, 1], 'app1')
        self.master.cell.apps['xxx.app2#2345'] = scheduler.Application(
            'xxx.app2#2345', 100, [1, 1, 1], 'app1')

        self.master.cell.apps['xxx.app1#1234'].server = 'test1.xx.com'

        self.master.check_placement_integrity()

        treadmill.zkutils.ensure_deleted.assert_called_with(
            mock.ANY,
            '/placement/test2.xx.com/xxx.app1#1234'
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock(
        return_value=(None, None)))
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('treadmill.zkutils.get', mock.Mock(return_value=None))
    @mock.patch('treadmill.zkutils.put', mock.Mock(return_value=False))
    def test_create_server(self):
        """Tests create server API."""
        zkclient = treadmill.zkutils.ZkClient()
        masterapi.create_server(zkclient, 'foo', 'bucket0', '_default')
        treadmill.zkutils.put.assert_called_with(
            zkclient,
            '/servers/foo',
            {'parent': 'bucket0', 'partition': '_default'},
            acl=mock.ANY,
            check_content=True
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock(
        return_value=('{}', None)))
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    def test_update_server_features(self):
        """Tests master.update_server_features()."""
        zkclient = treadmill.zkutils.ZkClient()
        kazoo.client.KazooClient.create.return_value = '/events/000-servers-1'

        masterapi.update_server_features(zkclient, 'foo.ms.com', ['test'])

        kazoo.client.KazooClient.set.assert_has_calls(
            [
                mock.call('/servers/foo.ms.com', b'features: [test]\n'),
            ],
            any_order=True
        )
        # Verify that event is placed correctly.
        kazoo.client.KazooClient.create.assert_called_with(
            '/events/000-servers-', value=mock.ANY,
            makepath=True, acl=mock.ANY, sequence=True, ephemeral=False
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('time.time', mock.Mock())
    def test_readonly_master(self):
        """Tests the ZK operations of a readonly master."""
        zk_content = {
            'traits': {},
            'server.presence': {
                'test1.xx.com': {
                    '.metadata': {'created': 100},
                },
                'test2.xx.com': {
                    '.metadata': {'created': 100},
                },
            },
            'cell': {
                'pod:pod1': {},
            },
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
            'identity-groups': {},
            'partitions': {},
            'blackedout.servers': {},
            'servers': {
                'test1.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                    'up_since': 100,
                },
                'test2.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                    'up_since': 200,
                },
            },
            # Comments indicate zkutils functions that would get called
            # for each entity if the master weren't in readonly mode
            'placement': {  # ensure_exists and put on each placement
                'test1.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {  # on two servers: ensure_deleted
                        '.metadata': {'created': 100},
                    },
                    'xxx.app2#2345': {  # not scheduled: ensure_deleted
                        '.metadata': {'created': 101},
                    },
                },
                'test2.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {  # on two servers: ensure_deleted
                        '.metadata': {'created': 100},
                    },
                }
            },
            'scheduled': {
                'xxx.app1#1234': {
                    'affinity': 'app1',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app3#6789': {  # gets scheduled by init_schedule: put
                    'affinity': 'app3',
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
            }
        }

        time.time.return_value = 500
        self.make_mock_zk(zk_content)
        ro_master = master.Master(
            zkbackend.ZkReadonlyBackend(treadmill.zkutils.ZkClient()),
            'test-cell',

        )
        ro_master.load_model()
        ro_master.init_schedule()

        self.assertFalse(treadmill.zkutils.ensure_deleted.called)
        self.assertFalse(treadmill.zkutils.ensure_exists.called)
        self.assertFalse(treadmill.zkutils.put.called)

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=100))
    def test_check_pending_start(self):
        """Tests checking all scheduled apps that are not running."""
        # Disable warning accessing protected member.
        #
        # pylint: disable=W0212
        zk_content = {
            'placement': {
                'test1.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                },
                'test2.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.metadata': {'created': 100},
                    },
                    'xxx.app2#2345': {
                        '.metadata': {'created': 101},
                    },
                    'xxx.app3#3456': {
                        '.metadata': {'created': 101},
                    },
                },
            },
            'server.presence': {
                'test1.xx.com': {
                    '.metadata': {'created': 100},
                },
                'test2.xx.com': {
                    '.metadata': {'created': 100},
                },
            },
            'cell': {
                'pod:pod1': {},
            },
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
            'servers': {
                'test1.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
                'test2.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
            },
            'scheduled': {
                'xxx.app1#1234': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app2#2345': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app3#3456': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
            },
            'running': {
                'xxx.app2#2345': {},
            },
        }

        self.make_mock_zk(zk_content)

        self.master.load_buckets()
        self.master.load_cell()
        self.master.load_servers()
        self.master.load_apps()
        self.master.restore_placements()

        # app1 and app3 are not running, record server and time.
        time.time.return_value = 200
        self.master._check_pending_start()

        self.assertEqual(
            self.master.pending_start,
            {
                'xxx.app1#1234': {'servername': 'test2.xx.com', 'since': 200},
                'xxx.app3#3456': {'servername': 'test2.xx.com', 'since': 200},
            }
        )
        self.assertEqual(
            self.master.servers['test1.xx.com'].get_state(),
            (scheduler.State.up, 100),
        )
        self.assertEqual(
            self.master.servers['test2.xx.com'].get_state(),
            (scheduler.State.up, 100),
        )

        # app3 is no longer scheduled, remove.
        time.time.return_value = 300
        del zk_content['scheduled']['xxx.app3#3456']
        self.master.remove_app('xxx.app3#3456')
        self.master._check_pending_start()

        self.assertEqual(
            self.master.pending_start,
            {'xxx.app1#1234': {'servername': 'test2.xx.com', 'since': 200}}
        )

        # app1 did not start in the required interval, freeze test2.
        time.time.return_value = 501
        self.master._check_pending_start()

        self.assertEqual(
            self.master.servers['test1.xx.com'].get_state(),
            (scheduler.State.up, 100),
        )
        self.assertEqual(
            self.master.servers['test2.xx.com'].get_state(),
            (scheduler.State.frozen, 501),
        )
        self.assertTrue(self.master.cell.apps['xxx.app1#1234'].unschedule)
        self.assertFalse(self.master.cell.apps['xxx.app2#2345'].unschedule)
        treadmill.zkutils.put.assert_called_with(
            mock.ANY,
            '/placement/test2.xx.com',
            {'state': 'frozen', 'since': 501},
            acl=mock.ANY
        )
        event = os.path.join(
            self.server_events_dir,
            '501,test2.xx.com,server_state,frozen'
        )
        self.assertTrue(os.path.exists(event))

        # Reschedule, move app1 to test1, update placement, post event.
        # app2 stays on test2, it is already running there.
        self.master.reschedule()
        self.assertEqual(
            self.master.cell.apps['xxx.app1#1234'].server,
            'test1.xx.com'
        )
        self.assertEqual(
            self.master.cell.apps['xxx.app2#2345'].server,
            'test2.xx.com'
        )
        treadmill.zkutils.ensure_deleted.assert_called_with(
            mock.ANY,
            '/placement/test2.xx.com/xxx.app1#1234'
        )
        treadmill.zkutils.put.assert_any_call(
            mock.ANY,
            '/placement/test1.xx.com/xxx.app1#1234',
            {'identity': None, 'expires': 501},
            acl=mock.ANY
        )
        event = os.path.join(
            self.app_events_dir,
            '501,xxx.app1#1234,scheduled,test1.xx.com:test2.xx.com:frozen'
        )
        self.assertTrue(os.path.exists(event))

        # app1 is not running yet, record new server and time.
        time.time.return_value = 530
        self.master._check_pending_start()

        self.assertEqual(
            self.master.pending_start,
            {'xxx.app1#1234': {'servername': 'test1.xx.com', 'since': 530}}
        )

        # All apps are running.
        time.time.return_value = 1000
        zk_content['running']['xxx.app1#1234'] = {}
        self.master._check_pending_start()

        self.assertEqual(
            self.master.pending_start,
            {}
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    @mock.patch('treadmill.zkutils.put', mock.Mock())
    def test_blacklisted_apps(self):
        """Tests handling of blacklisted apps."""
        # Disable warning accessing protected member.
        #
        # pylint: disable=W0212
        zk_content = {
            'blackedout.apps': {
                '.data': """
                    xxx.*: {reason: test, when: 1234567890.0}
                    yyy.app3: {reason: test, when: 1234567890.0}
                """,
            },
            'placement': {
                'test.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.metadata': {'created': 100},
                    },
                    'xxx.app2#2345': {
                        '.metadata': {'created': 101},
                    },
                },
            },
            'server.presence': {
                'test.xx.com': {
                    '.metadata': {'created': 100},
                },
            },
            'cell': {
                'pod:pod1': {},
            },
            'buckets': {
                'pod:pod1': {
                    'traits': None,
                },
                'rack:1234': {
                    'traits': None,
                    'parent': 'pod:pod1',
                },
            },
            'servers': {
                'test.xx.com': {
                    'memory': '16G',
                    'disk': '128G',
                    'cpu': '400%',
                    'parent': 'rack:1234',
                },
            },
            'scheduled': {
                'xxx.app1#1234': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'xxx.app2#2345': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'yyy.app3#3456': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'yyy.app4#4567': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
                'zzz.app5#5678': {
                    'memory': '1G',
                    'disk': '1G',
                    'cpu': '100%',
                },
            },
        }

        self.make_mock_zk(zk_content)

        self.master.load_buckets()
        self.master.load_cell()
        self.master.load_servers()
        self.master.load_apps_blacklist()
        self.master.load_apps()
        self.master.restore_placements()

        # xxx.app1, xxx.app2 and yyy.app3 are blacklisted.
        self.master.reschedule()

        self.assertEqual(self.master.cell.apps['xxx.app1#1234'].server, None)
        self.assertEqual(self.master.cell.apps['xxx.app2#2345'].server, None)
        self.assertEqual(self.master.cell.apps['yyy.app3#3456'].server, None)
        self.assertEqual(
            self.master.cell.apps['yyy.app4#4567'].server,
            'test.xx.com'
        )
        self.assertEqual(
            self.master.cell.apps['zzz.app5#5678'].server,
            'test.xx.com'
        )
        treadmill.zkutils.ensure_deleted.assert_has_calls([
            mock.call(mock.ANY, '/placement/test.xx.com/xxx.app1#1234'),
            mock.call(mock.ANY, '/placement/test.xx.com/xxx.app2#2345'),
        ], any_order=True)
        event = os.path.join(
            self.app_events_dir, '*,xxx.app*,pending,blacklisted'
        )
        self.assertEqual(len(glob.glob(event)), 2)

        # Add zzz.app5 to blacklist.
        treadmill.zkutils.ensure_deleted.reset_mock()
        treadmill.zkutils.put.reset_mock()

        zk_content['blackedout.apps'] = {
            '.data': """
                xxx.*: {reason: test, when: 1234567890.0}
                yyy.app3: {reason: test, when: 1234567890.0}
                zzz.app5: {reason: test, when: 1234567890.0}
            """
        }
        zk_content['events'] = {
            '000-apps_blacklist-12345': None,
        }
        self.master.process_events(['000-apps_blacklist-12345'])

        self.master.reschedule()

        self.assertEqual(self.master.cell.apps['xxx.app1#1234'].server, None)
        self.assertEqual(self.master.cell.apps['xxx.app2#2345'].server, None)
        self.assertEqual(self.master.cell.apps['yyy.app3#3456'].server, None)
        self.assertEqual(
            self.master.cell.apps['yyy.app4#4567'].server,
            'test.xx.com'
        )
        self.assertEqual(self.master.cell.apps['zzz.app5#5678'].server, None)
        treadmill.zkutils.ensure_deleted.assert_called_with(
            mock.ANY,
            '/placement/test.xx.com/zzz.app5#5678'
        )
        event = os.path.join(
            self.app_events_dir, '*,zzz.app5#5678,pending,blacklisted'
        )
        self.assertEqual(len(glob.glob(event)), 1)

        # Clear blackout for zzz.app5.
        treadmill.zkutils.ensure_deleted.reset_mock()
        treadmill.zkutils.put.reset_mock()

        zk_content['blackedout.apps'] = {
            '.data': """
                xxx.*: {reason: test, when: 1234567890.0}
                yyy.app3: {reason: test, when: 1234567890.0}
            """
        }
        zk_content['events'] = {
            '000-apps_blacklist-12345': None,
        }
        self.master.process_events(['000-apps_blacklist-12345'])

        self.master.reschedule()

        self.assertEqual(self.master.cell.apps['xxx.app1#1234'].server, None)
        self.assertEqual(self.master.cell.apps['xxx.app2#2345'].server, None)
        self.assertEqual(self.master.cell.apps['yyy.app3#3456'].server, None)
        self.assertEqual(
            self.master.cell.apps['yyy.app4#4567'].server,
            'test.xx.com'
        )
        self.assertEqual(
            self.master.cell.apps['zzz.app5#5678'].server,
            'test.xx.com'
        )
        treadmill.zkutils.put.assert_any_call(
            mock.ANY,
            '/placement/test.xx.com/zzz.app5#5678',
            mock.ANY,
            acl=mock.ANY
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=100))
    def test_blacklisted_servers(self):
        """Tests handling of blacklisted servers."""
        zk_content = {
            'blackedout.servers': {
                'test1.xx.com': {},
                'test2.xx.com': {},
            }
        }

        self.make_mock_zk(zk_content)

        self.master.load_servers_blacklist()
        self.assertEqual(
            self.master.servers_blacklist,
            {'test1.xx.com', 'test2.xx.com'}
        )

        self.master.process_blackedout_servers(
            ['test2.xx.com', 'test3.xx.com']
        )
        events = [
            '100,test3.xx.com,server_blackout,',
            '100,test1.xx.com,server_blackout_cleared,'
        ]
        for event in events:
            self.assertTrue(
                os.path.exists(os.path.join(self.server_events_dir, event))
            )
        self.assertEqual(
            self.master.servers_blacklist,
            {'test2.xx.com', 'test3.xx.com'}
        )


if __name__ == '__main__':
    unittest.main()
