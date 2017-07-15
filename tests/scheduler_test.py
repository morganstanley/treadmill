"""Unit test for treadmill.scheduler
"""

import time
import unittest
import sys

# Disable too many lines in module warning.
#
# pylint: disable=C0302

import mock
import numpy as np

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


class AllocationTest(unittest.TestCase):
    """treadmill.scheduler.Allocation tests."""

    def setUp(self):
        scheduler.DIMENSION_COUNT = 2
        super(AllocationTest, self).setUp()

    def test_utilization(self):
        """Test utilization calculation."""
        alloc = scheduler.Allocation([10, 10])

        alloc.add(scheduler.Application('app1', 100, [1, 1], 'app1'))
        alloc.add(scheduler.Application('app2', 100, [2, 2], 'app1'))
        alloc.add(scheduler.Application('app3', 100, [3, 3], 'app1'))

        # First element is rank.
        util_q = list(alloc.utilization_queue([20, 20]))
        self.assertEqual(100, util_q[0][0])
        self.assertEqual(100, util_q[1][0])
        self.assertEqual(100, util_q[2][0])

        # Second elememt is utilization.
        self.assertEqual(-9. / (10. + 20), util_q[0][1])
        self.assertEqual(-7. / (10. + 20), util_q[1][1])
        self.assertEqual(-4. / (10. + 20), util_q[2][1])

        # Applications are sorted by priority.
        alloc = scheduler.Allocation([10, 10])
        alloc.add(scheduler.Application('app1', 10, [1, 1], 'app1'))
        alloc.add(scheduler.Application('app2', 50, [2, 2], 'app1'))
        alloc.add(scheduler.Application('app3', 100, [3, 3], 'app1'))

        util_q = list(alloc.utilization_queue([20., 20.]))
        self.assertEqual(-7. / (10. + 20), util_q[0][1])
        self.assertEqual(-5. / (10. + 20), util_q[1][1])
        self.assertEqual(-4. / (10. + 20), util_q[2][1])

    def test_running_order(self):
        """Test apps are ordered by status (running first) for same prio."""
        alloc = scheduler.Allocation([10, 10])

        alloc.add(scheduler.Application('app1', 5, [1, 1], 'app1'))
        alloc.add(scheduler.Application('app2', 5, [2, 2], 'app1'))
        alloc.add(scheduler.Application('app3', 5, [3, 3], 'app1'))

        queue = list(alloc.utilization_queue([20., 20.]))
        self.assertEqual(alloc.apps['app1'], queue[0][-1])

        alloc.apps['app2'].server = 'abc'
        queue = list(alloc.utilization_queue([20., 20.]))
        self.assertEqual(alloc.apps['app2'], queue[0][-1])

    def test_utilization_max(self):
        """Tests max utilization cap on the allocation."""
        alloc = scheduler.Allocation([3, 3])

        alloc.add(scheduler.Application('app1', 1, [1, 1], 'app1'))
        alloc.add(scheduler.Application('app2', 1, [2, 2], 'app1'))
        alloc.add(scheduler.Application('app3', 1, [3, 3], 'app1'))

        self.assertEqual(3, len(list(alloc.utilization_queue([20., 20.]))))

        # Now set max_utilization to 1
        alloc.max_utilization = 1
        # XXX(boysson: Broken test. Needs upgrade to V3
        # XXX:
        # XXX: self.assertEqual(
        # XXX:     2,
        # XXX:     len(list(alloc.utilization_queue([20., 20.])))
        # XXX: )

        alloc.set_max_utilization(None)
        self.assertEqual(3, len(list(alloc.utilization_queue([20., 20.]))))

    def test_priority_zero(self):
        """Tests priority zero apps."""
        alloc = scheduler.Allocation([3, 3])

        alloc.add(scheduler.Application('app1', 1, [1, 1], 'app1'))
        alloc.add(scheduler.Application('app2', 0, [2, 2], 'app1'))

        # default max_utilization still lets prio 0 apps through
        queue = alloc.utilization_queue([20., 20.])
        self.assertEqual([100, 100], [item[0] for item in queue])

        alloc.set_max_utilization(100)
        # setting max_utilization will cut off prio 0 apps
        queue = alloc.utilization_queue([20., 20.])
        self.assertEqual([100, sys.maxsize], [item[0] for item in queue])

    def test_rank_adjustment(self):
        """Test rank adjustment"""
        alloc = scheduler.Allocation([3, 3])

        alloc.rank = 100
        alloc.rank_adjustment = 10
        alloc.add(scheduler.Application('app1', 1, [1, 1], 'app1'))
        alloc.add(scheduler.Application('app2', 1, [2, 2], 'app1'))
        alloc.add(scheduler.Application('app3', 1, [3, 3], 'app1'))

        queue = list(alloc.utilization_queue([20., 20.]))
        self.assertEqual(90, queue[0][0])
        self.assertEqual(90, queue[1][0])
        self.assertEqual(100, queue[2][0])

    def test_zerovector(self):
        """Test updating allocation with allocation vector containing 0's"""
        alloc = scheduler.Allocation(None)

        alloc.update([1, 0], None)
        self.assertEqual(1.0, alloc.reserved[0])
        self.assertEqual(0, alloc.reserved[1])

    def test_utilization_no_reservation(self):
        """Checks that any utilization without reservation is VERY large."""
        alloc = scheduler.Allocation(None)
        alloc.add(scheduler.Application('app1', 1, [1., 1.], 'app1'))
        queue = list(alloc.utilization_queue(np.array([10., 10.])))
        self.assertEqual(1. / (10), queue[0][1])

    def test_duplicate(self):
        """Checks behavior when adding duplicate app."""
        alloc = scheduler.Allocation(None)
        alloc.add(scheduler.Application('app1', 0, [1, 1], 'app1'))
        self.assertEqual(
            1, len(list(alloc.utilization_queue(np.array([5., 5.])))))
        alloc.add(scheduler.Application('app1', 0, [1, 1], 'app1'))
        self.assertEqual(
            1, len(list(alloc.utilization_queue(np.array([5., 5.])))))

    def test_sub_allocs(self):
        """Test utilization calculation with sub-allocs."""
        alloc = scheduler.Allocation([3, 3])
        self.assertEqual(3, alloc.total_reserved()[0])

        queue = list(alloc.utilization_queue([20., 20.]))

        sub_alloc_a = scheduler.Allocation([5, 5])
        alloc.add_sub_alloc('a1/a', sub_alloc_a)
        self.assertEqual(8, alloc.total_reserved()[0])
        sub_alloc_a.add(scheduler.Application('1a', 3, [2, 2], 'app1'))
        sub_alloc_a.add(scheduler.Application('2a', 2, [3, 3], 'app1'))
        sub_alloc_a.add(scheduler.Application('3a', 1, [5, 5], 'app1'))

        queue = list(alloc.utilization_queue([20., 20.]))
        _rank, util, _pending, _order, app = queue[0]
        self.assertEqual('1a', app.name)
        self.assertEqual((2 - (5 + 3)) / (20. + (5 + 3)), util)

        sub_alloc_b = scheduler.Allocation([10, 10])
        alloc.add_sub_alloc('a1/b', sub_alloc_b)
        sub_alloc_b.add(scheduler.Application('1b', 3, [2, 2], 'app1'))
        sub_alloc_b.add(scheduler.Application('2b', 2, [3, 3], 'app1'))
        sub_alloc_b.add(scheduler.Application('3b', 1, [5, 5], 'app1'))

        queue = list(alloc.utilization_queue([20., 20.]))

        self.assertEqual(6, len(queue))
        self.assertEqual(18, alloc.total_reserved()[0])

        # For each sub-alloc (and self) the least utilized app is 1.
        # The sub_allloc_b is largest, so utilization smallest, 1b will be
        # first.
        _rank, util, _pending, _order, app = queue[0]
        self.assertEqual('1b', app.name)
        self.assertEqual((2. - 18) / (20. + 18), util)

        # Add prio 0 app to each, make sure they all end up last.
        alloc.add(scheduler.Application('1-zero', 0, [2, 2], 'app1'))
        sub_alloc_b.add(scheduler.Application('b-zero', 0, [5, 5], 'app1'))
        sub_alloc_a.add(scheduler.Application('a-zero', 0, [5, 5], 'app1'))

        queue = list(alloc.utilization_queue([20., 20.]))
        self.assertIn('1-zero', [item[-1].name for item in queue[-3:]])
        self.assertIn('a-zero', [item[-1].name for item in queue[-3:]])
        self.assertIn('b-zero', [item[-1].name for item in queue[-3:]])

        # Check that utilization of prio 0 apps is always max float.
        self.assertEqual(
            [float('inf')] * 3,
            [
                util
                for (_rank,
                     util,
                     _pending,
                     _order,
                     _app) in queue[-3:]  # noqa: F812,E501
            ]
        )

    def test_sub_alloc_reservation(self):
        """Test utilization calculation is fair between sub-allocs."""
        alloc = scheduler.Allocation()

        sub_alloc_poor = scheduler.Allocation()
        alloc.add_sub_alloc('poor', sub_alloc_poor)
        sub_alloc_poor.add(scheduler.Application('p1', 1, [1, 1], 'app1'))

        sub_alloc_rich = scheduler.Allocation([5, 5])
        sub_alloc_rich.add(scheduler.Application('r1', 1, [5, 5], 'app1'))
        sub_alloc_rich.add(scheduler.Application('r2', 1, [5, 5], 'app1'))
        alloc.add_sub_alloc('rich', sub_alloc_rich)

        queue = list(alloc.utilization_queue([20., 20.]))

        self.assertEqual('r1', queue[0][-1].name)
        self.assertEqual('p1', queue[1][-1].name)
        self.assertEqual('r2', queue[2][-1].name)


class TraitSetTest(unittest.TestCase):
    """treadmill.scheduler.TraitSet tests."""

    def setUp(self):
        scheduler.DIMENSION_COUNT = 2
        super(TraitSetTest, self).setUp()

    def test_traits(self):
        """Test trait inheritance."""
        trait_a = int('0b0000001', 2)

        trait_x = int('0b0000100', 2)
        trait_y = int('0b0001000', 2)
        trait_z = int('0b0010000', 2)

        fset_a = scheduler.TraitSet(trait_a)

        fset_xz = scheduler.TraitSet(trait_x | trait_z)
        fset_xy = scheduler.TraitSet(trait_x | trait_y)

        self.assertTrue(fset_a.has(trait_a))

        fset_a.add('xy', fset_xy.traits)
        self.assertTrue(fset_a.has(trait_a))
        self.assertTrue(fset_a.has(trait_x))
        self.assertTrue(fset_a.has(trait_y))

        fset_a.add('xz', fset_xz.traits)
        self.assertTrue(fset_a.has(trait_x))
        self.assertTrue(fset_a.has(trait_y))
        self.assertTrue(fset_a.has(trait_z))

        fset_a.remove('xy')
        self.assertTrue(fset_a.has(trait_x))
        self.assertFalse(fset_a.has(trait_y))
        self.assertTrue(fset_a.has(trait_z))

        fset_a.remove('xz')
        self.assertFalse(fset_a.has(trait_x))
        self.assertFalse(fset_a.has(trait_y))
        self.assertFalse(fset_a.has(trait_z))


class NodeTest(unittest.TestCase):
    """treadmill.scheduler.Allocation tests."""

    def setUp(self):
        scheduler.DIMENSION_COUNT = 2
        super(NodeTest, self).setUp()

    def test_bucket_capacity(self):
        """Tests adjustment of bucket capacity up and down."""
        parent = scheduler.Bucket('top')

        bucket = scheduler.Bucket('b')
        parent.add_node(bucket)

        srv1 = scheduler.Server('n1', [10, 5], valid_until=500)
        bucket.add_node(srv1)
        self.assertTrue(np.array_equal(bucket.free_capacity,
                                       np.array([10., 5.])))
        self.assertTrue(np.array_equal(parent.free_capacity,
                                       np.array([10., 5.])))

        srv2 = scheduler.Server('n2', [5, 10], valid_until=500)
        bucket.add_node(srv2)
        self.assertTrue(np.array_equal(bucket.free_capacity,
                                       np.array([10., 10.])))
        self.assertTrue(np.array_equal(parent.free_capacity,
                                       np.array([10., 10.])))

        srv3 = scheduler.Server('n3', [3, 3], valid_until=500)
        bucket.add_node(srv3)
        self.assertTrue(np.array_equal(bucket.free_capacity,
                                       np.array([10., 10.])))
        self.assertTrue(np.array_equal(parent.free_capacity,
                                       np.array([10., 10.])))

        bucket.remove_node_by_name('n3')
        self.assertTrue(np.array_equal(bucket.free_capacity,
                                       np.array([10., 10.])))
        self.assertTrue(np.array_equal(parent.free_capacity,
                                       np.array([10., 10.])))

        bucket.remove_node_by_name('n1')
        self.assertTrue(np.array_equal(bucket.free_capacity,
                                       np.array([5., 10.])))
        self.assertTrue(np.array_equal(parent.free_capacity,
                                       np.array([5., 10.])))

    def test_app_node_placement(self):
        """Tests capacity adjustments for app placement."""
        parent = scheduler.Bucket('top')

        bucket = scheduler.Bucket('a_bucket')
        parent.add_node(bucket)

        srv1 = scheduler.Server('n1', [10, 5], valid_until=500)
        bucket.add_node(srv1)

        srv2 = scheduler.Server('n2', [10, 5], valid_until=500)
        bucket.add_node(srv2)

        self.assertTrue(np.array_equal(bucket.free_capacity,
                                       np.array([10., 5.])))
        self.assertTrue(np.array_equal(parent.free_capacity,
                                       np.array([10., 5.])))

        self.assertTrue(np.array_equal(bucket.size(None),
                                       np.array([20., 10.])))

        # Create 10 identical apps.
        apps = app_list(10, 'app', 50, [1, 2])

        self.assertTrue(srv1.put(apps[0]))

        # Capacity of buckets should not change, other node is intact.
        self.assertTrue(np.array_equal(bucket.free_capacity,
                                       np.array([10., 5.])))
        self.assertTrue(np.array_equal(parent.free_capacity,
                                       np.array([10., 5.])))

        self.assertTrue(srv1.put(apps[1]))
        self.assertTrue(srv2.put(apps[2]))

        self.assertTrue(np.array_equal(bucket.free_capacity,
                                       np.array([9., 3.])))
        self.assertTrue(np.array_equal(parent.free_capacity,
                                       np.array([9., 3.])))

    def test_bucket_placement(self):
        """Tests placement strategies."""
        top = scheduler.Bucket('top')

        a_bucket = scheduler.Bucket('a_bucket')
        top.add_node(a_bucket)

        b_bucket = scheduler.Bucket('b_bucket')
        top.add_node(b_bucket)

        a1_srv = scheduler.Server('a1_srv', [10, 10], valid_until=500)
        a_bucket.add_node(a1_srv)
        a2_srv = scheduler.Server('a2_srv', [10, 10], valid_until=500)
        a_bucket.add_node(a2_srv)

        b1_srv = scheduler.Server('b1_srv', [10, 10], valid_until=500)
        b_bucket.add_node(b1_srv)
        b2_srv = scheduler.Server('b2_srv', [10, 10], valid_until=500)
        b_bucket.add_node(b2_srv)

        # bunch of apps with the same affinity
        apps1 = app_list(10, 'app1', 50, [1, 1])
        apps2 = app_list(10, 'app2', 50, [1, 1])

        # Default strategy is spread, so placing 4 apps1 will result in each
        # node having one app.
        self.assertTrue(top.put(apps1[0]))
        self.assertTrue(top.put(apps1[1]))
        self.assertTrue(top.put(apps1[2]))
        self.assertTrue(top.put(apps1[3]))

        # from top level, it will spread between a and b buckets, so first
        # two apps go to a1_srv, b1_srv respectively.
        #
        # 3rd app - buckets rotate, and a bucket is preferred again. Inside the
        # bucket, next node is chosed. Same for 4th app.
        #
        # Result is the after 4 placements they are spread evenly.
        #
        self.assertEqual(1, len(a1_srv.apps))
        self.assertEqual(1, len(a2_srv.apps))
        self.assertEqual(1, len(b1_srv.apps))
        self.assertEqual(1, len(b2_srv.apps))

        a_bucket.set_affinity_strategy('app2', scheduler.PackStrategy)

        self.assertTrue(top.put(apps2[0]))
        self.assertTrue(top.put(apps2[1]))
        self.assertTrue(top.put(apps2[2]))
        self.assertTrue(top.put(apps2[3]))

        # B bucket still uses spread strategy.
        self.assertEqual(2, len(b1_srv.apps))
        self.assertEqual(2, len(b2_srv.apps))

        # Without predicting exact placement, apps will be placed on one of
        # the servers in A bucket but not the other, as they use pack strateg.
        self.assertNotEquals(len(a1_srv.apps), len(a2_srv.apps))

    def test_valid_times(self):
        """Tests node valid_until calculation."""
        top = scheduler.Bucket('top', traits=_traits2int(['top']))
        left = scheduler.Bucket('left', traits=_traits2int(['left']))
        right = scheduler.Bucket('right', traits=_traits2int(['right']))
        srv_a = scheduler.Server('a', [10, 10], traits=_traits2int(['a', '0']),
                                 valid_until=1)
        srv_b = scheduler.Server('b', [10, 10], traits=_traits2int(['b', '0']),
                                 valid_until=2)
        srv_y = scheduler.Server('y', [10, 10], traits=_traits2int(['y', '1']),
                                 valid_until=3)
        srv_z = scheduler.Server('z', [10, 10], traits=_traits2int(['z', '1']),
                                 valid_until=4)

        top.add_node(left)
        top.add_node(right)
        left.add_node(srv_a)
        left.add_node(srv_b)
        right.add_node(srv_y)
        right.add_node(srv_z)

        self.assertEqual(top.valid_until, 4)
        self.assertEqual(left.valid_until, 2)
        self.assertEqual(right.valid_until, 4)

        left.remove_node_by_name('a')
        self.assertEqual(top.valid_until, 4)
        self.assertEqual(left.valid_until, 2)
        self.assertEqual(right.valid_until, 4)

        right.remove_node_by_name('z')
        self.assertEqual(top.valid_until, 3)
        self.assertEqual(left.valid_until, 2)
        self.assertEqual(right.valid_until, 3)

    def test_node_traits(self):
        """Tests node trait inheritance."""
        top = scheduler.Bucket('top', traits=_traits2int(['top']))
        left = scheduler.Bucket('left', traits=_traits2int(['left']))
        right = scheduler.Bucket('right', traits=_traits2int(['right']))
        srv_a = scheduler.Server('a', [10, 10], traits=_traits2int(['a', '0']),
                                 valid_until=500)
        srv_b = scheduler.Server('b', [10, 10], traits=_traits2int(['b', '0']),
                                 valid_until=500)
        srv_y = scheduler.Server('y', [10, 10], traits=_traits2int(['y', '1']),
                                 valid_until=500)
        srv_z = scheduler.Server('z', [10, 10], traits=_traits2int(['z', '1']),
                                 valid_until=500)

        top.add_node(left)
        top.add_node(right)
        left.add_node(srv_a)
        left.add_node(srv_b)
        right.add_node(srv_y)
        right.add_node(srv_z)

        self.assertTrue(top.traits.has(_trait2int('a')))
        self.assertTrue(top.traits.has(_trait2int('b')))
        self.assertTrue(top.traits.has(_trait2int('0')))
        self.assertTrue(top.traits.has(_trait2int('y')))
        self.assertTrue(top.traits.has(_trait2int('z')))
        self.assertTrue(top.traits.has(_trait2int('1')))

        self.assertTrue(left.traits.has(_trait2int('a')))
        self.assertTrue(left.traits.has(_trait2int('b')))
        self.assertTrue(left.traits.has(_trait2int('0')))
        self.assertFalse(left.traits.has(_trait2int('y')))
        self.assertFalse(left.traits.has(_trait2int('z')))
        self.assertFalse(left.traits.has(_trait2int('1')))

        left.remove_node_by_name('a')
        self.assertFalse(left.traits.has(_trait2int('a')))
        self.assertTrue(left.traits.has(_trait2int('b')))
        self.assertTrue(left.traits.has(_trait2int('0')))

        self.assertFalse(top.traits.has(_trait2int('a')))
        self.assertTrue(top.traits.has(_trait2int('b')))
        self.assertTrue(top.traits.has(_trait2int('0')))

        left.remove_node_by_name('b')
        self.assertFalse(left.traits.has(_trait2int('b')))
        self.assertFalse(left.traits.has(_trait2int('0')))

        self.assertFalse(top.traits.has(_trait2int('b')))
        self.assertFalse(top.traits.has(_trait2int('0')))

    def test_app_trait_placement(self):
        """Tests placement of app with traits."""
        top = scheduler.Bucket('top', traits=_traits2int(['top']))
        left = scheduler.Bucket('left', traits=_traits2int(['left']))
        right = scheduler.Bucket('right', traits=_traits2int(['right']))
        srv_a = scheduler.Server('a', [10, 10], traits=_traits2int(['a', '0']),
                                 valid_until=500)
        srv_b = scheduler.Server('b', [10, 10], traits=_traits2int(['b', '0']),
                                 valid_until=500)
        srv_y = scheduler.Server('y', [10, 10], traits=_traits2int(['y', '1']),
                                 valid_until=500)
        srv_z = scheduler.Server('z', [10, 10], traits=_traits2int(['z', '1']),
                                 valid_until=500)

        top.add_node(left)
        top.add_node(right)
        left.add_node(srv_a)
        left.add_node(srv_b)
        right.add_node(srv_y)
        right.add_node(srv_z)

        alloc_a = scheduler.Allocation(traits=_traits2int(['a']))
        apps_a = app_list(10, 'app_a', 50, [2, 2])
        for app in apps_a:
            alloc_a.add(app)

        # srv_a is the only one with trait  'a'.
        self.assertTrue(top.put(apps_a[0]))
        self.assertTrue(top.put(apps_a[1]))
        self.assertIn(apps_a[0].name, srv_a.apps)
        self.assertIn(apps_a[1].name, srv_a.apps)

        alloc_0 = scheduler.Allocation(traits=_traits2int(['0']))
        apps_0 = app_list(10, 'app_0', 50, [2, 2])
        for app in apps_0:
            alloc_0.add(app)

        # '0' trait - two servers, will spread by default.
        self.assertTrue(top.put(apps_0[0]))
        self.assertTrue(top.put(apps_0[1]))
        self.assertIn(apps_0[0].name, srv_a.apps)
        self.assertIn(apps_0[1].name, srv_b.apps)

        # Prev implementation propagated traits from parent to children,
        # so "right" trait propagated to leaf servers.
        #
        # This behavior is removed, so placing app with "right" trait will
        # fail.
        #
        # alloc_r1 = scheduler.Allocation(traits=_traits2int(['right', '1']))
        # apps_r1 = app_list(10, 'app_r1', 50, [2, 2])
        # for app in apps_r1:
        #    alloc_r1.add(app)

        # self.assertTrue(top.put(apps_r1[0]))
        # self.assertTrue(top.put(apps_r1[1]))
        # self.assertIn(apps_r1[0].name, srv_y.apps)
        # self.assertIn(apps_r1[1].name, srv_z.apps)

        apps_nothing = app_list(10, 'apps_nothing', 50, [1, 1])

        # All nodes fit. Spead first between buckets, then between nodes.
        #                  top
        #         left             right
        #       a      b         y       z
        self.assertTrue(top.put(apps_nothing[0]))
        self.assertTrue(top.put(apps_nothing[1]))

        self.assertTrue(
            (apps_nothing[0].server in ['a', 'b'] and
             apps_nothing[1].server in ['y', 'z']) or

            (apps_nothing[0].server in ['y', 'z'] and
             apps_nothing[1].server in ['a', 'b']))

        self.assertTrue(top.put(apps_nothing[2]))
        self.assertTrue(top.put(apps_nothing[3]))

        self.assertTrue(
            (apps_nothing[2].server in ['a', 'b'] and
             apps_nothing[3].server in ['y', 'z']) or

            (apps_nothing[2].server in ['y', 'z'] and
             apps_nothing[3].server in ['a', 'b']))

    def test_size_and_members(self):
        """Tests recursive size calculation."""
        top = scheduler.Bucket('top', traits=_traits2int(['top']))
        left = scheduler.Bucket('left', traits=_traits2int(['left']))
        right = scheduler.Bucket('right', traits=_traits2int(['right']))
        srv_a = scheduler.Server('a', [1, 1], traits=_traits2int(['a', '0']),
                                 valid_until=500)
        srv_b = scheduler.Server('b', [1, 1], traits=_traits2int(['b', '0']),
                                 valid_until=500)
        srv_y = scheduler.Server('y', [1, 1], traits=_traits2int(['y', '1']),
                                 valid_until=500)
        srv_z = scheduler.Server('z', [1, 1], traits=_traits2int(['z', '1']),
                                 valid_until=500)

        top.add_node(left)
        top.add_node(right)
        left.add_node(srv_a)
        left.add_node(srv_b)
        right.add_node(srv_y)
        right.add_node(srv_z)

        # pylint: disable=W0212
        self.assertTrue(scheduler._all_isclose(srv_a.size(None), [1, 1]))
        self.assertTrue(scheduler._all_isclose(left.size(None), [2, 2]))
        self.assertTrue(scheduler._all_isclose(top.size(None), [4, 4]))

        self.assertEqual(
            {
                'a': srv_a,
                'b': srv_b,
                'y': srv_y,
                'z': srv_z
            },
            top.members()
        )

    def test_affinity_counters(self):
        """Tests affinity counters."""
        top = scheduler.Bucket('top', traits=_traits2int(['top']))
        left = scheduler.Bucket('left', traits=_traits2int(['left']))
        right = scheduler.Bucket('right', traits=_traits2int(['right']))
        srv_a = scheduler.Server('a', [10, 10], traits=0, valid_until=500)
        srv_b = scheduler.Server('b', [10, 10], traits=0, valid_until=500)
        srv_y = scheduler.Server('y', [10, 10], traits=0, valid_until=500)
        srv_z = scheduler.Server('z', [10, 10], traits=0, valid_until=500)

        top.add_node(left)
        top.add_node(right)
        left.add_node(srv_a)
        left.add_node(srv_b)
        right.add_node(srv_y)
        right.add_node(srv_z)

        apps_a = app_list(10, 'app_a', 50, [1, 1])

        self.assertTrue(srv_a.put(apps_a[0]))
        self.assertEqual(1, srv_a.affinity_counters['app_a'])
        self.assertEqual(1, left.affinity_counters['app_a'])
        self.assertEqual(1, top.affinity_counters['app_a'])

        srv_z.put(apps_a[0])
        self.assertEqual(1, srv_z.affinity_counters['app_a'])
        self.assertEqual(1, left.affinity_counters['app_a'])
        self.assertEqual(2, top.affinity_counters['app_a'])

        srv_a.remove(apps_a[0].name)
        self.assertEqual(0, srv_a.affinity_counters['app_a'])
        self.assertEqual(0, left.affinity_counters['app_a'])
        self.assertEqual(1, top.affinity_counters['app_a'])


class CellTest(unittest.TestCase):
    """treadmill.scheduler.Cell tests."""

    def setUp(self):
        scheduler.DIMENSION_COUNT = 2
        super(CellTest, self).setUp()

    def test_emtpy(self):
        """Simple test to test empty bucket"""
        cell = scheduler.Cell('top')

        empty = scheduler.Bucket('empty', traits=0)
        cell.add_node(empty)

        bucket = scheduler.Bucket('bucket', traits=0)
        srv_a = scheduler.Server('a', [10, 10], traits=0, valid_until=500)
        bucket.add_node(srv_a)

        cell.add_node(bucket)

        cell.schedule()

    def test_labels(self):
        """Test scheduling with labels."""
        cell = scheduler.Cell('top')
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
        cell = scheduler.Cell('top')
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
        cell = scheduler.Cell('top')
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
        cell = scheduler.Cell('top')
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
        cell = scheduler.Cell('top')
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

        # Both apps having different affinity, will be on same node.
        first_srv = sticky_apps[0].server
        self.assertEqual(sticky_apps[0].server, unsticky_app.server)

        # Mark srv_a as down, unsticky app migrates right away,
        # sticky stays.
        srvs[first_srv].state = scheduler.State.down

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
        srvs[first_srv].state = scheduler.State.up
        srvs[second_srv].state = scheduler.State.down

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

        srvs[second_srv].state = scheduler.State.up
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
        cell = scheduler.Cell('top')
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
        cell = scheduler.Cell('top')
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
        cell = scheduler.Cell('top')
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

        cell.children_by_name[apps[0].server].state = scheduler.State.down
        cell.remove_node_by_name(apps[1].server)

        cell.schedule()
        self.assertIsNone(apps[0].server)
        self.assertTrue(apps[0].evicted)
        self.assertIsNone(apps[1].server)
        self.assertTrue(apps[1].evicted)

    def test_schedule_once_eviction(self):
        """Tests schedule once trait with eviction."""
        cell = scheduler.Cell('top')
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
        cell = scheduler.Cell('top')
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
        cell = scheduler.Cell('top')
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
