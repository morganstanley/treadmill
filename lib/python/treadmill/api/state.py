"""Implementation of state API."""
from __future__ import absolute_import

import logging

import os
import zlib
import sqlite3
import tempfile
import fnmatch

import yaml

from treadmill import context
from treadmill import schema
from treadmill import exc
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)


def watch_running(zkclient, cell_state):
    """Watch running instances."""

    @exc.exit_on_unhandled
    @zkclient.ChildrenWatch(z.path.running())
    def _watch_running(running):
        """Watch /running nodes."""
        cell_state.running = set(running)
        for name, item in cell_state.placement.iteritems():
            state = item['state'] = (
                'running' if name in cell_state.running else 'scheduled'
            )
            if item['host'] is not None:
                item['state'] = state
        return True

    _LOGGER.info('Loaded running.')


def watch_finished(zkclient, cell_state):
    """Watch finished instances."""

    @exc.exit_on_unhandled
    @zkclient.ChildrenWatch(z.path.finished())
    def _watch_finished(finished):
        """Watch /finished nodes."""
        for instance in finished:
            if instance in cell_state.finished:
                continue
            finished_data = zkutils.get_default(
                zkclient,
                z.path.finished(instance),
                {}
            )
            cell_state.finished[instance] = finished_data

    _LOGGER.info('Loaded finished.')


def watch_placement(zkclient, cell_state):
    """Watch placement."""

    @exc.exit_on_unhandled
    @zkclient.DataWatch(z.path.placement())
    def _watch_placement(placement, _stat, event):
        """Watch /placement data."""
        if placement is None or event == 'DELETED':
            cell_state.placement.clear()
            return True

        updated_placement = {}
        for row in yaml.load(placement):
            instance, _before, _exp_before, after, expires = tuple(row)
            if after is None:
                state = 'pending'
            else:
                state = 'scheduled'
                if instance in cell_state.running:
                    state = 'running'
            updated_placement[instance] = {
                'state': state,
                'host': after,
                'expires': expires,
            }
        cell_state.placement = updated_placement
        return True

    _LOGGER.info('Loaded placement.')


def watch_finished_history(zkclient, cell_state):
    """Watch finished historical snapshots."""

    loaded_snapshots = set()
    _len_finished = len('/finished/')

    def _get_instance(path):
        """Get instance from finished node name."""
        return path[_len_finished:]

    @exc.exit_on_unhandled
    @zkclient.ChildrenWatch(z.FINISHED_HISTORY)
    def _watch_finished_snapshots(snapshots):
        """Watch /finished.history nodes."""
        for db_node in set(snapshots) - loaded_snapshots:
            _LOGGER.debug('Loading snapshot: %s', db_node)
            data, _stat = zkclient.get(z.path.finished_history(db_node))

            with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
                f.write(zlib.decompress(data))

            conn = sqlite3.connect(f.name)
            cur = conn.cursor()
            for row in cur.execute('select path, data from finished;'):
                path, data = row
                instance = _get_instance(path)
                if data:
                    data = yaml.load(data)
                cell_state.finished[instance] = data
            conn.close()
            os.unlink(f.name)

        return True

    _LOGGER.info('Loaded finished snapshots.')


class CellState(object):
    """Cell state."""

    __slots__ = (
        'running',
        'placement',
        'finished',
        'watches',
    )

    def __init__(self):
        self.running = []
        self.placement = {}
        self.finished = {}
        self.watches = set()

    def get_finished(self, rsrc_id):
        """Select finished state if present."""
        return self.finished.get(rsrc_id)


class API(object):
    """Treadmill State REST api."""

    def __init__(self):

        if context.GLOBAL.cell is not None:
            zkclient = context.GLOBAL.zk.conn
            cell_state = CellState()

            _LOGGER.info('Initializing api.')

            watch_running(zkclient, cell_state)
            watch_placement(zkclient, cell_state)
            watch_finished(zkclient, cell_state)
            watch_finished_history(zkclient, cell_state)

        def _list(match=None, finished=False):
            """List instances state."""
            if match is None:
                match = '*'
            if '#' not in match:
                match += '#*'
            filtered = [
                {'name': name, 'state': item['state'], 'host': item['host']}
                for name, item in cell_state.placement.iteritems()
                if fnmatch.fnmatch(name, match)
            ]

            if finished:
                for name, data in cell_state.finished.iteritems():
                    if fnmatch.fnmatch(name, match):
                        item = {
                            'name': name,
                            'state': 'finihsed'
                        }
                        item.update(data)
                        filtered.append(item)

            return sorted(filtered, key=lambda item: item['name'])

        @schema.schema({'$ref': 'instance.json#/resource_id'})
        def get(rsrc_id):
            """Get instance state."""
            data = None
            if rsrc_id in cell_state.placement:
                data = cell_state.placement[rsrc_id]
            else:
                data = cell_state.get_finished(rsrc_id)

            if data:
                data.update({'name': rsrc_id})

            return data

        self.list = _list
        self.get = get


def init(_authorizer):
    """Returns module API wrapped with authorizer function."""
    # There is no authorization for state api.
    return API()
