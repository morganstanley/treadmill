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


def watch_task_instance(zkclient, cell_state, instance):
    """Watch individual task instance."""

    @exc.exit_on_unhandled
    @zkclient.DataWatch(z.path.task(instance))
    def _watch_task(data, _stat, event):
        """Watch for task data."""
        if data is None or event == 'DELETED':
            if instance in cell_state.tasks:
                del cell_state.tasks[instance]
            return False

        cell_state.tasks[instance] = yaml.load(data)
        cont_watch = bool(zkclient.exists(
            z.path.scheduled(instance)
        ))
        _LOGGER.info('Continue watch on %s: %s',
                     z.path.task(instance),
                     cont_watch)
        return cont_watch


def watch_task(zkclient, cell_state, scheduled, task):
    """Watch individual task."""
    task_node = z.join_zookeeper_path(z.TASKS, task)

    # Establish watch on task instances.

    @exc.exit_on_unhandled
    @zkclient.ChildrenWatch(task_node)
    def _watch_task_instances(instance_ids):

        instance = None
        for instance_id in instance_ids:
            instance = '#'.join([task, instance_id])

            # Either watch is established or data is acquired.
            if instance in cell_state.tasks:
                continue

            # On first load, optimize lookup by preloading state
            # of all scheduled instances.
            #
            # Once initial load is done, scheduled will be cleared.
            if scheduled:
                need_watch = instance in scheduled
            else:
                need_watch = zkclient.exists(
                    z.path.scheduled(instance)
                )

            if need_watch:
                watch_task_instance(zkclient, cell_state, instance)
            else:
                data = zkutils.get_default(zkclient, z.path.task(instance))
                cell_state.tasks[instance] = data

        return True


def watch_tasks(zkclient, cell_state):
    """Watch tasks."""

    @exc.exit_on_unhandled
    @zkclient.ChildrenWatch(z.TASKS)
    def _watch_tasks(tasks):
        """Watch /tasks nodes."""
        scheduled = set(zkclient.get_children(z.SCHEDULED))

        for task in tasks:
            if task not in cell_state.watches:
                watch_task(zkclient, cell_state, scheduled, task)
                cell_state.watches.add(task)

        scheduled.clear()
        return True

    _LOGGER.info('Loaded tasks.')


def watch_tasks_history(zkclient, cell_state):
    """Watch tasks history.

    Load summary info from tasks history snapshots. Keep track of changes.
    """
    if not zkclient.exists(z.TASKS_HISTORY):
        _LOGGER.warn('Not loading tasks history, no node: %s', z.TASKS_HISTORY)
        return

    loaded_tasks_history = {}

    def _get_instance(path):
        return '#'.join(path[len(z.TASKS) + 1:].rsplit('/', 1))

    @exc.exit_on_unhandled
    @zkclient.ChildrenWatch(z.TASKS_HISTORY)
    def _watch_tasks_history(tasks_history):
        """Watch /tasks.history nodes."""
        for db_node in set(tasks_history) - set(loaded_tasks_history):
            _LOGGER.debug('Loading tasks history from: %s', db_node)
            db_node_path = z.path.tasks_history(db_node)
            data, _stat = zkclient.get(db_node_path)
            loaded_tasks_history[db_node] = []

            with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
                f.write(zlib.decompress(data))
            conn = sqlite3.connect(f.name)
            cur = conn.cursor()
            for row in cur.execute('select path, data from tasks'
                                   ' where data is not null'):
                path, data = row
                instance = _get_instance(path)
                if data:
                    data = yaml.load(data)
                cell_state.tasks_history[instance] = data
                loaded_tasks_history[db_node].append(instance)
            conn.close()
            os.unlink(f.name)

        for db_node in set(loaded_tasks_history) - set(tasks_history):
            _LOGGER.debug('Unloading tasks history from: %s', db_node)
            for instance in loaded_tasks_history[db_node]:
                del cell_state.tasks_history[instance]
            del loaded_tasks_history[db_node]

        return True

    _LOGGER.info('Loaded tasks history.')


class CellState(object):
    """Cell state."""

    __slots__ = (
        'running',
        'placement',
        'tasks',
        'tasks_history',
        'watches',
    )

    def __init__(self):
        self.running = []
        self.placement = {}
        self.tasks = {}
        self.tasks_history = {}
        self.watches = set()


class API(object):
    """Treadmill State REST api."""

    def __init__(self):

        zkclient = context.GLOBAL.zk.conn

        cell_state = CellState()

        _LOGGER.info('Initializing api.')

        watch_running(zkclient, cell_state)
        watch_placement(zkclient, cell_state)
        watch_tasks(zkclient, cell_state)
        watch_tasks_history(zkclient, cell_state)

        def _list(match=None):
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
            return sorted(filtered, key=lambda item: item['name'])

        @schema.schema({'$ref': 'instance.json#/resource_id'})
        def get(rsrc_id):
            """Get instance state."""
            data = None
            if rsrc_id in cell_state.placement:
                data = cell_state.placement[rsrc_id]
            else:
                data = (cell_state.tasks.get(rsrc_id) or
                        cell_state.tasks_history.get(rsrc_id))
                if data and data.get('state') == 'finished':
                    rc, signal = data.get('data', '255.255').split('.')
                    data['exitcode'] = rc
                    data['signal'] = signal

            if data:
                data.update({'name': rsrc_id})

            return data

        self.list = _list
        self.get = get


def init(_authorizer):
    """Returns module API wrapped with authorizer function."""
    # There is no authorization for state api.
    return API()
