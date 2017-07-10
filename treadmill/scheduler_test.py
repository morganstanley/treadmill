#!/usr/bin/env python

"""Performance test for treadmill.scheduler
"""

import random
import time

from . import scheduler
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
            "memory": "1M",
            "disk": "10G",
            "cpu": "1%"
        })
        name = 'app_.%s' % (app_idx)
        app = scheduler.Application(
            name, prio, demand, affinity=affinity(app_idx))
        cell.partitions[None].allocation.add(app)

    return cell


if __name__ == '__main__':
    cell = prepareData(20, 1, affinity=lambda idx: None)
    print(cell.schedule())
