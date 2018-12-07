"""Implementation of state API.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

import logging

import json
import os
import re
import zlib
import sqlite3
import tempfile
import fnmatch
import collections
import time

from treadmill import context
from treadmill import schema
from treadmill import utils
from treadmill import yamlwrapper as yaml
from treadmill import zknamespace as z
from treadmill import zkutils


_LOGGER = logging.getLogger(__name__)


def watch_scheduled(zkclient, cell_state):
    """Watch scheduled instances."""

    @zkclient.ChildrenWatch(z.path.scheduled())
    @utils.exit_on_unhandled
    def _watch_scheduled(scheduled):
        """Watch /scheduled nodes."""
        cell_state.scheduled = set(scheduled)
        return True

    _LOGGER.info('Loaded scheduled.')


def watch_running(zkclient, cell_state):
    """Watch running instances."""

    @zkclient.ChildrenWatch(z.path.running())
    @utils.exit_on_unhandled
    def _watch_running(running):
        """Watch /running nodes."""
        cell_state.running = set(running)
        return True

    _LOGGER.info('Loaded running.')


def watch_finished(zkclient, cell_state):
    """Watch finished instances."""

    @zkclient.ChildrenWatch(z.path.finished())
    @utils.exit_on_unhandled
    def _watch_finished(finished):
        """Watch /finished nodes."""
        updated_finished = cell_state.finished.copy()

        current = set(updated_finished)
        target = set(finished)

        for instance in target - current:
            finished_data = zkutils.get_default(
                zkclient, z.path.finished(instance), {}
            )
            updated_finished[instance] = finished_data

        for instance in current - target:
            del updated_finished[instance]

        cell_state.finished = updated_finished

    _LOGGER.info('Loaded finished.')


def watch_placement(zkclient, cell_state):
    """Watch placement."""

    @zkclient.DataWatch(z.path.placement())
    @utils.exit_on_unhandled
    def _watch_placement(placement_data, _stat, event):
        """Watch /placement data."""
        if placement_data is None or event == 'DELETED':
            cell_state.placement.clear()
            return True

        placement = json.loads(
            zlib.decompress(placement_data).decode()
        )

        cell_state.placement = {
            instance: {'host': after, 'expires': exp_after}
            for instance, _before, _exp_before, after, exp_after in placement
            if after
        }
        return True

    _LOGGER.info('Loaded placement.')


def watch_finished_history(zkclient, cell_state):
    """Watch finished historical snapshots."""

    loaded_snapshots = {}

    @zkclient.ChildrenWatch(z.FINISHED_HISTORY)
    @utils.exit_on_unhandled
    def _watch_finished_snapshots(snapshots):
        """Watch /finished.history nodes."""
        start_time = time.time()
        updated_finished_history = cell_state.finished_history.copy()

        for db_node in sorted(set(loaded_snapshots) - set(snapshots)):
            _LOGGER.info('Unloading snapshot: %s', db_node)
            for instance in loaded_snapshots.pop(db_node):
                updated_finished_history.pop(instance, None)

        for db_node in sorted(set(snapshots) - set(loaded_snapshots)):
            _LOGGER.info('Loading snapshot: %s', db_node)
            loading_start_time = time.time()
            loaded_snapshots[db_node] = []

            data, _stat = zkclient.get(z.path.finished_history(db_node))

            with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
                f.write(zlib.decompress(data))
            try:
                conn = sqlite3.connect(f.name)
                cur = conn.cursor()
                sql = 'SELECT name, data FROM finished ORDER BY timestamp'
                for row in cur.execute(sql):
                    instance, data = row
                    if data:
                        data = yaml.load(data)
                    updated_finished_history[instance] = data
                    loaded_snapshots[db_node].append(instance)
                conn.close()
            finally:
                os.unlink(f.name)

            _LOGGER.debug('Loading time: %s', time.time() - loading_start_time)

        cell_state.finished_history = updated_finished_history
        _LOGGER.debug(
            'Loaded snapshots: %d, finished: %d, finished history: %d, '
            'time: %s', len(loaded_snapshots), len(cell_state.finished),
            len(cell_state.finished_history), time.time() - start_time
        )

        return True

    _LOGGER.info('Loaded finished snapshots.')


class CellState:
    """Cell state."""

    __slots__ = (
        'scheduled',
        'running',
        'placement',
        'finished',
        'finished_history',
        'watches',
    )

    def __init__(self):
        self.scheduled = set()
        self.running = set()
        self.placement = {}
        self.finished = {}
        self.finished_history = collections.OrderedDict()
        self.watches = set()

    def get(self, instance):
        """Get instance state."""
        if instance not in self.scheduled:
            return None

        state = {
            'name': instance,
            'state': 'pending',
            'host': None,
            'expires': None,
        }

        if instance in self.placement:
            state['state'] = 'scheduled'
            state.update(self.placement[instance])

        if instance in self.running:
            state['state'] = 'running'

        return state

    def get_finished(self, instance):
        """Get finished instance state."""
        data = (self.finished.get(instance) or
                self.finished_history.get(instance))

        if not data:
            return None

        state = {
            'name': instance,
            'state': data['state'],
            'host': data['host'],
            'when': data['when'],
        }
        if data['state'] == 'finished' and data['data']:
            try:
                rc, signal = map(int, data['data'].split('.'))
                if rc > 255:
                    state['signal'] = signal
                else:
                    state['exitcode'] = rc
            except ValueError:
                _LOGGER.warning('Unexpected finished state data for %s: %s',
                                instance, data['data'])

        if data['state'] == 'aborted' and data['data']:
            state['aborted_reason'] = data['data']

        if data['state'] == 'terminated' and data['data']:
            state['terminated_reason'] = data['data']

        state['oom'] = data['state'] == 'killed' and data['data'] == 'oom'

        return state


class API:
    """Treadmill State REST api."""

    _FINISHED_LIMIT = 1000

    @staticmethod
    def _get_server_info():
        """Get server information"""
        return context.GLOBAL.admin.server().list({
            'cell': context.GLOBAL.cell
        })

    def __init__(self):

        if context.GLOBAL.cell is not None:
            zkclient = context.GLOBAL.zk.conn
            cell_state = CellState()

            _LOGGER.info('Initializing api.')

            watch_scheduled(zkclient, cell_state)
            watch_running(zkclient, cell_state)
            watch_placement(zkclient, cell_state)
            watch_finished(zkclient, cell_state)
            watch_finished_history(zkclient, cell_state)

        def _list(match=None, finished=False, partition=None):
            """List instances state."""
            _LOGGER.info('list: %s %s %s', match, finished, partition)
            start_time = time.time()

            if match is None:
                match = '*'
            if '#' not in match:
                match += '#*'
            match_re = re.compile(fnmatch.translate(os.path.normcase(match)))

            def _match(name):
                return match_re.match(os.path.normcase(name)) is not None

            hosts = None
            if partition:
                hosts = [server['_id'] for server in API._get_server_info()
                         if server['partition'] == partition]

            filtered = []

            for name in cell_state.scheduled:
                state = cell_state.get(name)
                if ((state and _match(name) and
                     (hosts is None or state['host'] in hosts))):
                    filtered.append(state)

            if finished:
                filtered_finished = {}

                def _filter_finished(iterable, limit=None):
                    added = 0
                    for name in iterable:
                        if not _match(name):
                            continue
                        if limit and added >= limit:
                            break
                        item = cell_state.get_finished(name)
                        if item and (hosts is None or item['host'] in hosts):
                            filtered_finished[name] = item
                            added += 1

                _filter_finished(cell_state.finished)
                _filter_finished(reversed(cell_state.finished_history),
                                 self._FINISHED_LIMIT)

                filtered.extend(sorted(filtered_finished.values(),
                                       key=lambda item: float(item['when']),
                                       reverse=True)[:self._FINISHED_LIMIT])

            res = sorted(filtered, key=lambda item: item['name'])
            _LOGGER.debug('list time: %s', time.time() - start_time)
            return res

        @schema.schema({'$ref': 'instance.json#/resource_id'})
        def get(rsrc_id):
            """Get instance state."""
            state = cell_state.get(rsrc_id) or cell_state.get_finished(rsrc_id)
            return state

        self.list = _list
        self.get = get
