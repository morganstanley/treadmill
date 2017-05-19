"""Performance test for treadmill.scheduler
"""

import timeit
import random
import time

from treadmill import scheduler
from treadmill import utils


def resources(data):
    """Convert resource demand/capacity spec into resource vector."""
    parsers = {
        'memory': utils.megabytes,
        'disk': utils.megabytes,
        'cpu': utils.cpu_units
    }

    return [parsers[k](data.get(k, 0)) for k in ['memory', 'cpu', 'disk']]

# XXX(boysson): Test needs update to new Scheduler API
# XXX:
def test_reschedule(nodes_count, app_count, attempts, affinity):
    """Add high priority apps on top of low priority with full capacity.
    """
    # print('nodes: %s, apps: %s, attempts: %s' % (nodes_count,
    #                                              app_count,
    #                                              attempts))
    scheduler.DIMENSION_COUNT = 3
    cell = scheduler.Cell("local", labels=set([None]))
    for idx in range(0, nodes_count):
        node = scheduler.Server('node' + str(idx), resources({
            "memory": "2G",
            "disk": "20G",
            "cpu": "90%"
        }), time.time() * 2)
        cell.add_node(node)

    for attempt in range(0, attempts):
        for app_idx in range(0, app_count):
            prio = attempt * 5 + random.randint(0, 5)
            demand = resources({
                "memory": "1G",
                "disk": "10G",
                "cpu": "40%"
            })
            name = 'app_%s.%s' % (attempt, app_idx)
            alloc = scheduler.Allocation([10, 10, 10])
            alloc.label = "test"
            app = scheduler.Application(name, prio, demand, affinity=affinity(app_idx))
            cell.add_app(alloc, app)
            cell.partitions[None] = scheduler.Partition()
            cell.partitions[None].allocation = alloc
            cell.schedule()


# XXX(boysson): Test needs update to new Scheduler API
# XXX:
# def test_affinity(nodes_count, app_count, affinity_limit):
#     """Add more apps than nodes count to test affinity limit algo."""
#     print 'node: %s, apps: %s, affinity_limit %s' % (nodes_count,
#                                                      app_count,
#                                                      affinity_limit)
# XXX:
#     cell = scheduler.Cell(3)
#     for idx in xrange(0, nodes_count):
#         node = scheduler.Node('node' + str(idx), [48, 48, 48])
#         cell.add_node(node)
# XXX:
#     alloc = scheduler.Allocation([10, 10, 10])
#     cell.add_allocation('a1', alloc)
#     for app_idx in xrange(0, app_count):
#         name = '1.%s' % (app_idx)
#         alloc.add(scheduler.Application(name, 0, [1, 1, 1],
#                                         affinity_limit=affinity_limit,
#                                         affinity='1'))
#         name = '2.%s' % (app_idx)
#         alloc.add(scheduler.Application(name, 0, [1, 1, 1],
#                                         affinity_limit=affinity_limit,
#                                         affinity='2'))
#         name = '3.%s' % (app_idx)
#         alloc.add(scheduler.Application(name, 0, [1, 1, 1],
#                                         affinity_limit=affinity_limit,
#                                         affinity='3'))
# XXX:
#     sched = scheduler.Scheduler(cell)
#     schedule(sched)


if __name__ == '__main__':
    for i in range(500, 1001):
        if i % 10 ==0:
            print(i, timeit.timeit("test_reschedule(500, %s, 5, affinity=lambda idx: None)" % i,
                                setup="from __main__ import test_reschedule", number=10))
#     test_reschedule(1000, 1000, 3, affinity=str)
#     test_reschedule(1000, 3000, 3, affinity=lambda idx: str(idx % 5))
#     test_affinity(500, 1000, 1)
