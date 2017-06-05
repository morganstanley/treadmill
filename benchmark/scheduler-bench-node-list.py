#!/usr/bin/env python

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

def prepareData(nodes_count, app_count, affinity):
    scheduler.DIMENSION_COUNT = 3
    cell = scheduler.Cell("local", labels=set([None]))
    for idx in range(0, nodes_count):
        node = scheduler.Server('node' + str(idx), resources({
            "memory": "2G",
            "disk": "20G",
            "cpu": "90%"
        }), time.time() * 2)
        cell.add_node(node)

    for app_idx in range(0, app_count):
        prio = random.randint(0, 5)
        demand = resources({
            "memory": "1G",
            "disk": "10G",
            "cpu": "40%"
        })
        name = 'app_.%s' % (app_idx)
        app = scheduler.Application(name, prio, demand, affinity=affinity(app_idx))
        cell.partitions[None].allocation.add(app)

    return cell


if __name__ == '__main__':
    cell = None
    for i in range(500, 1001):
        if i % 10 ==0:
            cell = prepareData(i, 1000, affinity=lambda idx: None)
            print(i, timeit.timeit("cell.schedule()",
                                setup="from __main__ import cell", number=10))

# import cProfile
# import pstats
# if __name__ == '__main__':
#     cProfile.run('test_reschedule(5000, 10000, 1, affinity=lambda idx: None)', 'restats')
#     p = pstats.Stats('restats')
#     p.strip_dirs().sort_stats('tottime').print_stats()