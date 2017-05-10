"""Unit test for treadmill.scheduler
"""

import datetime
import time
import unittest

import mock
import pandas as pd

from treadmill import scheduler
from treadmill import reports


def _construct_cell():
    """Constructs a test cell."""
    cell = scheduler.Cell('top')
    rack1 = scheduler.Bucket('rack:rack1', traits=0, level='rack')
    rack2 = scheduler.Bucket('rack:rack2', traits=0, level='rack')

    cell.add_node(rack1)
    cell.add_node(rack2)

    srv1 = scheduler.Server('srv1', [10, 20, 30], traits=3,
                            valid_until=1000)
    srv2 = scheduler.Server('srv2', [10, 20, 30], traits=7,
                            valid_until=2000)
    srv3 = scheduler.Server('srv3', [10, 20, 30], traits=0,
                            valid_until=3000)
    srv4 = scheduler.Server('srv4', [10, 20, 30], traits=0,
                            valid_until=4000)

    rack1.add_node(srv1)
    rack1.add_node(srv2)
    rack2.add_node(srv3)
    rack2.add_node(srv4)

    tenant1 = scheduler.Allocation()
    tenant2 = scheduler.Allocation()
    tenant3 = scheduler.Allocation()
    alloc1 = scheduler.Allocation([10, 10, 10], rank=100, traits=0)
    alloc2 = scheduler.Allocation([10, 10, 10], rank=100, traits=3)

    cell.partitions[None].allocation.add_sub_alloc('t1', tenant1)
    cell.partitions[None].allocation.add_sub_alloc('t2', tenant2)
    tenant1.add_sub_alloc('t3', tenant3)
    tenant2.add_sub_alloc('a1', alloc1)
    tenant3.add_sub_alloc('a2', alloc2)

    return cell


class ReportsTest(unittest.TestCase):
    """treadmill.reports tests."""

    def setUp(self):
        scheduler.DIMENSION_COUNT = 3

        self.cell = _construct_cell()
        super(ReportsTest, self).setUp()

    def test_servers(self):
        """Tests servers report."""
        df = reports.servers(self.cell)
        # print df
        # Sample data frame to see that the values are correct.
        self.assertEqual(df.ix['srv1']['memory'], 10)
        self.assertEqual(df.ix['srv2']['rack'], 'rack:rack1')

        # check valid until
        # XXX(boysson): There is a timezone bug here.
        # XXX(boysson): self.assertEqual(str(df.ix['srv1']['valid_until']),
        # XXX(boysson):                   '1969-12-31 19:16:40')
        # XXX(boysson): self.assertEqual(str(df.ix['srv4']['valid_until']),
        # XXX(boysson):                   '1969-12-31 20:06:40')

    def test_allocations(self):
        """Tests allocations report."""
        df = reports.allocations(self.cell)
        # print df
        #           cpu  disk  max_utilization  memory  rank
        # name
        # t2/a1      10    10              inf      10   100
        # t1/t3/a2   10    10              inf      10   100
        self.assertEqual(df.ix['-', 't2/a1']['cpu'], 10)
        self.assertEqual(df.ix['-', 't1/t3/a2']['cpu'], 10)

        # TODO: not implemented.
        # df_traits = reports.allocation_traits(self.cell)

    @mock.patch('time.time', mock.Mock(return_value=100))
    def test_applications(self):
        """Tests application queue report."""
        app1 = scheduler.Application('foo.xxx#1', 100,
                                     demand=[1, 1, 1],
                                     affinity='foo.xxx')
        app2 = scheduler.Application('foo.xxx#2', 100,
                                     demand=[1, 1, 1],
                                     affinity='foo.xxx')
        app3 = scheduler.Application('bla.xxx#3', 50,
                                     demand=[1, 1, 1],
                                     affinity='bla.xxx')

        (self.cell.partitions[None].allocation
         .get_sub_alloc('t1')
         .get_sub_alloc('t3')
         .get_sub_alloc('a2').add(app1))

        (self.cell.partitions[None].allocation
         .get_sub_alloc('t1')
         .get_sub_alloc('t3')
         .get_sub_alloc('a2').add(app2))

        (self.cell.partitions[None].allocation
         .get_sub_alloc('t2')
         .get_sub_alloc('a1').add(app3))

        self.cell.schedule()

        apps_df = reports.apps(self.cell)
        # print apps_df
#           affinity allocation  cpu  data_retention_timeout  disk  memory  \
# instance
# foo.xxx#1  foo.xxx   t1/t3/a2    1                       0     1       1
# foo.xxx#2  foo.xxx   t1/t3/a2    1                       0     1       1
# bla.xxx#3  bla.xxx      t2/a1    1                       0     1       1
#
#                   order  pending  rank server      util
# instance
# foo.xxx#1  1.458152e+15        0    99   srv1 -0.135714
# foo.xxx#2  1.458152e+15        0    99   srv1 -0.128571
# bla.xxx#3  1.458152e+15        0   100   srv1 -0.121429

        time.time.return_value = 100
        self.assertEqual(apps_df.ix['foo.xxx#2']['cpu'], 1)
        util0 = reports.utilization(None, apps_df)
        time.time.return_value = 101
        util1 = reports.utilization(util0, apps_df)

        # print util1

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


if __name__ == '__main__':
    unittest.main()
