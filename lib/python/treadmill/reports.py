"""Handles reports over scheduler data.
"""

from __future__ import division
from __future__ import unicode_literals
from __future__ import absolute_import
from __future__ import print_function

import bz2
import datetime
import fnmatch
import io
import itertools
import logging
import time

import numpy as np
import pandas as pd

import six

from treadmill import scheduler
from treadmill import traits

_LOGGER = logging.getLogger(__name__)


def servers(cell, trait_codes):
    """Prepare DataFrame with server information."""

    # Hard-code order of columns
    columns = [
        'name', 'location', 'partition', 'traits',
        'state', 'valid_until',
        'mem', 'cpu', 'disk',
        'mem_free', 'cpu_free', 'disk_free'
    ]

    def _server_location(node):
        """Recursively yield the node's parents."""
        while node:
            yield node.name
            node = node.parent

    def _server_row(server):
        """Transform server into a DataFrame-ready dict."""
        partition = list(server.labels)[0]
        traitz = traits.format_traits(trait_codes, server.traits.traits)
        row = {
            'name': server.name,
            'location': '/'.join(reversed(list(
                _server_location(server.parent)
            ))),
            'partition': partition if partition else '-',
            'traits': traitz,
            'state': server.state.value,
            'valid_until': server.valid_until,
            'mem': server.init_capacity[0],
            'cpu': server.init_capacity[1],
            'disk': server.init_capacity[2],
            'mem_free': server.free_capacity[0],
            'cpu_free': server.free_capacity[1],
            'disk_free': server.free_capacity[2]
        }

        return row

    rows = [_server_row(server) for server in cell.members().values()]
    frame = pd.DataFrame.from_dict(rows)
    if frame.empty:
        frame = pd.DataFrame(columns=columns)

    frame = frame.astype({
        'mem': 'int',
        'cpu': 'int',
        'disk': 'int',
        'mem_free': 'int',
        'cpu_free': 'int',
        'disk_free': 'int'
    })

    return frame[columns].sort_values(
        by=['partition', 'name']).reset_index(drop=True)


def iterate_allocations(path, alloc):
    """Generate (path, alloc) tuples for the leaves of the allocation tree."""
    if not alloc.sub_allocations:
        return iter([('/'.join(path), alloc)])
    else:
        def _chain(acc, item):
            """Chains allocation iterators."""
            name, suballoc = item
            return itertools.chain(
                acc,
                iterate_allocations(path + [name], suballoc)
            )

        return six.moves.reduce(
            _chain,
            six.iteritems(alloc.sub_allocations),
            []
        )


def allocations(cell, trait_codes):
    """Prepare DataFrame with allocation information."""

    # Hard-code order of columns
    columns = [
        'partition', 'name', 'mem', 'cpu', 'disk',
        'rank', 'rank_adj', 'traits', 'max_util'
    ]

    def _alloc_row(partition, name, alloc):
        """Transform allocation into a DataFrame-ready dict."""
        if not name:
            name = 'root'
        if not partition:
            partition = '-'

        traitz = traits.format_traits(trait_codes, alloc.traits)

        return {
            'partition': partition,
            'name': name,
            'mem': alloc.reserved[0],
            'cpu': alloc.reserved[1],
            'disk': alloc.reserved[2],
            'rank': alloc.rank,
            'rank_adj': alloc.rank_adjustment,
            'traits': traitz,
            'max_util': alloc.max_utilization,
        }

    frame = pd.DataFrame.from_dict(
        [
            _alloc_row(label, name, alloc)
            for label, partition in six.iteritems(cell.partitions)
            for name, alloc in iterate_allocations(
                [], partition.allocation
            )
        ]
    )
    if frame.empty:
        frame = pd.DataFrame(columns=columns)

    return frame[columns].astype({
        'mem': 'int',
        'cpu': 'int',
        'disk': 'int'
    }).sort_values(by=['partition', 'name']).reset_index(drop=True)


def apps(cell, _trait_codes):
    """Prepare DataFrame with app and queue information."""

    # Hard-code order of columns
    columns = [
        'instance', 'allocation', 'rank', 'affinity', 'partition',
        'identity_group', 'identity',
        'order', 'lease', 'expires', 'data_retention',
        'pending', 'server', 'util0', 'util1',
        'mem', 'cpu', 'disk'
    ]

    def _app_row(item):
        """Transform app into a DataFrame-ready dict."""
        rank, util0, util1, pending, order, app = item
        return {
            'instance': app.name,
            'affinity': app.affinity.name,
            'allocation': app.allocation.name,
            'rank': rank,
            'partition': app.allocation.label or '-',
            'util0': util0,
            'util1': util1,
            'pending': pending,
            'order': order,
            'identity_group': app.identity_group,
            'identity': app.identity,
            'mem': app.demand[0],
            'cpu': app.demand[1],
            'disk': app.demand[2],
            'lease': app.lease,
            'expires': app.placement_expiry,
            'data_retention': app.data_retention_timeout,
            'server': app.server
        }

    queue = []
    for partition in cell.partitions.values():
        allocation = partition.allocation
        queue += allocation.utilization_queue(cell.size(allocation.label))

    frame = pd.DataFrame.from_dict([_app_row(item) for item in queue]).fillna({
        'expires': -1,
        'identity': -1,
        'data_retention': -1
    })
    if frame.empty:
        frame = pd.DataFrame(columns=columns)

    return frame[columns].astype({
        'mem': 'int',
        'cpu': 'int',
        'disk': 'int',
        'order': 'int',
        'expires': 'int',
        'data_retention': 'int',
        'identity': 'int'
    }).sort_values(by=['partition',
                       'rank',
                       'util0',
                       'util1',
                       'pending',
                       'order']).reset_index(drop=True)


def utilization(prev_utilization, apps_df):
    """Returns dataseries describing cell utilization.

    prev_utilization - utilization dataframe before current.
    apps - app queue dataframe.
    """
    # Passed by ref.
    row = apps_df.reset_index()
    if row.empty:
        return row

    row['count'] = 1
    row['name'] = row['instance'].apply(lambda x: x.split('#')[0])
    row = row.groupby('name').agg({'cpu': np.sum,
                                   'mem': np.sum,
                                   'disk': np.sum,
                                   'count': np.sum,
                                   'util0': np.max,
                                   'util1': np.max})
    row = row.stack()
    dt_now = datetime.datetime.fromtimestamp(time.time())
    current = pd.DataFrame([row], index=pd.DatetimeIndex([dt_now]))

    if prev_utilization is None:
        return current
    else:
        return prev_utilization.append(current)


def reboots(cell):
    """Prepare dataframe with server reboot info."""

    # Hard-code order of columns
    columns = [
        'server', 'valid-until', 'days-left',
    ]

    def _reboot_row(server, now):
        valid_until = datetime.datetime.fromtimestamp(server.valid_until)
        return {
            'server': server.name,
            'valid-until': valid_until,
            'days-left': (valid_until - now).days,
        }

    now = datetime.datetime.now()

    frame = pd.DataFrame.from_dict([
        _reboot_row(server, now)
        for server in cell.members().values()
    ])

    return frame[columns]


class ExplainVisitor:
    """Scheduler visitor"""

    def __init__(self):
        """Initialize result"""
        self.result = []

    def add(self, alloc, entry, acc_demand):
        """Add new row to result"""
        rank, util_before, util_after, _pending, _order, app = entry

        alloc_name = ':'.join(alloc.path)
        self.result.append({
            'alloc': alloc_name,
            'rank': rank,
            'util0': util_before,
            'util1': util_after,
            'memory': int(acc_demand[0]),
            'cpu': int(acc_demand[1]),
            'disk': int(acc_demand[2]),
            'name': app.name,
        })

    def finish(self):
        """Post-process result array"""
        def _sort_order(entry):
            return (entry['alloc'],
                    entry['util0'],
                    entry['util1'])

        result = sorted(self.result, key=_sort_order)

        # annotate with position in alloc queue
        pos = 1
        alloc = ''
        for row in result:
            if row['alloc'] != alloc:
                alloc = row['alloc']
                pos = 1
            row['pos'] = pos
            pos = pos + 1

        self.result = result

    def filter(self, pattern):
        """Filter result to rows with matching app instances"""
        self.result = [row for row in self.result
                       if fnmatch.fnmatch(row['name'], pattern)]


def explain_queue(cell, partition, pattern=None):
    """Compute dataframe for explaining app queue"""
    alloc = cell.partitions[partition].allocation
    size = cell.size(partition)
    visitor = ExplainVisitor()
    queue = alloc.utilization_queue(size, visitor.add)

    # we run the generator to completion, and this builds up the
    # visitor as a side-effect
    for _ in queue:
        pass

    visitor.finish()

    if pattern:
        visitor.filter(pattern)

    return pd.DataFrame(visitor.result)


def _preorder_walk(node, _app=None):
    """Walk the tree in preorder"""
    return itertools.chain(
        [node],
        *[_preorder_walk(child) for child in node.children]
    )


def _servers_walk(cell, _app):
    """Return servers only
    """
    return list(six.itervalues(cell.members()))


def _limited_walk(node, app):
    """Walk the tree like preorder, expand nodes iff placement is feasible."""
    if node.check_app_constraints(app):
        return itertools.chain(
            [node],
            *[_limited_walk(child, app) for child in node.children]
        )
    else:
        return [node]


WALKS = {
    'servers': _servers_walk,
    'full': _preorder_walk,
    'default': _limited_walk,
}


def explain_placement(cell, app, mode):
    """Explain placement for app"""
    result = []
    for node in WALKS[mode](cell, app):
        is_server = False
        if isinstance(node, scheduler.Server):
            is_server = True
            lifetime = node.check_app_lifetime(app)
        else:
            lifetime = True
        capacity = node.free_capacity > app.demand
        result.append({
            'name': node.name,
            'server': is_server,
            'affinity': node.check_app_affinity_limit(app),
            'traits': node.traits.has(app.traits),
            'partition': app.allocation.label in node.labels,
            'feasible': node.check_app_constraints(app),
            'state': node.state == scheduler.State.up,
            'lifetime': lifetime,
            'memory': capacity[0],
            'cpu': capacity[1],
            'disk': capacity[2],
        })

    # Hard-code order of columns
    columns = [
        'partition', 'traits', 'affinity', 'state', 'lifetime',
        'memory', 'cpu', 'disk', 'name', 'server'
    ]
    return pd.DataFrame(result, columns=columns)


def serialize_dataframe(report, compressed=True):
    """Serialize a dataframe for storing.

    The dataframe is serialized as CSV and compressed with bzip2.
    """
    result = report.to_csv(index=False)
    if compressed:
        result = bz2.compress(result.encode())
    return result


def deserialize_dataframe(report):
    """Deserialize a dataframe.

    The dataframe is serialized as CSV and compressed with bzip2.
    """
    try:
        content = bz2.decompress(report)
    except IOError:
        content = report
    return pd.read_csv(io.StringIO(content.decode()))
