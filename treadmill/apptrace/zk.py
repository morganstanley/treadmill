"""Watch for application state transitions."""


import fnmatch
import logging
import os
import time

import kazoo

from treadmill import exc
from treadmill import zknamespace as z

from . import events as traceevents

_LOGGER = logging.getLogger(__name__)


class AppTrace(object):
    """Trace application lifecycle events.

    Application events are stored under app task Zookeeper directory, sequence
    node for each event.

    events are in the form:
    timestamp,source,event,msg
    """
    def __init__(self, zkclient, instanceid, callback=None):
        self.zk = zkclient
        self.instanceid = instanceid
        self._last_event = 0
        self._is_done = zkclient.handler.event_object()
        self._callback = callback

    def run(self, snapshot=False, ctx=None):
        """Process application events.
        """
        children_watch_created = self.zk.handler.event_object()
        if snapshot:
            self._is_done.set()

        # Setup the instance ID's scheduled status watch
        @self.zk.DataWatch(z.path.scheduled(self.instanceid))
        @exc.exit_on_unhandled
        def _watch_scheduled(data, stat, event):
            """Called when app scheduled node is modified.
            """
            if data is None and stat is None:
                # Node does not exist yet (or already gone).
                self._is_done.set()
                return False

            elif event and event.type == 'DELETED':
                # Node is deleted.
                self._is_done.set()
                return False

            else:
                return not snapshot

        # Setup the instance ID's task watch
        task_node = z.path.task(self.instanceid)

        @self.zk.DataWatch(task_node)
        @exc.exit_on_unhandled
        def _watch_task(data, stat, event):
            """Watch for task to appear and then process events.
            """
            if data is None and stat is None:
                # Node doesn't exist yet.
                _LOGGER.info('Task znode not exist %r', task_node)
                return True

            elif event and event.type == 'DELETED':
                # If task node is deleted, this is fatal, and we should exit.
                _LOGGER.warning('Task znode deleted %r', task_node)
                self._is_done.set()
                return False

            else:
                if not children_watch_created.is_set():
                    children_watch_created.set()
                    # Setup the instance ID's task node children events

                    @self.zk.ChildrenWatch(task_node)
                    @exc.exit_on_unhandled
                    def _watch_task_events(event_nodes):
                        """Process new children events."""
                        self._process_events(event_nodes, ctx)
                        return not snapshot

                return not snapshot

    def wait(self, timeout=None):
        """Wait for app lifecycle to finish.

        Returns True if event loop is finished, False otherwise (timeout).
        """
        return self._is_done.wait(timeout=timeout)

    def _process_events(self, event_nodes, ctx):
        """Process task event nodes.
        """
        all_events = sorted([tuple(event_node.split(','))
                             for event_node in event_nodes])

        for timestamp, source, event_type, event_data in all_events:
            if timestamp <= self._last_event:
                continue

            self._process_event(timestamp, source, event_type, event_data, ctx)
            self._last_event = timestamp

    def _process_event(self, timestamp, source, event_type, event_data, ctx):
        """Process event of given type."""
        # Master events.
        event = traceevents.AppTraceEvent.from_data(
            timestamp=timestamp,
            source=source,
            instanceid=self.instanceid,
            event_type=event_type,
            event_data=event_data,
        )
        if event is not None:
            self._callback.process(event, ctx)


def cleanup(zkclient, expire_after, max_events=1024):
    """Iterates over tasks nodes and deletes all that are expired."""
    # Enumerate all tasks.
    tasks = set(zkclient.get_children('/tasks'))
    scheduled = set(zkclient.get_children('/scheduled'))

    for task in tasks:
        task_node = os.path.join('/tasks', task)
        instances = set(zkclient.get_children(task_node))

        # Filter out instances that are not running
        finished = set([instance for instance in instances
                        if '#'.join([task, instance]) not in scheduled])

        for instance in instances:
            instance_node = os.path.join(task_node, instance)
            _LOGGER.info('Processing task: %s/%s', task_node, instance)
            events = sorted([tuple(reversed(node.rsplit('-', 1)))
                             for node in zkclient.get_children(instance_node)])
            # Maintain at most N events
            if len(events) > max_events:
                extra = len(events) - max_events
                _LOGGER.info('Deleting extra events for node: %s %s',
                             instance_node, extra)

                for event in events[:extra]:
                    ev_node = '-'.join(reversed(event))
                    ev_fullpath = os.path.join(task_node, instance, ev_node)

                    zkclient.delete(ev_fullpath)

            if instance in finished:
                # Check last event time stamp, and it if is > expired, mark
                # the whole node as expired.
                expired = False
                if not events:
                    expired = True
                else:
                    last_ev_node = '-'.join(reversed(events[-1]))
                    last_ev_fullpath = os.path.join(task_node,
                                                    instance,
                                                    last_ev_node)
                    _data, metadata = zkclient.get(last_ev_fullpath)
                    if metadata.last_modified + expire_after < time.time():
                        _LOGGER.info('Instance %s expired.', instance)
                        expired = True

                # If xpired, delete all events and then delete the task node.
                if expired:
                    _LOGGER.info('Deleting instance node: %s', instance_node)
                    zkclient.delete(instance_node, recursive=True)

        try:
            zkclient.delete('/tasks/' + task)
            _LOGGER.info('/tasks/%s empty, deleting.', task)
        except kazoo.exceptions.NotEmptyError:
            _LOGGER.info('/tasks/%s not empty.', task)


def list_history(zkclient, app_pattern):
    """List all historical tasks for given app name."""
    tasks = []
    for app in zkclient.get_children('/tasks'):
        if fnmatch.fnmatch(app, app_pattern):
            instances = zkclient.get_children(os.path.join('/tasks', app))
            tasks.extend([app + '#' + instance for instance in instances])

    return tasks
