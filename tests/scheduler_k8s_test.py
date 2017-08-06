"""Unit test for treadmill.scheduler
"""

import time
import unittest
import tempfile

# Disable too many lines in module warning.
#
# pylint: disable=C0302

import mock
import numpy as np

from treadmill.sched import utils as sched_utils
from treadmill import scheduler
from functools import reduce

_TRAITS = dict()


# Helper functions to convert user readable traits to bit mask.
def _trait2int(trait):
    if trait not in _TRAITS:
        _TRAITS[trait] = len(_TRAITS) + 1
    return 2 ** _TRAITS[trait]


def _traits2int(traits):
    return reduce(
        lambda acc, t: acc | _trait2int(t),
        traits,
        0
    )


def app_list(count, name, *args, **kwargs):
    """Return list of apps."""
    return [scheduler.Application(name + '-' + str(idx),
                                  *args, affinity=name, **kwargs)
            for idx in range(0, count)]


class CellTest(unittest.TestCase):
    """treadmill.scheduler.CellWithK8sScheduler tests."""

    def setUp(self):
        scheduler.DIMENSION_COUNT = 2
        # Create config file.
        self.config_file = tempfile.NamedTemporaryFile(
            prefix='treadmill.scheduler.config.', suffix='.json', mode='w+')
        self.config_file.write("""{
          "predicates": [
            {
              "name": "match_app_constraints"
            },
            {
              "name": "match_app_lifetime"
            },
            {
              "name": "alive_servers"
            }
          ],
          "priorities": [
            {
              "name": "spread",
              "weight": 1
            }
          ]
        }""")
        self.config_file.read()
        super(CellTest, self).setUp()

    def test_emtpy(self):
        """Simple test to test empty bucket"""
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)

        empty = scheduler.Bucket('empty', traits=0)
        cell.add_node(empty)

        bucket = scheduler.Bucket('bucket', traits=0)
        srv_a = scheduler.Server('a', [10, 10], traits=0, valid_until=500)
        bucket.add_node(srv_a)

        cell.add_node(bucket)

        cell.schedule()

    def test_labels(self):
        """Test scheduling with labels."""
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        left = scheduler.Bucket('left', traits=0)
        right = scheduler.Bucket('right', traits=0)
        srv_a = scheduler.Server('a_xx', [10, 10], valid_until=500, label='xx')
        srv_b = scheduler.Server('b', [10, 10], valid_until=500)
        srv_y = scheduler.Server('y_xx', [10, 10], valid_until=500, label='xx')
        srv_z = scheduler.Server('z', [10, 10], valid_until=500)

        cell.add_node(left)
        cell.add_node(right)
        left.add_node(srv_a)
        left.add_node(srv_b)
        right.add_node(srv_y)
        right.add_node(srv_z)

        app1 = scheduler.Application('app1', 4, [1, 1], 'app')
        app2 = scheduler.Application('app2', 3, [2, 2], 'app')
        app3 = scheduler.Application('app_xx_3', 2, [3, 3], 'app')
        app4 = scheduler.Application('app_xx_4', 1, [4, 4], 'app')
        cell.partitions[None].allocation.add(app1)
        cell.partitions[None].allocation.add(app2)
        cell.partitions['xx'].allocation.add(app3)
        cell.partitions['xx'].allocation.add(app4)

        cell.schedule()

        self.assertIn(app1.server, ['b', 'z'])
        self.assertIn(app2.server, ['b', 'z'])
        self.assertIn(app3.server, ['a_xx', 'y_xx'])
        self.assertIn(app4.server, ['a_xx', 'y_xx'])

    def test_simple(self):
        """Simple placement test."""
        # pylint - too many lines.
        #
        # pylint: disable=R0915
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        left = scheduler.Bucket('left', traits=0)
        right = scheduler.Bucket('right', traits=0)
        srv_a = scheduler.Server('a', [10, 10], traits=0, valid_until=500)
        srv_b = scheduler.Server('b', [10, 10], traits=0, valid_until=500)
        srv_y = scheduler.Server('y', [10, 10], traits=0, valid_until=500)
        srv_z = scheduler.Server('z', [10, 10], traits=0, valid_until=500)

        cell.add_node(left)
        cell.add_node(right)
        left.add_node(srv_a)
        left.add_node(srv_b)
        right.add_node(srv_y)
        right.add_node(srv_z)

        app1 = scheduler.Application('app1', 4, [1, 1], 'app')
        app2 = scheduler.Application('app2', 3, [2, 2], 'app')
        app3 = scheduler.Application('app3', 2, [3, 3], 'app')
        app4 = scheduler.Application('app4', 1, [4, 4], 'app')
        cell.partitions[None].allocation.add(app1)
        cell.partitions[None].allocation.add(app2)
        cell.partitions[None].allocation.add(app3)
        cell.partitions[None].allocation.add(app4)

        cell.schedule()

        self.assertEqual(
            set([app1.server, app2.server, app3.server, app4.server]),
            set(['a', 'y', 'b', 'z'])
        )

        srv1 = app1.server
        srv2 = app2.server
        srv3 = app3.server
        srv4 = app4.server

        # Add high priority app that needs entire cell
        app_prio50 = scheduler.Application('prio50', 50, [10, 10], 'app')
        cell.partitions[None].allocation.add(app_prio50)
        cell.schedule()

        # The queue is ordered by priority:
        #  - prio50, app1, app2, app3, app4
        #
        # As placement not found for prio50, app4 will be evicted first.
        #
        # As result, prio50 will be placed on 'z', and app4 (evicted) will be
        # placed on "next" server, which is 'a'.
        self.assertEqual(app_prio50.server, srv4)
        self.assertEqual(app4.server, srv1)

        app_prio51 = scheduler.Application('prio51', 51, [10, 10], 'app')
        cell.partitions[None].allocation.add(app_prio51)
        cell.schedule()

        # app4 is now colocated with app1. app4 will still be evicted first,
        # then app3, at which point there will be enough capacity to place
        # large app.
        #
        # app3 will be rescheduled to run on "next" server - 'y', and app4 will
        # be restored to 'a'.
        self.assertEqual(app_prio51.server, srv3)
        self.assertEqual(app_prio50.server, srv4)
        self.assertEqual(app4.server, srv1)

        app_prio49_1 = scheduler.Application('prio49_1', 49, [10, 10], 'app')
        app_prio49_2 = scheduler.Application('prio49_2', 49, [9, 9], 'app')
        cell.partitions[None].allocation.add(app_prio49_1)
        cell.partitions[None].allocation.add(app_prio49_2)
        cell.schedule()

        # 50/51 not moved. from the end of the queue,
        self.assertEqual(app_prio51.server, srv3)
        self.assertEqual(app_prio50.server, srv4)
        self.assertEqual(
            set([app_prio49_1.server, app_prio49_2.server]),
            set([srv1, srv2])
        )

        # Only capacity left for small [1, 1] app.
        self.assertIsNotNone(app1.server)
        self.assertIsNone(app2.server)
        self.assertIsNone(app3.server)
        self.assertIsNone(app4.server)

    def test_max_utilization(self):
        """Test max-utilization is handled properly when priorities change"""
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        left = scheduler.Bucket('left', traits=0)
        right = scheduler.Bucket('right', traits=0)
        srv_a = scheduler.Server('a', [10, 10], traits=0, valid_until=500)
        srv_b = scheduler.Server('b', [10, 10], traits=0, valid_until=500)
        srv_y = scheduler.Server('y', [10, 10], traits=0, valid_until=500)
        srv_z = scheduler.Server('z', [10, 10], traits=0, valid_until=500)

        cell.add_node(left)
        cell.add_node(right)
        left.add_node(srv_a)
        left.add_node(srv_b)
        right.add_node(srv_y)
        right.add_node(srv_z)

        app1 = scheduler.Application('app1', 4, [1, 1], 'app')
        app2 = scheduler.Application('app2', 3, [2, 2], 'app')
        app3 = scheduler.Application('app3', 2, [3, 3], 'app')
        app4 = scheduler.Application('app4', 1, [4, 4], 'app')
        cell.partitions[None].allocation.add(app1)
        cell.partitions[None].allocation.add(app2)
        cell.partitions[None].allocation.add(app3)
        cell.partitions[None].allocation.add(app4)

        cell.partitions[None].allocation.set_reserved([6, 6])
        cell.partitions[None].allocation.set_max_utilization(1)
        cell.schedule()

        self.assertIsNotNone(app1.server)
        self.assertIsNotNone(app2.server)
        self.assertIsNotNone(app3.server)
        self.assertIsNone(app4.server)

        app4.priority = 5
        cell.schedule()

        self.assertIsNotNone(app1.server)
        self.assertIsNone(app2.server)
        self.assertIsNone(app3.server)
        self.assertIsNotNone(app4.server)

    def test_affinity_limits(self):
        """Test affinity limits"""
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        left = scheduler.Bucket('left', traits=0)
        right = scheduler.Bucket('right', traits=0)
        srv_a = scheduler.Server('a', [10, 10], traits=0, valid_until=500)
        srv_b = scheduler.Server('b', [10, 10], traits=0, valid_until=500)
        srv_y = scheduler.Server('y', [10, 10], traits=0, valid_until=500)
        srv_z = scheduler.Server('z', [10, 10], traits=0, valid_until=500)

        cell.add_node(left)
        cell.add_node(right)
        left.add_node(srv_a)
        left.add_node(srv_b)
        right.add_node(srv_y)
        right.add_node(srv_z)

        left.level = 'rack'
        right.level = 'rack'

        apps = app_list(10, 'app', 50, [1, 1],
                        affinity_limits={'server': 1})
        cell.add_app(cell.partitions[None].allocation, apps[0])
        cell.add_app(cell.partitions[None].allocation, apps[1])
        cell.add_app(cell.partitions[None].allocation, apps[2])
        cell.add_app(cell.partitions[None].allocation, apps[3])
        cell.add_app(cell.partitions[None].allocation, apps[4])

        cell.schedule()

        self.assertIsNotNone(apps[0].server)
        self.assertIsNotNone(apps[1].server)
        self.assertIsNotNone(apps[2].server)
        self.assertIsNotNone(apps[3].server)
        self.assertIsNone(apps[4].server)

        for app in apps:
            cell.remove_app(app.name)

        apps = app_list(10, 'app', 50, [1, 1],
                        affinity_limits={'server': 1, 'rack': 1})

        cell.add_app(cell.partitions[None].allocation, apps[0])
        cell.add_app(cell.partitions[None].allocation, apps[1])
        cell.add_app(cell.partitions[None].allocation, apps[2])
        cell.add_app(cell.partitions[None].allocation, apps[3])
        cell.schedule()

        self.assertIsNotNone(apps[0].server)
        self.assertIsNotNone(apps[1].server)
        self.assertIsNone(apps[2].server)
        self.assertIsNone(apps[3].server)

        for app in apps:
            cell.remove_app(app.name)

        apps = app_list(10, 'app', 50, [1, 1],
                        affinity_limits={'server': 1, 'rack': 2, 'cell': 3})

        cell.add_app(cell.partitions[None].allocation, apps[0])
        cell.add_app(cell.partitions[None].allocation, apps[1])
        cell.add_app(cell.partitions[None].allocation, apps[2])
        cell.add_app(cell.partitions[None].allocation, apps[3])
        cell.schedule()

        self.assertIsNotNone(apps[0].server)
        self.assertIsNotNone(apps[1].server)
        self.assertIsNotNone(apps[2].server)
        self.assertIsNone(apps[3].server)

    @mock.patch('time.time', mock.Mock(return_value=0))
    def test_data_retention(self):
        """Tests data retention."""
        # Disable pylint's too many statements warning.
        #
        # pylint: disable=R0915
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        left = scheduler.Bucket('left', traits=0)
        right = scheduler.Bucket('right', traits=0)
        srvs = {
            'a': scheduler.Server('a', [10, 10], traits=0, valid_until=500),
            'b': scheduler.Server('b', [10, 10], traits=0, valid_until=500),
            'y': scheduler.Server('y', [10, 10], traits=0, valid_until=500),
            'z': scheduler.Server('z', [10, 10], traits=0, valid_until=500),
        }
        cell.add_node(left)
        cell.add_node(right)
        left.add_node(srvs['a'])
        left.add_node(srvs['b'])
        right.add_node(srvs['y'])
        right.add_node(srvs['z'])

        left.level = 'rack'
        right.level = 'rack'

        time.time.return_value = 100

        sticky_apps = app_list(10, 'sticky', 50, [1, 1],
                               affinity_limits={'server': 1, 'rack': 1},
                               data_retention_timeout=30)
        unsticky_app = scheduler.Application('unsticky', 10, [1., 1.],
                                             'unsticky',
                                             data_retention_timeout=0)

        cell.partitions[None].allocation.add(sticky_apps[0])
        cell.partitions[None].allocation.add(unsticky_app)

        cell.schedule()

        # Apps should be scheduled on different nodes.
        first_srv = sticky_apps[0].server
        self.assertNotEqual(sticky_apps[0].server, unsticky_app.server)

        # Mark srv_a as down, unsticky app migrates right away,
        # sticky stays.
        srvs[first_srv].state = sched_utils.State.down

        cell.schedule()
        self.assertEqual(sticky_apps[0].server, first_srv)
        self.assertNotEquals(unsticky_app.server, first_srv)
        self.assertEqual(cell.next_event_at, 130)

        time.time.return_value = 110

        cell.schedule()
        self.assertEqual(sticky_apps[0].server, first_srv)
        self.assertNotEquals(unsticky_app.server, first_srv)
        self.assertEqual(cell.next_event_at, 130)

        time.time.return_value = 130
        cell.schedule()
        self.assertNotEquals(sticky_apps[0].server, first_srv)
        self.assertNotEquals(unsticky_app.server, first_srv)
        self.assertEqual(cell.next_event_at, np.inf)

        second_srv = sticky_apps[0].server

        # Mark srv_a as up, srv_y as down.
        srvs[first_srv].state = sched_utils.State.up
        srvs[second_srv].state = sched_utils.State.down

        cell.schedule()
        self.assertEqual(sticky_apps[0].server, second_srv)
        self.assertNotEquals(unsticky_app.server, second_srv)
        self.assertEqual(cell.next_event_at, 160)

        # Schedule one more sticky app. As it has rack affinity limit 1, it
        # can't to to right (x,y) rack, rather will end up in left (a,b) rack.
        #
        # Other sticky apps will be pending.
        time.time.return_value = 135
        cell.partitions[None].allocation.add(sticky_apps[1])
        cell.partitions[None].allocation.add(sticky_apps[2])
        cell.schedule()

        # Original app still on 'y', timeout did not expire
        self.assertEqual(sticky_apps[0].server, second_srv)
        # next sticky app is on (a,b) rack.
        # self.assertIn(sticky_apps[1].server, ['a', 'b'])
        # The 3rd sticky app pending, as rack affinity taken by currently
        # down node y.
        self.assertIsNone(sticky_apps[2].server)

        srvs[second_srv].state = sched_utils.State.up
        cell.schedule()
        # Original app still on 'y', timeout did not expire
        self.assertEqual(sticky_apps[0].server, second_srv)
        # next sticky app is on (a,b) rack.
        # self.assertIn(sticky_apps[1].server, ['a', 'b'])
        # The 3rd sticky app pending, as rack affinity taken by currently
        # app[0] on node y.
        self.assertIsNone(sticky_apps[2].server)

    def test_serialization(self):
        """Tests cell serialization."""
        # Disable pylint's too many statements warning.
        #
        # pylint: disable=R0915
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        left = scheduler.Bucket('left', traits=0)
        right = scheduler.Bucket('right', traits=0)
        srv_a = scheduler.Server('a', [10, 10], traits=0, valid_until=500)
        srv_b = scheduler.Server('b', [10, 10], traits=0, valid_until=500)
        srv_y = scheduler.Server('y', [10, 10], traits=0, valid_until=500)
        srv_z = scheduler.Server('z', [10, 10], traits=0, valid_until=500)

        cell.add_node(left)
        cell.add_node(right)
        left.add_node(srv_a)
        left.add_node(srv_b)
        right.add_node(srv_y)
        right.add_node(srv_z)

        left.level = 'rack'
        right.level = 'rack'

        apps = app_list(10, 'app', 50, [1, 1],
                        affinity_limits={'server': 1, 'rack': 1})

        cell.add_app(cell.partitions[None].allocation, apps[0])
        cell.add_app(cell.partitions[None].allocation, apps[1])
        cell.add_app(cell.partitions[None].allocation, apps[2])
        cell.add_app(cell.partitions[None].allocation, apps[3])

        cell.schedule()

        # TODO: need to implement serialization.
        #
        # data = scheduler.dumps(cell)
        # cell1 = scheduler.loads(data)

    def test_identity(self):
        """Tests scheduling apps with identity."""
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        for idx in range(0, 10):
            server = scheduler.Server(str(idx), [10, 10], traits=0,
                                      valid_until=time.time() + 1000)
            cell.add_node(server)

        cell.configure_identity_group('ident1', 3)
        apps = app_list(10, 'app', 50, [1, 1], identity_group='ident1')
        for app in apps:
            cell.add_app(cell.partitions[None].allocation, app)

        self.assertTrue(apps[0].acquire_identity())
        self.assertEqual(set([1, 2]), apps[0].identity_group_ref.available)
        self.assertEqual(set([1, 2]), apps[1].identity_group_ref.available)

        cell.schedule()

        self.assertEqual(apps[0].identity, 0)
        self.assertEqual(apps[1].identity, 1)
        self.assertEqual(apps[2].identity, 2)
        for idx in range(3, 10):
            self.assertIsNone(apps[idx].identity, None)

        # Removing app will release the identity, and it will be aquired by
        # next app in the group.
        cell.remove_app('app-2')
        cell.schedule()
        self.assertEqual(apps[3].identity, 2)

        # Increase ideneity group count to 5, expect 5 placed apps.
        cell.configure_identity_group('ident1', 5)
        cell.schedule()
        self.assertEqual(
            5,
            len([app for app in apps if app.server is not None])
        )

        cell.configure_identity_group('ident1', 3)
        cell.schedule()
        self.assertEqual(
            3,
            len([app for app in apps if app.server is not None])
        )

    def test_schedule_once(self):
        """Tests schedule once trait on server down."""
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        for idx in range(0, 10):
            server = scheduler.Server(str(idx), [10, 10], traits=0,
                                      valid_until=time.time() + 1000)
            cell.add_node(server)

        apps = app_list(2, 'app', 50, [6, 6], schedule_once=True)
        for app in apps:
            cell.add_app(cell.partitions[None].allocation, app)

        cell.schedule()

        self.assertNotEquals(apps[0].server, apps[1].server)
        self.assertFalse(apps[0].evicted)
        self.assertFalse(apps[0].evicted)

        cell.children_by_name[apps[0].server].state = sched_utils.State.down
        cell.remove_node_by_name(apps[1].server)

        cell.schedule()
        self.assertIsNone(apps[0].server)
        self.assertTrue(apps[0].evicted)
        self.assertIsNone(apps[1].server)
        self.assertTrue(apps[1].evicted)

    def test_schedule_once_eviction(self):
        """Tests schedule once trait with eviction."""
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        for idx in range(0, 10):
            server = scheduler.Server(str(idx), [10, 10], traits=0,
                                      valid_until=time.time() + 1000)
            cell.add_node(server)

        # Each server has capacity 10.
        #
        # Place two apps - capacity 1, capacity 8, they will occupy entire
        # server.
        #
        # Try and place app with demand of 2. First it will try to evict
        # small app, but it will not be enough, so it will evict large app.
        #
        # Check that evicted flag is set only for large app, and small app
        # will be restored.

        small_apps = app_list(10, 'small', 50, [1, 1], schedule_once=True)
        for app in small_apps:
            cell.add_app(cell.partitions[None].allocation, app)
        large_apps = app_list(10, 'large', 60, [8, 8], schedule_once=True)
        for app in large_apps:
            cell.add_app(cell.partitions[None].allocation, app)

        placement = cell.schedule()
        # Check that all apps are placed.
        app2server = {app: after for app, _, _, after, _ in placement
                      if after is not None}
        self.assertEqual(len(app2server), 20)

        # Add one app, higher priority than rest, will force eviction.
        medium_apps = app_list(1, 'medium', 70, [5, 5])
        for app in medium_apps:
            cell.add_app(cell.partitions[None].allocation, app)

        cell.schedule()
        self.assertEqual(len([app for app in small_apps if app.evicted]), 0)
        self.assertEqual(len([app for app in small_apps if app.server]), 10)

        self.assertEqual(len([app for app in large_apps if app.evicted]), 1)
        self.assertEqual(len([app for app in large_apps if app.server]), 9)

        # Remove app, make sure the evicted app is not placed again.
        cell.remove_app(medium_apps[0].name)
        cell.schedule()

        self.assertEqual(len([app for app in small_apps if app.evicted]), 0)
        self.assertEqual(len([app for app in small_apps if app.server]), 10)

        self.assertEqual(len([app for app in large_apps if app.evicted]), 1)
        self.assertEqual(len([app for app in large_apps if app.server]), 9)

    @mock.patch('time.time', mock.Mock(return_value=100))
    def test_restore(self):
        """Tests app restore."""
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        large_server = scheduler.Server('large', [10, 10], traits=0,
                                        valid_until=200)
        cell.add_node(large_server)

        small_server = scheduler.Server('small', [3, 3], traits=0,
                                        valid_until=1000)
        cell.add_node(small_server)

        apps = app_list(1, 'app', 50, [6, 6], lease=50)
        for app in apps:
            cell.add_app(cell.partitions[None].allocation, app)

        # 100 sec left, app lease is 50, should fit.
        time.time.return_value = 100
        cell.schedule()

        self.assertEqual(apps[0].server, 'large')

        time.time.return_value = 190
        apps_not_fit = app_list(1, 'app-not-fit', 90, [6, 6], lease=50)
        for app in apps_not_fit:
            cell.add_app(cell.partitions[None].allocation, app)

        cell.schedule()
        self.assertIsNone(apps_not_fit[0].server)
        self.assertEqual(apps[0].server, 'large')

    @mock.patch('time.time', mock.Mock(return_value=10))
    def test_renew(self):
        """Tests app renew."""
        cell = scheduler.CellWithK8sScheduler(
            'top', config=self.config_file.name)
        server_a = scheduler.Server('a', [10, 10], traits=0,
                                    valid_until=1000)
        cell.add_node(server_a)

        apps = app_list(1, 'app', 50, [6, 6], lease=50)
        for app in apps:
            cell.add_app(cell.partitions[None].allocation, app)

        cell.schedule()
        self.assertEqual(apps[0].server, 'a')
        self.assertEqual(apps[0].placement_expiry, 60)

        time.time.return_value = 100
        cell.schedule()
        self.assertEqual(apps[0].server, 'a')
        self.assertEqual(apps[0].placement_expiry, 60)

        time.time.return_value = 200
        apps[0].renew = True
        cell.schedule()
        self.assertEqual(apps[0].server, 'a')
        self.assertEqual(apps[0].placement_expiry, 250)
        self.assertFalse(apps[0].renew)

        # fast forward to 975, close to server 'a' expiration, app will
        # migratoe to 'b' on renew.
        server_b = scheduler.Server('b', [10, 10], traits=0,
                                    valid_until=2000)
        cell.add_node(server_b)

        time.time.return_value = 975
        apps[0].renew = True
        cell.schedule()
        self.assertEqual(apps[0].server, 'b')
        self.assertEqual(apps[0].placement_expiry, 1025)
        self.assertFalse(apps[0].renew)

        # fast forward to 1975, when app can't be renewed on server b, but
        # there is not alternative placement.
        time.time.return_value = 1975
        apps[0].renew = True
        cell.schedule()
        self.assertEqual(apps[0].server, 'b')
        # Placement expiry did not change, as placement was not found.
        self.assertEqual(apps[0].placement_expiry, 1025)
        # Renew flag is not cleared, as new placement was not found.
        self.assertTrue(apps[0].renew)


class IdentityGroupTest(unittest.TestCase):
    """scheduler IdentityGroup test."""

    def test_basic(self):
        """Test basic acquire/release ops."""
        ident_group = scheduler.IdentityGroup(3)
        self.assertEqual(0, ident_group.acquire())
        self.assertEqual(1, ident_group.acquire())
        self.assertEqual(2, ident_group.acquire())
        self.assertEqual(None, ident_group.acquire())

        ident_group.release(1)
        self.assertEqual(1, ident_group.acquire())

    def test_adjust(self):
        """Test identity group count adjustement."""
        ident_group = scheduler.IdentityGroup(5)
        ident_group.available = set([1, 3])

        ident_group.adjust(7)
        self.assertEqual(set([1, 3, 5, 6]), ident_group.available)

        ident_group.adjust(3)
        self.assertEqual(set([1]), ident_group.available)


if __name__ == '__main__':
    unittest.main()
