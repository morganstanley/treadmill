"""Unit test for treadmill master.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

# Disable C0302: Too many lines in the module
# pylint: disable=C0302

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

import treadmill
import treadmill.exc
from treadmill import scheduler
from treadmill.scheduler import loader
from treadmill.scheduler import master
from treadmill.scheduler import masterapi
from treadmill.scheduler import zkbackend

from tests.testutils import mockzk


class MasterTest(mockzk.MockZookeeperTestCase):
    """Mock test for treadmill.master."""

    def setUp(self):
        super(MasterTest, self).setUp()

        scheduler.DIMENSION_COUNT = 3

        self.root = tempfile.mkdtemp()
        os.environ['TREADMILL_MASTER_ROOT'] = self.root
        backend = zkbackend.ZkBackend(kazoo.client.KazooClient())
        self.master = master.Master(backend, 'test-cell')
        # Use 111 to assert on zkhandle value.
        # Disable the exit on exception hack for tests
        self.old_exit_on_unhandled = treadmill.utils.exit_on_unhandled
        treadmill.utils.exit_on_unhandled = mock.Mock(side_effect=lambda x: x)

    def tearDown(self):
        if self.root and os.path.isdir(self.root):
            shutil.rmtree(self.root)
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

        # Modify server parent, make sure it is reloaded.
        zk_content['servers']['test.xx.com']['parent'] = 'rack:2345'
        self.master.reload_servers(['test.xx.com'])

        rack_2345 = self.master.cell \
            .children_by_name['pod:pod1'].children_by_name['rack:2345']
        self.assertNotIn('test.xx.com', rack_1234.children_by_name)
        self.assertIn('test.xx.com', rack_2345.children_by_name)

        # Modify server capacity, make sure it is refreshed.
        server_obj1 = self.master.servers['test.xx.com']
        zk_content['servers']['test.xx.com']['memory'] = '32G'
        self.master.reload_servers(['test.xx.com'])
        server_obj2 = self.master.servers['test.xx.com']

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
                        reboot-schedule: [5, 6]
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
                        reboot-schedule: [1]
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
    def test_restore_placement(self):
        """Tests application placement."""
        zk_content = {
            'placement': {
                'test.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': {
                        '.data': '{identity: 1}\n',
                    },
                    'xxx.app2#2345': '',
                }
            },
            'server.presence': {
                'test.xx.com': {},
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
        self.master.restore_placements()
        self.master.load_identity_groups()
        self.master.load_placement_data()

        self.assertTrue(
            self.master.servers['test.xx.com'].state is scheduler.State.up)

        # Reschedule should produce no events.
        treadmill.zkutils.ensure_deleted.reset_mock()
        treadmill.zkutils.ensure_exists.reset_mock()
        self.master.reschedule()
        self.assertFalse(treadmill.zkutils.ensure_deleted.called)
        self.assertFalse(treadmill.zkutils.ensure_exists.called)

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
                    'xxx.app1#1234': '',
                    'xxx.app2#2345': '',
                },
                'test2.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': '',
                }
            },
            'server.presence': {
                'test1.xx.com': {},
                'test2.xx.com': {},
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
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=123.34))
    @mock.patch('treadmill.appevents._HOSTNAME', 'xxx')
    def test_create_apps(self):
        """Tests app api."""
        zkclient = kazoo.client.KazooClient()
        kazoo.client.KazooClient.create.return_value = '/scheduled/foo.bar#12'

        masterapi.create_apps(zkclient, 'foo.bar', {}, 2)

        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call(
                '/scheduled/foo.bar#',
                b'{}\n',
                makepath=True,
                sequence=True,
                ephemeral=False,
                acl=mock.ANY
            ),
            mock.call(
                '/trace/000C/foo.bar#12,123.34,xxx,pending,created',
                b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            ),
            # Mock call returns same instance (#12), so same task is created
            # twice.
            mock.call('/scheduled/foo.bar#',
                      b'{}\n',
                      makepath=True,
                      sequence=True,
                      ephemeral=False,
                      acl=mock.ANY),
            mock.call('/trace/000C/foo.bar#12,123.34,xxx,pending,created',
                      b'',
                      ephemeral=False, makepath=True, sequence=False,
                      acl=mock.ANY)
        ])

        kazoo.client.KazooClient.create.reset_mock()
        masterapi.create_apps(zkclient, 'foo.bar', {}, 1, 'monitor')
        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call('/scheduled/foo.bar#',
                      b'{}\n',
                      makepath=True,
                      sequence=True,
                      ephemeral=False,
                      acl=mock.ANY),
            mock.call(
                '/trace/000C/foo.bar#12,123.34,xxx,pending,monitor:created',
                b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            )
        ])

    @mock.patch('kazoo.client.KazooClient.get_children',
                mock.Mock(return_value=[]))
    @mock.patch('kazoo.client.KazooClient.delete', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    @mock.patch('time.time', mock.Mock(return_value=123.34))
    @mock.patch('treadmill.appevents._HOSTNAME', 'xxx')
    def test_delete_apps(self):
        """Tests app api."""
        zkclient = kazoo.client.KazooClient()

        masterapi.delete_apps(zkclient, ['foo.bar#12', 'foo.bar#22'])
        kazoo.client.KazooClient.delete.assert_has_calls([
            mock.call('/scheduled/foo.bar#12'),
            mock.call('/scheduled/foo.bar#22')
        ])
        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call(
                '/trace/000C/foo.bar#12,123.34,xxx,pending_delete,deleted',
                b'',
                ephemeral=False, makepath=True, sequence=False,
                acl=mock.ANY
            ),
            mock.call(
                '/trace/0016/foo.bar#22,123.34,xxx,pending_delete,deleted',
                b'',
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
                b'',
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
        zkclient = kazoo.client.KazooClient()

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
            '/events/001-apps-', mock.ANY,
            makepath=True, acl=mock.ANY, sequence=True, ephemeral=False
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock(
        return_value=('{}', None)))
    @mock.patch('treadmill.zkutils.update', mock.Mock(return_value=None))
    @mock.patch('treadmill.scheduler.masterapi.create_event',
                mock.Mock(return_value=None))
    def test_update_app_priority_noop(self):
        """Tests app api."""
        zkclient = kazoo.client.KazooClient()

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
        zkclient = kazoo.client.KazooClient()
        kazoo.client.KazooClient.create.return_value = '/events/000-cell-1'
        masterapi.cell_insert_bucket(zkclient, 'pod:pod1')

        kazoo.client.KazooClient.create.assert_has_calls([
            mock.call('/cell/pod:pod1', b'',
                      makepath=True, acl=mock.ANY,
                      sequence=False),
            mock.call('/events/000-cell-', b'',
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
                    'xxx.app1#1234': '',
                    'xxx.app2#2345': '',
                },
                'test2.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': '',
                }
            },
            'server.presence': {
                'test1.xx.com': {},
                'test2.xx.com': {},
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
        self.master.load_placement_data()
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
            acl=[zkbackend._SERVERS_ACL_DEL]
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

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.exists', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.get_children', mock.Mock())
    @mock.patch('treadmill.zkutils.ensure_deleted', mock.Mock())
    def test_placement_integrity(self):
        """Tests placement integrity."""
        zk_content = {
            'placement': {
                'test1.xx.com': {
                    'xxx.app1#1234': '',
                    'xxx.app2#2345': '',
                },
                'test2.xx.com': {
                    'xxx.app1#1234': '',
                }
            },
        }

        self.master.cell.apps['xxx.app1#1234'] = scheduler.Application(
            'xxx.app1#1234', 100, [1, 1, 1], 'app1')
        self.master.cell.apps['xxx.app2#2345'] = scheduler.Application(
            'xxx.app2#2345', 100, [1, 1, 1], 'app1')

        self.master.cell.apps['xxx.app1#1234'].server = 'test1.xx.com'

        self.make_mock_zk(zk_content)
        self.master.check_placement_integrity()

        treadmill.zkutils.ensure_deleted.assert_called_with(
            mock.ANY,
            '/placement/test2.xx.com/xxx.app1#1234'
        )

    @mock.patch('kazoo.client.KazooClient.get', mock.Mock(
        return_value=('{}', None)))
    @mock.patch('kazoo.client.KazooClient.set', mock.Mock())
    @mock.patch('kazoo.client.KazooClient.create', mock.Mock())
    def test_update_server_features(self):
        """Tests master.update_server_features()."""
        zkclient = kazoo.client.KazooClient()
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
            '/events/000-servers-', mock.ANY,
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
            'server.presence': {
                'test1.xx.com': {},
                'test2.xx.com': {},
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
                    'xxx.app1#1234': '',  # on two servers: ensure_deleted
                    'xxx.app2#2345': '',  # not scheduled: ensure_deleted
                },
                'test2.xx.com': {
                    '.data': """
                        state: up
                        since: 100
                    """,
                    'xxx.app1#1234': '',  # on two servers: ensure_deleted
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
            zkbackend.ZkReadonlyBackend(kazoo.client.KazooClient()),
            'test-cell',

        )
        ro_master.load_model()
        ro_master.init_schedule()

        self.assertFalse(treadmill.zkutils.ensure_deleted.called)
        self.assertFalse(treadmill.zkutils.ensure_exists.called)
        self.assertFalse(treadmill.zkutils.put.called)


if __name__ == '__main__':
    unittest.main()
