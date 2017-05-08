"""Handles reports over scheduler data."""

import time
import datetime
import itertools
import logging

import numpy as np
import pandas as pd
from functools import reduce


_LOGGER = logging.getLogger(__name__)


def servers(cell):
    """Returns dataframe for servers hierarchy."""

    def _server_row(server):
        """Converts server object to dict used to construct dataframe row.
        """
        row = {
            'name': server.name,
            'memory': server.init_capacity[0],
            'cpu': server.init_capacity[1],
            'disk': server.init_capacity[2],
            'traits': server.traits.traits,
            'free.memory': server.free_capacity[0],
            'free.cpu': server.free_capacity[1],
            'free.disk': server.free_capacity[2],
            'state': server.state.value,
            'valid_until': server.valid_until
        }

        node = server.parent
        while node:
            row[node.level] = node.name
            node = node.parent

        return row

    frame = pd.DataFrame.from_dict([
        _server_row(server) for server in cell.members().values()
    ])
    if frame.empty:
        frame = pd.DataFrame(columns=['name', 'memory', 'cpu', 'disk',
                                      'free.memory', 'free.cpu', 'free.disk',
                                      'state'])
    for col in ['valid_until']:
        frame[col] = pd.to_datetime(frame[col], unit='s')

    return frame.set_index('name')


def allocations(cell):
    """Converts cell allocations into dataframe row."""

    def _leafs(path, alloc):
        """Generate leaf allocations - (path, alloc) tuples."""
        if not alloc.sub_allocations:
            return iter([('/'.join(path), alloc)])
        else:
            def _chain(acc, item):
                """Chains allocation iterators."""
                name, suballoc = item
                return itertools.chain(acc, _leafs(path + [name], suballoc))

            return reduce(_chain, iter(alloc.sub_allocations.items()), [])

    def _alloc_row(label, name, alloc):
        """Converts allocation to dict/dataframe row."""
        if not name:
            name = 'root'
        if not label:
            label = '-'

        return {
            'label': label,
            'name': name,
            'memory': alloc.reserved[0],
            'cpu': alloc.reserved[1],
            'disk': alloc.reserved[2],
            'rank': alloc.rank,
            'traits': alloc.traits,
            'max_utilization': alloc.max_utilization,
        }

    all_allocs = []
    for label, partition in cell.partitions.items():
        allocation = partition.allocation
        leaf_allocs = _leafs([], allocation)
        alloc_df = pd.DataFrame.from_dict(
            [_alloc_row(label, name, alloc) for name, alloc in leaf_allocs]
        ).set_index(['label', 'name'])
        all_allocs.append(alloc_df)
    return pd.concat(all_allocs)


def apps(cell):
    """Return application queue and app details as dataframe."""

    def _app_row(item):
        """Converts app queue item into dict for dataframe row."""
        rank, util, pending, order, app = item
        return {
            'instance': app.name,
            'affinity': app.affinity.name,
            'allocation': app.allocation.name,
            'rank': rank,
            'label': app.allocation.label,
            'util': util,
            'pending': pending,
            'order': order,
            'identity_group': app.identity_group,
            'identity': app.identity,
            'memory': app.demand[0],
            'cpu': app.demand[1],
            'disk': app.demand[2],
            'lease': app.lease,
            'expires': app.placement_expiry,
            'data_retention_timeout': app.data_retention_timeout,
            'server': app.server
        }

    queue = []
    for partition in cell.partitions.values():
        allocation = partition.allocation
        queue += allocation.utilization_queue(cell.size(allocation.label))

    frame = pd.DataFrame.from_dict([_app_row(item) for item in queue])
    if frame.empty:
        return frame

    for col in ['expires']:
        frame[col] = pd.to_datetime(frame[col], unit='s')
    for col in ['lease', 'data_retention_timeout']:
        frame[col] = pd.to_timedelta(frame[col], unit='s')

    return frame.set_index('instance')


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
                                   'memory': np.sum,
                                   'disk': np.sum,
                                   'count': np.sum,
                                   'util': np.max})
    row = row.stack()
    dt_now = datetime.datetime.fromtimestamp(time.time())
    current = pd.DataFrame([row], index=pd.DatetimeIndex([dt_now]))

    if prev_utilization is None:
        return current
    else:
        return prev_utilization.append(current)
