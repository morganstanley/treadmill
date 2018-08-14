"""Unit test for treadmill.scheduler.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import bz2
import datetime
import time
import unittest

import mock
import numpy as np
import pandas as pd

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

from treadmill import scheduler
from treadmill import reports


def _construct_cell(empty=False):
    """Constructs a test cell."""
    cell = scheduler.Cell('top')
    if empty:
        return cell

    rack1 = scheduler.Bucket('rack:rack1', traits=0, level='rack')
    rack2 = scheduler.Bucket('rack:rack2', traits=0, level='rack')

    cell.add_node(rack1)
    cell.add_node(rack2)

    srv1 = scheduler.Server('srv1', [10, 20, 30], traits=1,
                            valid_until=1000, label='part')
    srv2 = scheduler.Server('srv2', [10, 20, 30], traits=3,
                            valid_until=2000, label='part')
    srv3 = scheduler.Server('srv3', [10, 20, 30], traits=0,
                            valid_until=3000, label='_default')
    srv4 = scheduler.Server('srv4', [10, 20, 30], traits=0,
                            valid_until=4000, label='_default')
    rack1.add_node(srv1)
    rack1.add_node(srv2)
    rack2.add_node(srv3)
    rack2.add_node(srv4)

    tenant1 = scheduler.Allocation()
    cell.partitions['_default'].allocation.add_sub_alloc('t1', tenant1)
    tenant11 = scheduler.Allocation()
    tenant1.add_sub_alloc('t11', tenant11)
    alloc1 = scheduler.Allocation([10, 10, 10], rank=100, traits=0)
    tenant11.add_sub_alloc('a1', alloc1)

    tenant2 = scheduler.Allocation()
    cell.partitions['part'].allocation.add_sub_alloc('t2', tenant2)
    alloc2 = scheduler.Allocation([10, 10, 10], rank=100, traits=3)
    tenant2.add_sub_alloc('a2', alloc2)

    return cell


class ReportsTest(unittest.TestCase):
    """treadmill.reports tests."""

    def setUp(self):
        scheduler.DIMENSION_COUNT = 3

        self.cell = _construct_cell()
        self.trait_codes = {
            'a': 1,
            'b': 2,
        }
        super(ReportsTest, self).setUp()

    def test_servers(self):
        """Tests servers report."""
        report = reports.servers(self.cell, self.trait_codes)
        pd.util.testing.assert_frame_equal(report, pd.DataFrame([
            ['srv3', 'top/rack:rack2', '_default', '', 'up', 3000,
             10, 20, 30, 10, 20, 30],
            ['srv4', 'top/rack:rack2', '_default', '', 'up', 4000,
             10, 20, 30, 10, 20, 30],
            ['srv1', 'top/rack:rack1', 'part', 'a', 'up', 1000,
             10, 20, 30, 10, 20, 30],
            ['srv2', 'top/rack:rack1', 'part', 'a,b', 'up', 2000,
             10, 20, 30, 10, 20, 30],
        ], columns=[
            'name', 'location', 'partition', 'traits', 'state', 'valid_until',
            'mem', 'cpu', 'disk', 'mem_free', 'cpu_free', 'disk_free'
        ]))

    def test_allocations(self):
        """Tests allocations report."""
        report = reports.allocations(self.cell, self.trait_codes)
        pd.util.testing.assert_frame_equal(report, pd.DataFrame([
            ['_default', 't1/t11/a1', 10, 10, 10, 100, 0, '', np.inf],
            ['part', 't2/a2', 10, 10, 10, 100, 0, 'a,b', np.inf]
        ], columns=[
            'partition', 'name', 'mem', 'cpu', 'disk',
            'rank', 'rank_adj', 'traits', 'max_util'
        ]).sort_values(by=['partition', 'name']))

        # TODO: not implemented.
        # df_traits = reports.allocation_traits(self.cell)

    @mock.patch('time.time', mock.Mock(return_value=100))
    def test_applications(self):
        """Tests application queue report."""
        app1 = scheduler.Application('foo.xxx#1', 100,
                                     demand=[1, 1, 1],
                                     affinity='foo.xxx')
        app1.global_order = 1
        app2 = scheduler.Application('foo.xxx#2', 100,
                                     demand=[1, 1, 1],
                                     affinity='foo.xxx')
        app2.global_order = 2
        app3 = scheduler.Application('bla.xxx#3', 50,
                                     demand=[1, 1, 1],
                                     affinity='bla.xxx')
        app3.global_order = 3

        (self.cell.partitions['_default'].allocation
         .get_sub_alloc('t1')
         .get_sub_alloc('t3')
         .get_sub_alloc('a2').add(app1))

        (self.cell.partitions['_default'].allocation
         .get_sub_alloc('t1')
         .get_sub_alloc('t3')
         .get_sub_alloc('a2').add(app2))

        (self.cell.partitions['part'].allocation
         .get_sub_alloc('t2')
         .get_sub_alloc('a1').add(app3))

        self.cell.schedule()

        apps_df = reports.apps(self.cell, self.trait_codes)
        pd.util.testing.assert_frame_equal(apps_df, pd.DataFrame([
            [
                'bla.xxx#3', 't2/a1', 100, 'bla.xxx', 'part',
                None, -1, 3, 0, 100,
                0, 0, 'srv1', -0.142857142857, -0.128571, 1, 1, 1
            ],
            [
                'foo.xxx#1', 't1/t3/a2', 100, 'foo.xxx', '_default',
                None, -1, 1, 0, 100,
                0, 0, 'srv3', -0.142857142857, -0.128571, 1, 1, 1
            ],
            [
                'foo.xxx#2', 't1/t3/a2', 100, 'foo.xxx', '_default',
                None, -1, 2, 0, 100,
                0, 0, 'srv4', -0.128571428571, -0.114286, 1, 1, 1
            ],
        ], columns=[
            'instance', 'allocation', 'rank', 'affinity', 'partition',
            'identity_group', 'identity', 'order', 'lease', 'expires',
            'data_retention', 'pending', 'server', 'util0', 'util1',
            'mem', 'cpu', 'disk'
        ]).sort_values(by=['partition',
                           'rank',
                           'util0',
                           'util1',
                           'pending',
                           'order']).reset_index(drop=True))

        time.time.return_value = 100
        self.assertEqual(apps_df.ix[2]['cpu'], 1)
        util0 = reports.utilization(None, apps_df)
        time.time.return_value = 101
        util1 = reports.utilization(util0, apps_df)

# name                bla.xxx                           foo.xxx               \
#                       count      util disk cpu memory   count      util disk
# 1969-12-31 19:00:00       1 -0.121429    1   1      1       2 -0.128571    2
# 1969-12-31 19:00:01       1 -0.121429    1   1      1       2 -0.128571    2
#
# name
#                     cpu memory
# 1969-12-31 19:00:00   2      2
# 1969-12-31 19:00:01   2      2

        time0 = pd.Timestamp(datetime.datetime.fromtimestamp(100))
        time1 = pd.Timestamp(datetime.datetime.fromtimestamp(101))
        self.assertEqual(util1.ix[time0]['bla.xxx']['cpu'], 1)
        self.assertEqual(util1.ix[time1]['foo.xxx']['count'], 2)

    def test_empty_cell_reports(self):
        """Tests all reports for an empty cell."""
        empty_cell = _construct_cell(empty=True)

        servers = reports.servers(empty_cell, self.trait_codes)
        empty_servers = pd.DataFrame(columns=[
            'name', 'location', 'partition', 'traits', 'state', 'valid_until',
            'mem', 'cpu', 'disk', 'mem_free', 'cpu_free', 'disk_free'
        ]).astype({
            'mem': 'int',
            'cpu': 'int',
            'disk': 'int',
            'mem_free': 'int',
            'cpu_free': 'int',
            'disk_free': 'int'
        }).reset_index(drop=True)
        pd.util.testing.assert_frame_equal(servers, empty_servers)

        allocations = reports.allocations(empty_cell, self.trait_codes)
        empty_allocations = pd.DataFrame(columns=[
            'partition', 'name', 'mem', 'cpu', 'disk',
            'rank', 'rank_adj', 'traits', 'max_util'
        ]).astype({
            'mem': 'int',
            'cpu': 'int',
            'disk': 'int'
        }).reset_index(drop=True)
        pd.util.testing.assert_frame_equal(allocations, empty_allocations)

        apps = reports.apps(empty_cell, self.trait_codes)
        empty_apps = pd.DataFrame(columns=[
            'instance', 'allocation', 'rank', 'affinity', 'partition',
            'identity_group', 'identity',
            'order', 'lease', 'expires', 'data_retention',
            'pending', 'server', 'util0', 'util1',
            'mem', 'cpu', 'disk'
        ]).astype({
            'mem': 'int',
            'cpu': 'int',
            'disk': 'int',
            'order': 'int',
            'expires': 'int',
            'data_retention': 'int',
            'identity': 'int'
        }).reset_index(drop=True)
        pd.util.testing.assert_frame_equal(apps, empty_apps)

    def test_explain_queue(self):
        """Test explain queue"""
        app1 = scheduler.Application('foo.xxx#1', 100,
                                     demand=[1, 1, 1],
                                     affinity='foo.xxx')
        app2 = scheduler.Application('bar.xxx#2', 100,
                                     demand=[1, 1, 1],
                                     affinity='foo.xxx')
        app3 = scheduler.Application('bla.xxx#3', 50,
                                     demand=[1, 1, 1],
                                     affinity='bla.xxx')

        (self.cell.partitions['_default'].allocation
         .get_sub_alloc('t1')
         .get_sub_alloc('t3')
         .get_sub_alloc('a2').add(app1))

        (self.cell.partitions['_default'].allocation
         .get_sub_alloc('t1')
         .get_sub_alloc('t3')
         .get_sub_alloc('a2').add(app2))

        (self.cell.partitions['part'].allocation
         .get_sub_alloc('t2')
         .get_sub_alloc('a2').add(app3))

        df = reports.explain_queue(self.cell, '_default')
        self.assertEqual(len(df), 2 * 4)  # 2 apps at 4 alloc levels

        df = reports.explain_queue(self.cell, '_default', 'foo*')
        self.assertEqual(len(df), 4)  # 1 app at 4 alloc levels

        df = reports.explain_queue(self.cell, 'part')
        self.assertEqual(len(df), 3)  # 1 app at 3 alloc levels

    def test_explain_placement(self):
        """Test explain placement"""
        app1 = scheduler.Application('foo.xxx#1', 100,
                                     demand=[1, 1, 1],
                                     affinity='foo.xxx')

        alloc = (self.cell.partitions['_default'].allocation
                 .get_sub_alloc('t1')
                 .get_sub_alloc('t3')
                 .get_sub_alloc('a2'))
        self.cell.add_app(alloc, app1)

        df = reports.explain_placement(self.cell, app1, mode='full')
        self.assertEqual(len(df), 7)

        df = reports.explain_placement(self.cell, app1, mode='servers')
        self.assertEqual(len(df), 4)

    def test_serialize_dataframe(self):
        """Test serializing a dataframe."""
        df = pd.DataFrame([
            [1, 2, 3],
            [4, 5, 6]
        ], columns=['a', 'b', 'c'])

        result = reports.serialize_dataframe(df)
        self.assertEqual(
            bz2.decompress(result),
            b'\n'.join(
                [
                    b'a,b,c',
                    b'1,2,3',
                    b'4,5,6',
                    b''
                ]
            )
        )

    def test_deserialize_dataframe_bz2(self):
        """Test deserializing a compressed dataframe."""
        content = bz2.compress(
            b'\n'.join(
                [
                    b'a,b,c',
                    b'1,2,3',
                    b'4,5,6'
                ]
            )
        )

        result = reports.deserialize_dataframe(content)
        pd.util.testing.assert_frame_equal(
            result,
            pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=['a', 'b', 'c'])
        )

    def test_deserialize_dataframe(self):
        """Test deserializing an uncompressed dataframe."""
        content = b'\n'.join(
            [
                b'a,b,c',
                b'1,2,3',
                b'4,5,6'
            ]
        )

        result = reports.deserialize_dataframe(content)
        pd.util.testing.assert_frame_equal(
            result,
            pd.DataFrame([[1, 2, 3], [4, 5, 6]], columns=['a', 'b', 'c'])
        )


if __name__ == '__main__':
    unittest.main()
