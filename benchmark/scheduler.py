"""Performance test for treadmill.scheduler
"""

import timeit
import random

from treadmill import scheduler


def schedule(sched):
    """Helper function to run the scheduler."""

    def _schedule():
        """Run the scheduler, print some stats."""
        new_placement = 0
        evicted = 0
        for event in sched.schedule():
            if event.node:
                new_placement = new_placement + 1
            else:
                evicted = evicted + 1

        print('scheduled: ', new_placement, ', evicted: ', evicted)

    interval = timeit.timeit(stmt=_schedule, number=1)
    print('time  :', interval)


# XXX(boysson): Test needs update to new Scheduler API
# XXX:
def test_reschedule(nodes_count, app_count, attempts, affinity):
    """Add high priority apps on top of low priority with full capacity.
    """
    print('nodes: %s, apps: %s, attempts: %s' % (nodes_count,
                                                 app_count,
                                                 attempts))
    scheduler.DIMENSION_COUNT = 3
    cell = scheduler.Cell(3)
    for idx in range(0, nodes_count):
        node = scheduler.Node('node' + str(idx), 0, 0)
        cell.add_node(node)

    alloc = scheduler.Allocation([10, 10, 10])

    for attempt in range(0, attempts):
        for app_idx in range(0, app_count):
            prio = attempt * 5 + random.randint(0, 5)
            demand = [random.randint(1, 48),
                      random.randint(1, 48),
                      random.randint(1, 48)]
            name = 'app_%s.%s' % (attempt, app_idx)
            cell.add_app(alloc, scheduler.Application(name, prio,
                                                      demand, affinity=affinity(app_idx)))

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
    print(timeit.timeit("test_reschedule(500, 1000, 5, affinity=lambda idx: None)",
                        setup="from __main__ import test_reschedule", number=250))
#     test_reschedule(1000, 1000, 3, affinity=str)
#     test_reschedule(1000, 3000, 3, affinity=lambda idx: str(idx % 5))
#     test_affinity(500, 1000, 1)
