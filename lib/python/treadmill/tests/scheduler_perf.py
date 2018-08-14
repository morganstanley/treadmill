"""Performance test for treadmill.scheduler.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import timeit

# Disable W0611: Unused import
import treadmill.tests.treadmill_test_skip_windows  # pylint: disable=W0611

# XXX: Test needs update to new Scheduler API
# XXX: from treadmill import scheduler


def schedule(sched):
    """Helper function to run the scheduler."""

    def _schedule():
        """Run the scheduler, output some stats."""
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


# XXX: Test needs update to new Scheduler API
# XXX:
# XXX: def test_reschedule(nodes_count, app_count, attempts, affinity):
# XXX:     """Add high priority apps on top of low priority with full capacity.
# XXX:     """
# XXX:     print('nodes: %s, apps: %s, attempts: %s' % (nodes_count,
# XXX:                                                  app_count,
# XXX:                                                  attempts))
# XXX:     cell = scheduler.Cell(3)
# XXX:     for idx in range(0, nodes_count):
# XXX:         node = scheduler.Node('node' + str(idx), [48, 48, 48])
# XXX:         cell.add_node(node)
# XXX:
# XXX:     alloc = scheduler.Allocation([10, 10, 10])
# XXX:     cell.add_allocation('a1', alloc)
# XXX:
# XXX:     sched = scheduler.Scheduler(cell)
# XXX:
# XXX:     for attempt in range(0, attempts):
# XXX:         for app_idx in range(0, app_count):
# XXX:             prio = attempt * 5 + random.randint(0, 5)
# XXX:             demand = [random.randint(1, 48),
# XXX:                       random.randint(1, 48),
# XXX:                       random.randint(1, 48)]
# XXX:             name = 'app_%s.%s' % (attempt, app_idx)
# XXX:             alloc.add(scheduler.Application(name, prio, demand,
# XXX:                                             affinity=affinity(app_idx)))
# XXX:
# XXX:         schedule(sched)


# XXX: Test needs update to new Scheduler API
# XXX:
# XXX: def test_affinity(nodes_count, app_count, affinity_limit):
# XXX:     """Add more apps than nodes count to test affinity limit algo."""
# XXX:     print('node: %s, apps: %s, affinity_limit %s' % (nodes_count,
# XXX:                                                      app_count,
# XXX:                                                      affinity_limit))
# XXX:
# XXX:     cell = scheduler.Cell(3)
# XXX:     for idx in range(0, nodes_count):
# XXX:         node = scheduler.Node('node' + str(idx), [48, 48, 48])
# XXX:         cell.add_node(node)
# XXX:
# XXX:     alloc = scheduler.Allocation([10, 10, 10])
# XXX:     cell.add_allocation('a1', alloc)
# XXX:     for app_idx in range(0, app_count):
# XXX:         name = '1.%s' % (app_idx)
# XXX:         alloc.add(scheduler.Application(name, 0, [1, 1, 1],
# XXX:                                         affinity_limit=affinity_limit,
# XXX:                                         affinity='1'))
# XXX:         name = '2.%s' % (app_idx)
# XXX:         alloc.add(scheduler.Application(name, 0, [1, 1, 1],
# XXX:                                         affinity_limit=affinity_limit,
# XXX:                                         affinity='2'))
# XXX:         name = '3.%s' % (app_idx)
# XXX:         alloc.add(scheduler.Application(name, 0, [1, 1, 1],
# XXX:                                         affinity_limit=affinity_limit,
# XXX:                                         affinity='3'))
# XXX:
# XXX:     sched = scheduler.Scheduler(cell)
# XXX:     schedule(sched)


if __name__ == '__main__':
    pass
# XXX:     test_reschedule(500, 1000, 5, affinity=lambda idx: None)
# XXX:     test_reschedule(1000, 1000, 3, affinity=str)
# XXX:     test_reschedule(1000, 3000, 3, affinity=lambda idx: str(idx % 5))
# XXX:     test_affinity(500, 1000, 1)
